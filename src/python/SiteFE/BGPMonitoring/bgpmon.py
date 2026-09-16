#!/usr/bin/env python3
# pylint: disable=E1101
"""
BGPMonitoring periodically checks BGP session state for switches with an
active SENSE BGP delta, tags each peer sense=True/False, and writes the
result to DB for the Prometheus exporter to pick up.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/09/15
"""
import sys

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import NoOptionError, NoSectionError
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.ipaddr import normalizedip
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
from SiteRMLibs.timing import Timing

COMPONENT = "BGPMonitoring"

MAX_CHECK_INTERVAL = 3600

REPEAT_SCANS_ON_CHANGE = 3

BGP_CAPABLE_NETWORK_OS = {
    "sense.frr.frr",
    "sense.sonic.sonic",
    "sense.dellos9.dellos9",
    "sense.dellos10.dellos10",
    "sense.cisconx9.cisconx9",
    "sense.junos.junos",
}


class BGPMonitoring(Timing):
    """BGP Monitoring main process"""

    def __init__(self, config, sitename):
        super().__init__()
        self.config = config if config else getGitConfig()
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service=COMPONENT)
        self.switch = Switch(self.config, self.sitename)
        self.switches = {}
        self.diragent = contentDB()
        self.dbI = getVal(getDBConn(COMPONENT, self), **{"sitename": self.sitename})
        self._lastActivePeers = None
        self._lastfullcheck = 0
        self._pendingRescans = 0
        self.logger.info(f"====== {COMPONENT} Start Work. Sitename: {self.sitename}")

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def _activeBGPPeersChanged(self, activepeers):
        """Whether the active BGP peer set has changed since the last check."""
        changed = activepeers != self._lastActivePeers
        self._lastActivePeers = activepeers
        return changed

    def _isBgpEnabled(self, host):
        """Whether BGP is enabled for this device in site config (private_asn set)."""
        try:
            privateasn = self.config.get(host, "private_asn")
        except (NoOptionError, NoSectionError):
            return False
        return bool(privateasn)

    def _getConfiguredVrf(self, host):
        """VRF configured for this device in site config."""
        try:
            return self.config.get(host, "vrf")
        except (NoOptionError, NoSectionError):
            return ""

    def _activeBGPPeers(self):
        """Map of host -> set of normalized peer addresses from currently
        active BGP deltas (activeDeltas "rst" map, same fields RoutingService
        uses to build sense_bgp)."""
        activedeltas = getActiveDeltas(self)
        rst = activedeltas.get("output", {}).get("rst", {})
        peersbyhost = {}
        for connDict in rst.values():
            if not isinstance(connDict, dict):
                continue
            for host, hostDict in connDict.items():
                if not isinstance(hostDict, dict):
                    continue
                for rFullDict in hostDict.values():
                    if not isinstance(rFullDict, dict) or not self.checkIfStarted(rFullDict):
                        continue
                    peers = self._peerAddrsFromRoutes(rFullDict)
                    if peers:
                        peersbyhost.setdefault(host, set()).update(peers)
        return peersbyhost

    @staticmethod
    def _bareIP(addr):
        """Normalized IP with any /mask stripped, so a CIDR value (activeDeltas)
        and a bare address (device output) compare equal."""
        if not addr:
            return None
        norm = normalizedip(addr)
        return norm.split("/")[0] if norm else None

    @staticmethod
    def _peerAddrsFromRoutes(rFullDict):
        """Normalized nextHop peer addresses for one activeDeltas rst host/iptype entry."""
        addrs = set()
        for rDict in rFullDict.get("hasRoute", {}).values():
            for iptype in ("ipv4", "ipv6"):
                addr = rDict.get("nextHop", {}).get(f"{iptype}-address", {}).get("value")
                norm = BGPMonitoring._bareIP(addr)
                if norm:
                    addrs.add(norm)
        return addrs

    @staticmethod
    def _tagSensePeers(bgpsummary, activepeers):
        """Tag every peer sense=True/False; keeps all peers, drops none."""
        tagged = dict(bgpsummary)
        tagged["peers"] = [{**peer, "sense": BGPMonitoring._bareIP(peer.get("peer", "")) in activepeers} for peer in bgpsummary.get("peers", [])]
        return tagged

    def _getConfiguredAfis(self, host):
        """Address families to check for this device, from rsts_enabled site config."""
        try:
            enabled = strtolist(self.config.get(host, "rsts_enabled"), ",")
        except (NoOptionError, NoSectionError):
            enabled = []
        enabled = [a for a in enabled if a in ("ipv4", "ipv6")]
        return "both" if not enabled or len(enabled) == 2 else enabled[0]

    def _findBGPHosts(self, activepeers):
        """Switches with BGP enabled and an active BGP delta, with their active peer sets."""
        out = {}
        for host in self.switches:
            peers = activepeers.get(host)
            if not peers:
                continue
            networkos = self.switch.plugin.getAnsNetworkOS(host)
            if networkos not in BGP_CAPABLE_NETWORK_OS:
                continue
            if not self._isBgpEnabled(host):
                continue
            out[host] = {"vrf": self._getConfiguredVrf(host), "type": self._getConfiguredAfis(host), "activepeers": peers}
        return out

    def _writeBgpmonInventory(self, hosts):
        """Write inventory + host_vars (with bgp_summary) into the _bgpmon subtree."""
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
        """Pull bgp_summary from the ansible run's event stream for one host."""
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
        """Scan switches with an active BGP delta and refresh their bgpmon
        DB entry. Runs 3x in a row on a BGP peer-set change (one scan per
        Daemonizer tick), or hourly, whichever comes first."""
        activepeers = self._activeBGPPeers()
        changed = self._activeBGPPeersChanged(activepeers)
        now = getUTCnow()
        if changed:
            self._pendingRescans = REPEAT_SCANS_ON_CHANGE - 1
            reason = "active BGP peer set changed"
        elif self._pendingRescans > 0:
            self._pendingRescans -= 1
            reason = f"post-change re-check, {self._pendingRescans} more queued"
        elif (now - self._lastfullcheck) < MAX_CHECK_INTERVAL:
            return
        else:
            reason = f"{MAX_CHECK_INTERVAL}s ceiling elapsed"
        self.logger.info(f"[{self.sitename}]: Running BGP check ({reason}).")
        self._lastfullcheck = now

        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()
        hosts = self._findBGPHosts(activepeers)
        if not hosts:
            self.logger.info(f"[{self.sitename}]: No hosts with an active BGP delta found. Nothing to check.")
            return
        self._writeBgpmonInventory(hosts)
        ansOut, failures = self.switch.plugin._applyNewConfig(list(hosts.keys()), "_bgpmon", templateName="bgpsummary.yaml")
        if failures:
            self.logger.warning(f"[{self.sitename}]: Ansible failures during BGP check: {failures}")
        checked = 0
        for host, params in hosts.items():
            bgpsummary = self._extractBgpSummary(ansOut, host)
            if bgpsummary is None:
                self.logger.warning(f"[{host}]: No BGP summary result found in ansible output. Skipping DB write.")
                continue
            bgpsummary = self._tagSensePeers(bgpsummary, params["activepeers"])
            if not any(peer.get("sense") for peer in bgpsummary["peers"]):
                self.logger.warning(f"[{host}]: Device's BGP summary did not include any peer matching this host's active BGP delta(s).")
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
