#!/usr/bin/env python3
"""Check for conflicting deltas

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import copy

from SiteRMLibs.CustomExceptions import OverlapException, WrongIPAddress
from SiteRMLibs.ipaddr import checkOverlap as incheckOverlap
from SiteRMLibs.ipaddr import ipOverlap as inipOverlap
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.timing import Timing


class ConflictChecker(Timing):
    """Conflict Checker"""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="PolicyService")
        self.newid = ""
        self.oldid = ""
        self.logger.info("Conflict Checker initialized")

    @staticmethod
    def checkOverlap(inrange, ipval, iptype):
        """Check if overlap"""
        return incheckOverlap(inrange, ipval, iptype)

    @staticmethod
    def _ipOverlap(ip1, ip2, iptype):
        """Check if IP Overlap. Return True/False"""
        return inipOverlap(ip1, ip2, iptype)

    @staticmethod
    def _checkVlanInRange(polcls, vlan, hostname):
        """Check if VLAN in Allowed range"""
        if not vlan or not vlan.get("vlan", "") or not vlan.get("interface", ""):
            return
        # If Agent, check in agent reported configuration
        if hostname in polcls.hosts:
            interfaces = (polcls.hosts[hostname]
                          .get("hostinfo", {})
                          .get("NetInfo", {})
                          .get("interfaces", {}))
            if vlan["interface"] not in interfaces:
                raise OverlapException(f"Interface not available for dtn {hostname} in configuration. \
                                       Available interfaces: {interfaces}")
            vlanRange = interfaces.get(vlan["interface"], {}).get("vlan_range_list", {})
            if vlanRange and vlan["vlan"] not in vlanRange:
                raise OverlapException(f"Vlan {vlan} not available for dtn {hostname} in configuration. \
                                       Either used or not configured. Allowed Vlans: {vlanRange}")
            return
        # If switch, check in Switch config
        rawConf = polcls.config.getraw("MAIN")
        if hostname in rawConf:
            # Get Global vlan range for device
            vlanRange = rawConf.get(hostname, {}).get("vlan_range_list", [])
            portName = polcls.switch.getSwitchPortName(hostname, vlan['interface'])
            # If port has vlan range, use that. Means check is done at the port level.
            vlanRange = rawConf.get(hostname, {}).get('ports', {})\
                               .get(portName , {}).get("vlan_range_list", vlanRange)
            if vlanRange and vlan["vlan"] not in vlanRange:
                raise OverlapException(f"Vlan {vlan} not available for switch {hostname} in configuration. \
                                       Either used or not configured. Allowed Vlans: {vlanRange}")
        else:
            raise OverlapException(f"(1) Hostname {hostname} not available in this Frontend.")

    def _checkifIPInRange(self, polcls, ipval, iptype, hostname):
        """Check if IP in Allowed range"""
        if not ipval or not ipval.get(f"{iptype}-address", ""):
            return
        iptoCheck = ipval[f"{iptype}-address"]

        ipRange = (
            polcls.config.getraw("MAIN")
            .get(polcls.sitename, {})
            .get(f"{iptype}-address-pool-list", [])
        )
        if hostname in polcls.config.getraw("MAIN"):
            ipRange = (
                polcls.config.getraw("MAIN")
                .get(hostname, {})
                .get(f"{iptype}-address-pool-list", ipRange)
            )
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise OverlapException(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        elif hostname in polcls.hosts:
            interfaces = (
                polcls.hosts[hostname]
                .get("hostinfo", {})
                .get("NetInfo", {})
                .get("interfaces", {})
            )
            if ipval["interface"] not in interfaces:
                raise OverlapException(
                    f"Interface not available for dtn {hostname} in configuration. \
                                       Available interfaces: {interfaces}"
                )
            ipRange = interfaces.get(ipval["interface"], {}).get(
                f"{iptype}-address-pool-list", []
            )
            if not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise OverlapException(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        else:
            raise OverlapException(
                f"(2) Hostname {hostname} not available in this Frontend."
            )

    def _checkIfVlanOverlap(self, vlan1, vlan2):
        """Check if Vlan equal. Raise error if True"""
        v1, v2 = vlan1.get('vlan', None), vlan2.get('vlan', None)
        int1, int2 = vlan1.get('interface', None), vlan2.get('interface', None)
        if not v1 or not v2:
            return
        if not int1 or not int2:
            return
        if int1 != int2:
            return
        if v1 == v2:
            raise OverlapException(
                f"New Request VLANs Overlap on same controlled resources. \
                                   Overlap resources: {self.newid} and {self.oldid}"
            )

    def _checkIfIPOverlap(self, ip1, ip2, iptype):
        """Check if IP Overlap. Raise error if True"""
        overlap = self._ipOverlap(ip1, ip2, iptype)
        if overlap:
            raise OverlapException(
                f"New Request {iptype} overlap on same controlled resources. \
                                   Overlap resources: {self.newid} and {self.oldid}"
            )

    def _checkIfIPRouteAll(self, polcls, ipval, iptype, hostname):
        """Check if IP Range is in allowed configuration"""
        # If switch, check in Switch config
        if not ipval.get(iptype, {}):
            return
        rawConf = polcls.config.getraw("MAIN")
        if hostname not in rawConf:
            raise OverlapException(
                f"(3) Hostname {hostname} not available in this Frontend."
            )
        if ipval and ipval.get(iptype, {}).get("nextHop", ""):
            iptoCheck = ipval[iptype]["nextHop"]
            ipRange = rawConf.get(polcls.sitename, {}).get(
                f"{iptype}-address-pool-list", []
            )
            if hostname in rawConf:
                ipRange = rawConf.get(hostname, {}).get(
                    f"{iptype}-address-pool-list", ipRange
                )
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise WrongIPAddress(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )
        if ipval and ipval.get(iptype, {}).get("routeFrom", ""):
            iptoCheck = ipval[iptype]["routeFrom"]
            ipRange = rawConf.get(polcls.sitename, {}).get(
                f"{iptype}-subnet-pool-list", []
            )
            if hostname in rawConf:
                ipRange = rawConf.get(hostname, {}).get(
                    f"{iptype}-subnet-pool-list", ipRange
                )
            if ipRange and not self.checkOverlap(ipRange, iptoCheck, iptype):
                raise WrongIPAddress(
                    f"IP {ipval} not available for {hostname} in configuration. \
                          Either used or not configured. Allowed IPs: {ipRange}"
                )

    @staticmethod
    def _getVlanIPs(dataIn):
        """Get Vlan IPs"""
        out = {}
        for intf, val in dataIn.items():
            out.setdefault("interface", intf)
            for key1, val1 in val.items():
                if key1 == "hasLabel":
                    out.setdefault("vlan", val1["value"])
                    continue
                if key1 == "hasNetworkAddress" and "ipv6-address" in val1:
                    out.setdefault("ipv6-address", val1["ipv6-address"]["value"])
                if key1 == "hasNetworkAddress" and "ipv4-address" in val1:
                    out.setdefault("ipv4-address", val1["ipv4-address"]["value"])
        return out

    @staticmethod
    def _getRSTIPs(dataIn):
        """Get All IPs from RST definition"""
        out = {}
        for key in ["ipv4", "ipv6"]:
            for _route, routeItems in dataIn.get(key, {}).get("hasRoute", {}).items():
                nextHop = (
                    routeItems.get("nextHop", {})
                    .get(f"{key}-address", {})
                    .get("value", None)
                )
                if nextHop:
                    out.setdefault(key, {})
                    out[key]["nextHop"] = nextHop
                routeFrom = (
                    routeItems.get("routeFrom", {})
                    .get(f"{key}-prefix-list", {})
                    .get("value", None)
                )
                if routeFrom:
                    out.setdefault(key, {})
                    out[key]["routeFrom"] = routeFrom
                routeTo = (
                    routeItems.get("routeTo", {})
                    .get(f"{key}-prefix-list", {})
                    .get("value", None)
                )
                if routeTo:
                    out.setdefault(key, {})
                    out[key]["routeTo"] = routeTo
        return out

    @staticmethod
    def _overlap_count(times1, times2):
        """Find out if times overlap."""
        latestStart = max(times1.start, times2.start)
        earliestEnd = min(times1.end, times2.end)
        delta = (earliestEnd - latestStart).seconds
        overlap = max(0, delta)
        if earliestEnd < latestStart:
            overlap = 0
        return overlap

    def _checkIfOverlap(self, newitem, oldItem):
        """Check if 2 deltas overlap for timing"""
        dates1 = self.getTimeRanges(newitem)
        dates2 = self.getTimeRanges(oldItem)
        if self._overlap_count(dates1, dates2):
            return True
        return False

    def checkEnd(self, connItems):
        """Check if end date is in past"""
        if self.checkIfEnded(connItems):
            self.logger.debug(f"End date is in past for {self.newid}")
            self.logger.debug(f"Conneciton Items: {connItems}")
            raise OverlapException(
                f"End date is in past for {self.newid}. Cannot modify or add new resources."
            )

    def checkvsw(self, cls, svc, svcitems, oldConfig, newDelta=False):
        """Check vsw Service"""
        for connID, connItems in svcitems.items():
            if connID == "_params":
                continue
            self.newid = connID
            # If Connection ID in oldConfig - it is either == or it is a modify call.
            if connID in oldConfig.get(svc, {}):
                if oldConfig[svc][connID] != connItems:
                    self.logger.debug("="*50)
                    self.logger.debug("MODIFY!!!")
                    self.logger.debug(oldConfig[svc][connID])
                    self.logger.debug(connItems)
                    self.logger.debug("="*50)
                if oldConfig[svc][connID] == connItems:
                    # No Changes - connID is same, ignoring it
                    continue
            if newDelta:
                self.checkEnd(connItems)
            for hostname, hostitems in connItems.items():
                if hostname == "_params":
                    continue
                nStats = self._getVlanIPs(hostitems)
                # Check if vlan is in allowed list;
                self._checkVlanInRange(cls, nStats, hostname)
                # check if ip address with-in available ranges
                self._checkifIPInRange(cls, nStats, "ipv4", hostname)
                self._checkifIPInRange(cls, nStats, "ipv6", hostname)
                for oldID, oldItems in oldConfig.get(svc, {}).items():
                    # connID == oldID was checked in step3. Skipping it
                    self.oldid = oldID
                    if oldID == connID:
                        continue
                    # Check if 2 items overlap
                    overlap = self._checkIfOverlap(connItems, oldItems)
                    if overlap:
                        # If 2 items overlap, and have same host for config
                        # Check that vlans and IPs are not overlapping
                        for oldHost, oldHostItems in oldItems.items():
                            if hostname != oldHost:
                                continue
                            oStats = self._getVlanIPs(oldHostItems)
                            self._checkIfVlanOverlap(nStats, oStats)
                            self._checkIfIPOverlap(
                                nStats.get("ipv6-address", ""),
                                oStats.get("ipv6-address", ""),
                                "ipv6",
                            )
                            self._checkIfIPOverlap(
                                nStats.get("ipv4-address", ""),
                                oStats.get("ipv4-address", ""),
                                "ipv4",
                            )

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

    def checkrst(self, cls, rst, rstitems, oldConfig, newDelta=False):
        """Check rst Service"""
        for connID, connItems in rstitems.items():
            if connID == "_params":
                continue
            self.newid = connID
            # If Connection ID in oldConfig - it is either == or it is a modify call.
            if connID in oldConfig.get(rst, {}):
                if oldConfig[rst][connID] != connItems:
                    self.logger.debug("="*50)
                    self.logger.debug("MODIFY!!!")
                    self.logger.debug(oldConfig[rst][connID])
                    self.logger.debug(connItems)
                    self.logger.debug("="*50)
                if oldConfig[rst][connID] == connItems:
                    # No Changes - connID is same, ignoring it
                    continue
            if newDelta:
                self.checkEnd(connItems)
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
                for oldID, oldItems in oldConfig.get(rst, {}).items():
                    # connID == oldID was checked in step3. Skipping it
                    self.oldid = oldID
                    if oldID == connID:
                        continue
                    # Check if 2 items overlap
                    overlap = self._checkIfOverlap(connItems, oldItems)
                    if overlap:
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
                                self._checkRSTIPOverlap(
                                    nStats.get(key, {}), oStats.get(key, {}), key
                                )

    def checkConflicts(self, cls, newConfig, oldConfig, newDelta=False):
        """Check conflicting resources and not allow them"""
        if newConfig == oldConfig:
            return False
        for dkey, ditems in newConfig.items():
            if dkey == "vsw":
                self.checkvsw(cls, dkey, ditems, oldConfig, newDelta)
            elif dkey == "rst":
                self.checkrst(cls, dkey, ditems, oldConfig, newDelta)
        return False

    def checkActiveConfig(self, activeConfig):
        """Check all Active Config"""
        newconf = copy.deepcopy(activeConfig)
        cleaned = []
        # VSW Cleanup
        for host, pSubnets in activeConfig.get("SubnetMapping", {}).items():
            for subnet, _ in pSubnets.get("providesSubnet", {}).items():
                if self._ended(activeConfig.get("vsw", {}).get(subnet, {})):
                    cleaned.append(subnet)
                    newconf["SubnetMapping"][host]["providesSubnet"].pop(subnet, None)
                    newconf["vsw"].pop(subnet, None)
        # RST Cleanup
        for rkey, rval in {
            "providesRoute": "RoutingMapping",
            "providesRoutingTable": "RoutingMapping",
        }.items():
            for host, pRoutes in activeConfig.get(rval, {}).items():
                for route, rdict in pRoutes.get(rkey, {}).items():
                    for iptype in rdict.keys():
                        if self._ended(
                            activeConfig.get("rst", {})
                            .get(route, {})
                            .get(host, {})
                            .get(iptype, {})
                        ):
                            cleaned.append(route)
                            newconf[rval][host][rkey].pop(route, None)
                            newconf["rst"].pop(route, None)
        return newconf, cleaned
