#!/usr/bin/env python3
# pylint: disable=E1101
"""
    BGPMonitoring periodically runs a BGP summary check (session state,
    prefixes received/advertised, up/down) against every switch that
    currently has an active BGP delta, and writes the normalized result
    to the DB for the Prometheus exporter (see SNMPMonitoring/snmpmon.py's
    PromOut.__getBGPData) to pick up.

    "Based on active deltas" means two things:
    1. Only switches whose live ansible host_vars currently has a
       `sense_bgp.neighbor` entry are checked. That key is only present
       while there is at least one active BGP delta for that host (see
       SiteFE.ProvisioningService.modules.RoutingService._getDefaultBGP)
       -- so a host with no active BGP peering is skipped rather than
       producing an empty/irrelevant check.
    2. A check also runs immediately whenever the site's `activeDeltas`
       row changes (a delta was added/removed/modified), rather than
       only on the fixed MAX_CHECK_INTERVAL ceiling -- see
       _activeDeltasChanged()/startwork(). The Daemonizer loop calling
       this still ticks frequently (short --sleeptimeok, e.g. 60s); the
       expensive ansible sweep itself only actually runs when there's a
       delta change to react to, or the ceiling has elapsed, whichever
       comes first.

    Only devices with a `private_asn` configured are ever considered,
    independent of active-delta state -- see _isBgpEnabled(), which
    checks the same field RoutingService._getDefaultBGP itself requires
    before including a device's ASN in sense_bgp at all. The VRF (and,
    as an optimization, which address families to check) is likewise
    read from that same static site config (self.config.get(host, "vrf")
    / "rsts_enabled"), not solely from the transient sense_bgp mirror.

    Runs the same bgpsummary.yaml playbook used by the on-demand BGP
    summary debug action, but against a dedicated "_bgpmon" ansible
    inventory subtree (its own private_data_dir/inventory/host_vars,
    configured in GitConfig.py's ansible defaults) so this sweep can
    never race with a concurrent human-triggered debug request over the
    same inventory files.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/09/15
"""
import sys

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import NoOptionError, NoSectionError
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    contentDB,
    getActiveDeltas,
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
    jsondumps,
    strtolist,
)

COMPONENT = "BGPMonitoring"

# Ceiling on how long a host can go without a fresh check even if
# activeDeltas never changes (e.g. a peer flapped without any delta
# change) -- a delta change triggers a check well before this elapses.
MAX_CHECK_INTERVAL = 3600

# Matches the vendor branches actually present in ansible-templates'
# bgpsummary.yaml -- Arista and FreeRTR have no branch there at all (BGP
# summary is not supported on those platforms in this deployment), so
# they are deliberately excluded here rather than attempted and skipped.
BGP_CAPABLE_NETWORK_OS = {
    "sense.frr.frr",
    "sense.sonic.sonic",
    "sense.dellos9.dellos9",
    "sense.dellos10.dellos10",
    "sense.cisconx9.cisconx9",
    "sense.junos.junos",
}


