#!/usr/bin/env python3
"""Check for conflicting deltas

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/01/20
"""
import copy
import itertools
from pprint import pprint

from deepdiff import DeepDiff
from SiteRMLibs.BWService import BWService
from SiteRMLibs.CustomExceptions import (
    NoOptionError,
    NoSectionError,
    OverlapException,
    ServiceNotReady,
    WrongIPAddress,
)
from SiteRMLibs.DefaultParams import SERVICE_NOACCEPT_TIMEOUT
from SiteRMLibs.ipaddr import checkOverlap as incheckOverlap
from SiteRMLibs.ipaddr import ipOverlap as inipOverlap
from SiteRMLibs.MainUtilities import getLoggingObject, getUTCnow
from SiteRMLibs.timing import Timing


def _normalize_ip(ip):
    """Normalize IP to list"""
    if ip is None:
        return []
    if isinstance(ip, (list, tuple, set)):
        return list(ip)
    return [ip]


class ConflictChecker(Timing, BWService):
    """Conflict Checker"""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="PolicyService")
        self.newid = ""
        self.oldid = ""
        self.logger.info("Conflict Checker initialized")
        self.checkmethod = ""

    @staticmethod
    def checkOverlap(inrange, ipval, iptype):
        """Check if overlap"""
        out = []
        ipval = _normalize_ip(ipval)
        for ip in ipval:
            out.append(incheckOverlap(inrange, ip, iptype))
        return any(out)

    @staticmethod
    def _ipOverlap(ip1, ip2, iptype):
        """Check if IP Overlap. Return True/False"""
        ip1 = _normalize_ip(ip1)
        ip2 = _normalize_ip(ip2)
        out = []
        for a, b in itertools.product(ip1, ip2):
            out.append(inipOverlap(a, b, iptype))
        return any(out)

    def _checkIfHostAlive(self, polcls, hostname):
        """Check if Host is alive"""
        if hostname in polcls.hosts:
            updatedate = polcls.hosts[hostname]["updatedate"]
            if updatedate < getUTCnow() - SERVICE_NOACCEPT_TIMEOUT:
                raise OverlapException(
                    f"Host {hostname} did not update in the last {SERVICE_NOACCEPT_TIMEOUT // 60} minutes. \
                                       Cannot proceed with this request. Check Agent status for the host \
                                       Last update: {updatedate}, CurrentTime: {getUTCnow()}"
                )
            self._checkIfRulerAlive(polcls, hostname)

    @staticmethod
    def _checkIfRulerAlive(polcls, hostname):
        """Check if Ruler Service is alive on the host"""
        dbitem = polcls.dbI.get("servicestates", search=[["hostname", hostname], ["servicename", "Ruler"]], limit=1)
        if not dbitem:
            raise ServiceNotReady(f"Ruler service not found for {hostname}. Is Agent container running at the site?")

        if dbitem[0]["updatedate"] < getUTCnow() - SERVICE_NOACCEPT_TIMEOUT:
            raise ServiceNotReady(
                f"Ruler service did not update in the last {SERVICE_NOACCEPT_TIMEOUT // 60} minutes for {hostname}. \
                                       Cannot proceed with this request. Check Agent status for the host \
                                       Last update: {dbitem[0]['updatedate']}, CurrentTime: {getUTCnow()}"
            )
        if dbitem[0]["servicestate"] != "OK":
            raise ServiceNotReady(
                f"Ruler service state is not OK for {hostname}. \
                                       Cannot proceed with this request. Check Agent status for the host \
                                       Service state: {dbitem[0]['servicestate']}, Last update: {dbitem[0]['updatedate']}, CurrentTime: {getUTCnow()}. Full info: {dbitem[0]}"
            )

    def _checkVlanSwapping(self, vlans, hostname):
        """Check if vlan Swapping is allowed"""
        swapAllowed = False
        try:
            swapAllowed = self.config.get(hostname, "labelswapping")
        except NoSectionError:
            return
        except NoOptionError:
            swapAllowed = False
        if swapAllowed:
            return
        # If we reach here, means swapping is not allowed.
        if len(vlans) > 1:
            raise OverlapException(
                f"Vlan swapping is not allowed for {hostname}. \
                                   Request is invalid. Current requested vlans: {vlans}"
            )

    @staticmethod
    def _checkVlanInRange(polcls, vlan, hostname):
        """Check if VLAN in Allowed range"""
        if not vlan or not vlan.get("vlan", "") or not vlan.get("interface", ""):
            return
        # If Agent, check in agent reported configuration
        if hostname in polcls.hosts:
            interfaces = polcls.hosts[hostname].get("hostinfo", {}).get("NetInfo", {}).get("interfaces", {})
            if vlan["interface"] not in interfaces:
                raise OverlapException(
                    f"Interface not available for dtn {hostname} in configuration. \
                                       Available interfaces: {interfaces}"
                )
            vlanRange = interfaces.get(vlan["interface"], {}).get("vlan_range_list", {})
            if vlanRange and vlan["vlan"] not in vlanRange:
                raise OverlapException(
                    f"Vlan {vlan} not available for dtn {hostname} in configuration. \
                                       Either used or not configured. Allowed Vlans: {vlanRange}"
                )
            return
        # If switch, check in Switch config
        rawConf = polcls.config.getraw("MAIN")
        if hostname in rawConf:
            # Get Global vlan range for device
            vlanRange = rawConf.get(hostname, {}).get("vlan_range_list", [])
            if rawConf[hostname].get("ports", {}).get(vlan["interface"], {}).get("realportname", ""):
                # If port is a fake and it points to a real port, we check only fake port vlan range
                vlanRange = rawConf.get(hostname, {}).get("ports", {}).get(vlan["interface"], {}).get("vlan_range_list", vlanRange)
            else:
                portName = polcls.switch.getSwitchPortName(hostname, vlan["interface"])
                # If port has vlan range, use that. Means check is done at the port level.
                vlanRange = rawConf.get(hostname, {}).get("ports", {}).get(portName, {}).get("vlan_range_list", vlanRange)

            if vlanRange and vlan["vlan"] not in vlanRange:
                raise OverlapException(
                    f"Vlan {vlan} not available for switch {hostname} in configuration. \
                                       Either used or not configured. Allowed Vlans: {vlanRange}"
                )
        else:
            raise OverlapException(f"(1) Hostname {hostname} not available in this Frontend.")

    def _checkifIPInRange(self, polcls, ipval, iptype, hostname):
        """Check if IP in Allowed range"""
        if not ipval or not ipval.get(f"{iptype}-address", ""):
            return
        iptoCheck = ipval[f"{iptype}-address"]

        ipRange = polcls.config.getraw("MAIN").get(polcls.sitename, {}).get(f"{iptype}-address-pool-list", [])
        if hostname in polcls.config.getraw("MAIN"):
            ipRange = polcls.config.getraw("MAIN").get(hostname, {}).get(f"{iptype}-address-pool-list", ipRange)
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise OverlapException(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        elif hostname in polcls.hosts:
            interfaces = polcls.hosts[hostname].get("hostinfo", {}).get("NetInfo", {}).get("interfaces", {})
            if ipval["interface"] not in interfaces:
                raise OverlapException(
                    f"Interface not available for dtn {hostname} in configuration. \
                                       Available interfaces: {interfaces}"
                )
            ipRange = interfaces.get(ipval["interface"], {}).get(f"{iptype}-address-pool-list", [])
            if not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise OverlapException(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        else:
            raise OverlapException(f"(2) Hostname {hostname} not available in this Frontend.")

    def _checkIfVlanOverlap(self, vlan1, vlan2):
        """Check if Vlan equal. Raise error if True"""
        v1, v2 = vlan1.get("vlan", None), vlan2.get("vlan", None)
        if not v1 or not v2:
            self.logger.debug(f"Vlan not available for {self.newid} or {self.oldid}. Input: {vlan1}, {vlan2}")
            return
        if v1 == v2:
            raise OverlapException(
                f"New Request VLANs Overlap on same controlled resources. \
                  Vlan {vlan1} already used by {self.oldid}. New Request {self.newid} not allowed"
            )

    def _checkIfIPOverlap(self, ip1, ip2, iptype):
        """Check if IP Overlap. Raise error if True"""
        overlap = self._ipOverlap(ip1, ip2, iptype)
        if overlap:
            raise OverlapException(
                f"New Request {iptype} overlap on same controlled resources. \
                  {iptype} IP {ip1} already used by {self.oldid}. New Request {self.newid} not allowed"
            )

    def _checkIfIPOverlapDevice(self, ip1, ip2, iptype):
        """Check if IP Overlap. Raise error if True"""
        overlap = self._ipOverlap(ip1, ip2, iptype)
        if overlap:
            raise OverlapException(
                f"New Request {iptype} requests duplicate IPs on the same device. \
                  Requested: {ip1} and {ip2} are overlapping. "
            )

    def _checkIfIPRouteAll(self, polcls, ipval, iptype, hostname):
        """Check if IP Range is in allowed configuration"""
        # If switch, check in Switch config
        if not ipval.get(iptype, {}):
            return
        rawConf = polcls.config.getraw("MAIN")
        if hostname not in rawConf:
            raise OverlapException(f"(3) Hostname {hostname} not available in this Frontend.")
        if ipval and ipval.get(iptype, {}).get("nextHop", ""):
            iptoCheck = ipval[iptype]["nextHop"]
            ipRange = rawConf.get(polcls.sitename, {}).get(f"{iptype}-address-pool-list", [])
            if hostname in rawConf:
                ipRange = rawConf.get(hostname, {}).get(f"{iptype}-address-pool-list", ipRange)
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise WrongIPAddress(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        if ipval and ipval.get(iptype, {}).get("routeFrom", ""):
            iptoCheck = ipval[iptype]["routeFrom"]
            ipRange = rawConf.get(polcls.sitename, {}).get(f"{iptype}-subnet-pool-list", [])
            if hostname in rawConf:
                ipRange = rawConf.get(hostname, {}).get(f"{iptype}-subnet-pool-list", ipRange)
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise WrongIPAddress(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )

    @staticmethod
    def _getVlans(dataIn):
        """Get Vlans in request"""
        out = []
        for _, val in dataIn.items():
            for key1, val1 in val.items():
                if key1 == "hasLabel" and "value" in val1:
                    if val1["value"] not in out:
                        out.append(val1["value"])
        return out

    def _getVlanIPs(self, dataIn, bwstats=False):
        """Get Vlan IPs"""
        allIPs = []
        for intf, val in dataIn.items():
            out = {}
            out.setdefault("interface", intf)
            for key1, val1 in val.items():
                if key1 == "hasLabel":
                    out.setdefault("vlan", val1["value"])
                    continue
                if key1 == "hasNetworkAddress" and "ipv6-address" in val1:
                    out.setdefault("ipv6-address", val1["ipv6-address"]["value"])
                if key1 == "hasNetworkAddress" and "ipv4-address" in val1:
                    out.setdefault("ipv4-address", val1["ipv4-address"]["value"])
                if bwstats and key1 == "hasService" and val1.get("type", "") in ["guaranteedCapped", "softCapped", "bestEffort"]:
                    bw, _bwtype = self.convertToRate(val1)
                    out.setdefault("bandwidth", bw)
                # After all checks, we check if it has all required key/values
            if "interface" in out and "vlan" in out:
                allIPs.append(out)
        return allIPs

    def _bwOverlapCalculation(self, hostname, portName, connItems, oldConfig):
        """Calculate overlapping bandwidth used on device port"""
        usedBW = 0
        for svcitem in ["vsw", "singleport", "kube"]:
            for oldID, oldItems in oldConfig.get(svcitem, {}).items():
                # connID == oldID was checked in step3. Skipping it
                if oldID == self.newid:
                    continue
                self.oldid = oldID
                if self._checkIfOverlap(connItems, oldItems):
                    # If 2 items overlap, and have same host for config
                    # Check that vlans and IPs are not overlapping
                    for oldHost, oldHostItems in oldItems.items():
                        if hostname != oldHost:
                            continue
                        for item in self._getVlanIPs(oldHostItems, bwstats=True):
                            if portName != item.get("interface", ""):
                                continue
                            if "bandwidth" in item:
                                usedBW += item["bandwidth"]
                            self.logger.debug(f"Used BW on {hostname} {portName} by {self.oldid}: {item['bandwidth']} Mbps")
        self.logger.info(f"Total used BW on {hostname} {portName}: {usedBW} Mbps")
        return usedBW

    def _checkRemainingBandwidth(self, polcls, hostname, hostitems, connItems, oldConfig):
        """Check Remaining Bandwidth on device ports"""
        allPortIPs = self._getVlanIPs(hostitems, bwstats=True)
        for portIP in allPortIPs:
            # HOST Check
            if hostname in polcls.hosts:
                # Take the maximumCapacity from hostinfo. This is what maximum is allowed
                maxHostBW = polcls.hosts[hostname].get("hostinfo", {}).get("NetInfo", {}).get("interfaces", {}).get(portIP["interface"], {}).get("bwParams", {}).get("maximumCapacity", None)
                if not maxHostBW:
                    continue
                usedBW = self._bwOverlapCalculation(hostname, portIP["interface"], connItems, oldConfig)
                remainingBW = int(maxHostBW) - portIP.get("bandwidth", 0) - usedBW
                self.logger.debug(f"BW on {hostname} {portIP['interface']} after applying new delta. Max: {maxHostBW}, Used: {usedBW}, Remaining: {remainingBW} Mbps")
                if remainingBW < 0:
                    self.logger.error(f"Insufficient bandwidth on {hostname} {portIP['interface']}. Remaining: {remainingBW} Mbps")
                    raise OverlapException(
                        f"Insufficient bandwidth on {hostname} {portIP['interface']}. After all checks, remaining: {remainingBW} Mbps. Max: {maxHostBW} Mbps, Used: {usedBW} Mbps, Requested: {portIP.get('bandwidth', 0)} Mbps"
                    )
            # SWITCH Check
            elif portData := polcls.switch.getSwitchPort(hostname, portIP["interface"]):
                if "bandwidth" not in portData:
                    continue
                remainingBW = int(portData["bandwidth"]) - portIP.get("bandwidth", 0)
                usedBW = self._bwOverlapCalculation(hostname, portIP["interface"], connItems, oldConfig)
                remainingBW -= usedBW
                self.logger.debug(f"BW on {hostname} {portIP['interface']} after applying new delta. Max: {portData['bandwidth']}, Used: {usedBW}, Remaining: {remainingBW} Mbps")
                if remainingBW < 0:
                    msg = f"Insufficient bandwidth on {hostname} {portIP['interface']}. After all checks, remaining BW: {portData.get('bandwidth', 0)-usedBW} Mbps; After applying delta: {remainingBW} Mbps; Max available: {portData.get('bandwidth', 0)} Mbps; Used: {usedBW} Mbps; Requested: {portIP.get('bandwidth', 0)} Mbps"
                    self.logger.error(msg)
                    raise OverlapException(msg)
            # Unknown Host/Switch/Device
            else:
                self.logger.error(f"Hostname {hostname} not found in hosts or switches.")

    @staticmethod
    def _getRSTIPs(dataIn):
        """Get All IPs from RST definition"""
        out = {}
        for key in ["ipv4", "ipv6"]:
            for _route, routeItems in dataIn.get(key, {}).get("hasRoute", {}).items():
                nextHop = routeItems.get("nextHop", {}).get(f"{key}-address", {}).get("value", None)
                if nextHop:
                    out.setdefault(key, {})
                    out[key]["nextHop"] = nextHop
                routeFrom = routeItems.get("routeFrom", {}).get(f"{key}-prefix-list", {}).get("value", None)
                if routeFrom:
                    out.setdefault(key, {})
                    out[key]["routeFrom"] = routeFrom
                routeTo = routeItems.get("routeTo", {}).get(f"{key}-prefix-list", {}).get("value", None)
                if routeTo:
                    out.setdefault(key, {})
                    out[key]["routeTo"] = routeTo
        return out

    @staticmethod
    def _overlap_count(times1, times2):
        """Calculate the overlap in seconds between two time ranges"""
        latestStart = max(times1.start, times2.start)
        earliestEnd = min(times1.end, times2.end)

        delta = (earliestEnd - latestStart).total_seconds()
        return max(0, delta)

    def _checkIfOverlap(self, newitem, oldItem):
        """Check if 2 deltas overlap for timing"""
        dates1 = self.getTimeRanges(newitem)
        dates2 = self.getTimeRanges(oldItem)
        if self._overlap_count(dates1, dates2):
            return True
        return False

    def checkEnd(self, connItems, oldItems):
        """Check if end date is in past"""
        # Olditems is empty for new delta
        if oldItems:
            if self.getTimeRanges(connItems) == self.getTimeRanges(oldItems):
                # If timings did not change, we continue as normal
                return
        if self.checkIfEnded(connItems):
            self.logger.debug(f"End date is in past for {self.newid}")
            self.logger.debug(f"Connection Items: {connItems}")
            raise OverlapException(f"End date is in past for {self.newid}. Cannot modify or add new resources.")

    def _checkIPOverlaps(self, nStats, connItems, hostname, oldConfig):
        """Check if IP Overlaps"""
        for svcitem in ["vsw", "singleport", "kube"]:
            for oldID, oldItems in oldConfig.get(svcitem, {}).items():
                # connID == oldID was checked in step3. Skipping it
                if oldID == self.newid:
                    continue
                self.oldid = oldID
                # Check if 2 items overlap
                if self._checkIfOverlap(connItems, oldItems):
                    # If 2 items overlap, and have same host for config
                    # Check that vlans and IPs are not overlapping
                    for oldHost, oldHostItems in oldItems.items():
                        if hostname != oldHost:
                            continue
                        for item in self._getVlanIPs(oldHostItems):
                            self._checkIfVlanOverlap(nStats, item)
                            self._checkIfIPOverlap(
                                nStats.get("ipv6-address", ""),
                                item.get("ipv6-address", ""),
                                "ipv6",
                            )
                            self._checkIfIPOverlap(
                                nStats.get("ipv4-address", ""),
                                item.get("ipv4-address", ""),
                                "ipv4",
                            )

    @staticmethod
    def _checkSystemIPOverlap(nStats, hostname, oldConfig):
        """Check if overlaps with any IP set on the system"""
        for iptype in ["ipv4", "ipv6"]:
            ipaddr = nStats.get(f"{iptype}-address", "")
            if ipaddr in oldConfig.get("usedIPs", {}).get("deltas", {}).get(hostname, {}).get(iptype, []):
                continue
            if ipaddr in oldConfig.get("usedIPs", {}).get("system", {}).get(hostname, {}).get(iptype, []):
                raise OverlapException(
                    f"IP {ipaddr} is already in use on the system (manually set \
                                        or remains from undeleted request). Cannot proceed with this request."
                )

    def _isModify(self, oldConfig, connItems, newDelta):
        """Check if it is modify or new"""
        # If Connection ID in oldConfig - it is either == or it is a modify call.
        retstate = ""
        if self.newid in oldConfig.get(self.checkmethod, {}):
            diff = DeepDiff(oldConfig[self.checkmethod][self.newid], connItems, ignore_order=True)
            if diff:
                self.logger.debug("=" * 50)
                self.logger.debug("MODIFY!!!")
                self.logger.debug(oldConfig[self.checkmethod][self.newid])
                self.logger.debug(connItems)
                self.logger.debug("=" * 50)
                self.logger.info(f"Diff for {self.newid}:")
                self.logger.info(pprint(diff))
                retstate = "modified"
            if oldConfig[self.checkmethod][self.newid] == connItems:
                # No Changes - connID is same, ignoring it
                retstate = "unchanged"
                return retstate
            if newDelta:
                self.checkEnd(connItems, oldConfig[self.checkmethod][self.newid])
        elif newDelta:
            # This is new delta and not available in oldConfig. Check that it is not in past
            self.checkEnd(connItems, {})
            retstate = "new"
        return retstate

    def __printSummary(self, idstatetrack):
        """Print Summary of id state track"""
        self.logger.info(f"Summary of {self.checkmethod} instances:")
        for key, vals in idstatetrack.items():
            self.logger.info(f"{key}: {vals}")

    @staticmethod
    def _checkIsAlias(polcls, hostname, hostitems):
        """Check if isAlias match what is inside the configuration"""
        for intf, vals in hostitems.items():
            if "isAlias" in vals and vals["isAlias"]:
                # If isAlias is set, check if it is in the configuration
                realPortName = polcls.switch.getSwitchPortName(hostname, intf)
                if realPortName in polcls.config.getraw("MAIN").get(hostname, {}).get("ports", {}):
                    confAlias = polcls.config.getraw("MAIN").get(hostname, {}).get("ports", {}).get(realPortName, {}).get("isAlias", None)
                    if confAlias and not vals["isAlias"].startswith(confAlias):
                        raise OverlapException(
                            f"Alias mismatch for {hostname} on {intf}. \
                                                Config: {confAlias}, Request: {vals['isAlias']}"
                        )

    def _checkDuplicateIPs(self, nStats):
        """Check if duplicate IPs in request overlap"""
        if not nStats:
            return
        if len(nStats) < 2:
            return
        ips = {"ipv4": [], "ipv6": []}
        for item in nStats:
            if item.get("ipv4-address", ""):
                ips["ipv4"].append(item["ipv4-address"])
            if item.get("ipv6-address", ""):
                ips["ipv6"].append(item["ipv6-address"])
        # Check for overlaps in the collected IPs
        for iptype, iplist in ips.items():
            if len(iplist) > 1:
                pairs = list(itertools.combinations(iplist, 2))
                for ip1, ip2 in pairs:
                    self._checkIfIPOverlapDevice(ip1, ip2, iptype)

    def checkvsw(self, cls, svcitems, oldConfig, newDelta=False):
        """Check vsw Service"""
        idstatetrack = {"modified": [], "new": [], "deleted": [], "unchanged": []}
        for connID, connItems in svcitems.items():
            if connID == "_params":
                continue
            self.newid = connID
            retstate = self._isModify(oldConfig, connItems, newDelta)
            if retstate == "unchanged":
                idstatetrack.setdefault(retstate, []).append(connID)
                continue
            if retstate:
                idstatetrack.setdefault(retstate, {}).append(connID)
            for hostname, hostitems in connItems.items():
                if hostname == "_params":
                    continue
                nStats = self._getVlanIPs(hostitems)
                self._checkDuplicateIPs(nStats)
                for item in nStats:
                    if newDelta:
                        self._checkSystemIPOverlap(item, hostname, oldConfig)
                    # Check if vlan is in allowed list;
                    self._checkVlanInRange(cls, item, hostname)
                    # check if ip address with-in available ranges
                    self._checkifIPInRange(cls, item, "ipv4", hostname)
                    self._checkifIPInRange(cls, item, "ipv6", hostname)
                    self._checkIPOverlaps(item, connItems, hostname, oldConfig)
                # Check if host updated frontend in the last 5minutes
                if newDelta:
                    self._checkIfHostAlive(cls, hostname)
                    self._checkVlanSwapping(self._getVlans(hostitems), hostname)
                    self._checkIsAlias(cls, hostname, hostitems)
                    # Check if remaining BW is > 0
                    self._checkRemainingBandwidth(cls, hostname, hostitems, connItems, oldConfig)
        for oldID in oldConfig.get(self.checkmethod, {}).keys():
            if oldID not in svcitems:
                idstatetrack.setdefault("deleted", {}).append(oldID)
        self.__printSummary(idstatetrack)
        if not newDelta:
            return
        # In case of deleted, check if host is alive
        for connID in idstatetrack["deleted"]:
            for hostname, hostitems in oldConfig[self.checkmethod][connID].items():
                if hostname == "_params":
                    continue
                self._checkIfHostAlive(cls, hostname)

    def _checkRSTIPOverlap(self, nIPs, oIPs, iptype):
        """Check if routes overlap on diff requests"""

        def _rstoverlapwrapper(key, iptype):
            """Check if IP Ranges overlap and catch Exception.
            True if fail. False if not."""
            try:
                self._checkIfIPOverlap(nIPs.get(key, None), oIPs.get(key, None), iptype)
            except OverlapException:
                return True
            return False

        overlaps = []
        overlaps.append(_rstoverlapwrapper("routeFrom", iptype))
        overlaps.append(_rstoverlapwrapper("routeTo", iptype))
        if all(overlaps):
            raise OverlapException(
                f"New Request {iptype} overlap on same controlled resources. \
                                   Overlap resources: {self.newid} and {self.oldid}"
            )

    def _comparewithOldConfig(self, nStats, connItems, hostname, oldConfig):
        """Compare new config with old config"""
        for oldID, oldItems in oldConfig.get(self.checkmethod, {}).items():
            # connID == oldID was checked in step3. Skipping it
            self.oldid = oldID
            if oldID == self.newid:
                continue
            # Check if 2 items overlap
            if self._checkIfOverlap(connItems, oldItems):
                # If 2 items overlap, and have same host for config
                # Check that vlans and IPs are not overlapping
                if oldItems.get(hostname, {}):
                    oStats = self._getRSTIPs(oldItems[hostname])
                    for key in ["ipv4", "ipv6"]:
                        self._checkIfIPOverlap(
                            nStats.get(key, {}).get("nextHop", ""),
                            oStats.get(key, {}).get("nextHop", ""),
                            key,
                        )
                        self._checkRSTIPOverlap(nStats.get(key, {}), oStats.get(key, {}), key)

    def checkrst(self, cls, rstitems, oldConfig, newDelta=False):
        """Check rst Service"""
        idstatetrack = {"modified": [], "new": [], "deleted": [], "unchanged": []}
        for connID, connItems in rstitems.items():
            if connID == "_params":
                continue
            self.newid = connID
            retstate = self._isModify(oldConfig, connItems, newDelta)
            if retstate == "unchanged":
                idstatetrack.setdefault(retstate, {}).append(connID)
                continue
            if retstate:
                idstatetrack.setdefault(retstate, {}).append(connID)
            for hostname, hostitems in connItems.items():
                if hostname == "_params":
                    continue
                nStats = self._getRSTIPs(hostitems)
                # Check if vlan is in allowed list;
                self._checkVlanInRange(cls, nStats, hostname)
                # check if ip address with-in available ranges
                self._checkifIPInRange(cls, nStats, "ipv4", hostname)
                self._checkifIPInRange(cls, nStats, "ipv6", hostname)
                self._checkIfIPRouteAll(cls, nStats, "ipv6", hostname)
                self._checkIfIPRouteAll(cls, nStats, "ipv4", hostname)
                self._comparewithOldConfig(nStats, connItems, hostname, oldConfig)
        self.__printSummary(idstatetrack)

    def checkConflicts(self, cls, newConfig, oldConfig, newDelta=False):
        """Check conflicting resources and not allow them"""
        if newConfig == oldConfig:
            return False
        for dkey, ditems in newConfig.items():
            self.checkmethod = dkey
            if dkey in ["vsw", "singleport", "kube"]:
                self.checkvsw(cls, ditems, oldConfig, newDelta)
            elif dkey == "rst":
                self.checkrst(cls, ditems, oldConfig, newDelta)
        return False

    def checkActiveConfig(self, activeConfig):
        """Check all Active Config"""
        newconf = copy.deepcopy(activeConfig)
        cleaned = []
        # VSW, Kube and SinglePort Cleanup
        for key in ["vsw", "kube", "singleport"]:
            for subnet, subnetdict in activeConfig.get(key, {}).items():
                if self._ended(subnetdict):
                    cleaned.append(subnet)
                    newconf[key].pop(subnet, None)
                    for host in subnetdict.keys():
                        if newconf.get("SubnetMapping", {}).get(host, {}).get("providesSubnet", {}).get(subnet, None):
                            newconf["SubnetMapping"][host]["providesSubnet"].pop(subnet, None)
        # RST Cleanup
        for rkey, rval in {
            "providesRoute": "RoutingMapping",
            "providesRoutingTable": "RoutingMapping",
        }.items():
            for host, pRoutes in activeConfig.get(rval, {}).items():
                for route, rdict in pRoutes.get(rkey, {}).items():
                    for iptype in rdict.keys():
                        if self._ended(activeConfig.get("rst", {}).get(route, {}).get(host, {}).get(iptype, {})):
                            cleaned.append(route)
                            newconf[rval][host][rkey].pop(route, None)
                            newconf["rst"].pop(route, None)
        return newconf, cleaned