class BGPMonitoring:
    """BGP Monitoring main process"""

    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service=COMPONENT)
        self.switch = Switch(self.config, self.sitename)
        self.switches = {}
        self.diragent = contentDB()
        self.dbI = getVal(getDBConn(COMPONENT, self), **{"sitename": self.sitename})
        self._lastactivedeltasupdate = None
        self._lastfullcheck = 0
        self.logger.info(f"====== {COMPONENT} Start Work. Sitename: {self.sitename}")

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def _activeDeltasChanged(self):
        """Whether the site's activeDeltas row has changed since the last
        time this was called. writeActiveDeltas() bumps `updatedate` on
        every write, so it's a cheap, reliable change marker -- no need
        to diff the (potentially large) `output` content itself."""
        activedeltas = getActiveDeltas(self)
        marker = activedeltas.get("updatedate", activedeltas.get("insertdate"))
        changed = marker != self._lastactivedeltasupdate
        self._lastactivedeltasupdate = marker
        return changed

    def _isBgpEnabled(self, host):
        """Whether BGP is enabled for this device in site config at all,
        independent of whether it currently has an active delta.

        NOTE: an earlier revision of this also required a "rst" config
        key, copying SiteFE.LookUpService.modules.switchinfo's
        rst/private_asn/rsts_enabled check -- that turned out to be the
        wrong reference: "rst" there gates that module's own narrower
        subnet-pool-advertisement feature, not general BGP capability,
        and real site config (confirmed live) never sets it for devices
        that otherwise fully participate in BGP. "private_asn" is the
        actual, correct gate -- it's the one field RoutingService itself
        requires before including a device's ASN in sense_bgp at all
        (see RoutingService._getDefaultBGP)."""
        try:
            privateasn = self.config.get(host, "private_asn")
        except (NoOptionError, NoSectionError):
            return False
        return bool(privateasn)

    def _getConfiguredVrf(self, host):
        """VRF as configured for this device in site config. Preferred
        over the transient sense_bgp.vrf mirror (which only exists while
        a delta is active) since this is the authoritative, static
        source RoutingService itself reads the value from."""
        try:
            return self.config.get(host, "vrf")
        except (NoOptionError, NoSectionError):
            return ""

    def _getConfiguredAfis(self, host):
        """Address families to check for this device, from its
        `rsts_enabled` site config (e.g. "ipv6" or "ipv4,ipv6"). Purely
        an optimization -- narrows which AFI-scoped ansible calls actually
        run instead of always requesting "both" -- so any missing/unset
        value just falls back to "both" rather than blocking the check."""
        try:
            enabled = strtolist(self.config.get(host, "rsts_enabled"), ",")
        except (NoOptionError, NoSectionError):
            enabled = []
        enabled = [a for a in enabled if a in ("ipv4", "ipv6")]
        return "both" if not enabled or len(enabled) == 2 else enabled[0]

    def _findBGPHosts(self):
        """Find switches with BGP enabled in site config that also have
        an active BGP delta right now."""
        out = {}
        for host in self.switches:
            networkos = self.switch.plugin.getAnsNetworkOS(host)
            if networkos not in BGP_CAPABLE_NETWORK_OS:
                continue
            if not self._isBgpEnabled(host):
                continue
            try:
                hostconfig = self.switch.plugin.getHostConfig(host)
            except Exception as ex:  # pylint: disable=broad-except
                self.logger.warning(f"[{host}]: Unable to read host config, skipping. Exception: {ex}")
                continue
            sensebgp = hostconfig.get("sense_bgp", {}) or {}
            if not sensebgp.get("neighbor"):
                # No active BGP delta on this host right now -- nothing to check.
                continue
            vrf = self._getConfiguredVrf(host) or sensebgp.get("vrf", "")
            out[host] = {"vrf": vrf, "type": self._getConfiguredAfis(host)}
        return out

    def _writeBgpmonInventory(self, hosts):
        """Write inventory + per-host host_vars (with bgp_summary injected)
        into the dedicated _bgpmon inventory subtree."""
        inventory = self.switch.plugin._getInventoryInfo(list(hosts.keys()))
        self.switch.plugin._writeInventoryInfo(inventory, "_bgpmon")
        for host, params in hosts.items():
            hostconfig = self.switch.plugin.getHostConfig(host)
            hostconfig["bgp_summary"] = {
                "vrf": params["vrf"],
                "type": params["type"],
                "detail": True,
            }
            self.switch.plugin._writeHostConfig(host, hostconfig, "_bgpmon")

    @staticmethod
    def _extractBgpSummary(ansOut, host):
        """Pull the registered bgpsummary_result.bgp_summary dict out of
        the ansible run's event stream for one host. Returns None if the
        host has no such event (e.g. it was skipped inside the playbook)."""
        if not ansOut:
            return None
        for hostevent in ansOut.host_events(host):
            if hostevent.get("event") != "runner_on_ok":
                continue
            res = hostevent.get("event_data", {}).get("res", {})
            if "bgp_summary" in res:
                return res["bgp_summary"]
        return None

    def _writeToDB(self, host, output):
        """Write BGP Summary Data to DB"""
        out = {
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
            "hostname": host,
            "output": jsondumps(output),
        }
        dbOut = self.dbI.get("bgpmon", limit=1, search=[["hostname", host]])
        if dbOut:
            out["id"] = dbOut[0]["id"]
            self.dbI.update("bgpmon", [out])
        else:
            self.dbI.insert("bgpmon", [out])

    def startwork(self):
        """Scan all switches, check BGP summary for those with an active
        BGP delta, and refresh their entry in the DB.

        Called frequently by the Daemonizer loop (short --sleeptimeok),
        but the actual (expensive) ansible sweep only runs when
        activeDeltas has changed since the last check, or MAX_CHECK_INTERVAL
        has elapsed since the last full check -- whichever comes first."""
        changed = self._activeDeltasChanged()
        now = getUTCnow()
        if not changed and (now - self._lastfullcheck) < MAX_CHECK_INTERVAL:
            return
        reason = "activeDeltas changed" if changed else f"{MAX_CHECK_INTERVAL}s ceiling elapsed"
        self.logger.info(f"[{self.sitename}]: Running BGP check ({reason}).")
        self._lastfullcheck = now

        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()
        hosts = self._findBGPHosts()
        if not hosts:
            self.logger.info(f"[{self.sitename}]: No hosts with an active BGP delta found. Nothing to check.")
            return
        self._writeBgpmonInventory(hosts)
        ansOut = self.switch.plugin._applyNewConfig(list(hosts.keys()), "_bgpmon", templateName="bgpsummary.yaml")
        checked = 0
        for host in hosts:
            bgpsummary = self._extractBgpSummary(ansOut, host)
            if bgpsummary is None:
                self.logger.warning(f"[{host}]: No BGP summary result found in ansible output. Skipping DB write.")
                continue
            self._writeToDB(host, bgpsummary)
            checked += 1
        self.logger.info(f"[{self.sitename}]: BGP Monitoring finished. Checked {checked}/{len(hosts)} hosts with an active BGP delta.")


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args and len(args) > 1:
        bgpmon = BGPMonitoring(config, args[1])
        bgpmon.startwork()
    else:
        sitename = getSiteNameFromConfig(config)
        bgpmon = BGPMonitoring(config, sitename)
        bgpmon.startwork()


if __name__ == "__main__":
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    print("1st argument has to be sitename which is configured in this frontend")
    print(sys.argv)
    getLoggingObject(logType="StreamLogger", service=COMPONENT)
    execute(args=sys.argv)
