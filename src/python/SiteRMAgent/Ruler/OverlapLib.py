#!/usr/bin/env python3
"""Overlap Libraries to check network IP Overlaps from delta with OS IPs

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/08/29
"""
from SiteRMLibs.ipaddr import (
    checkoverlap,
    getInterfaceIP,
    getMasterSlaveInterfaces,
    getNetmaskBits,
    getsubnet,
)


class OverlapLib:
    """OverLap Lib - checks and prepares configs for overlap calculations"""

    # pylint: disable=E1101
    def __init__(self):
        self.allIPs = {"ipv4": {}, "ipv6": {}}
        self.totalrequests = {}
        self.getAllIPs()

    def __getAllIPsHost(self):
        """Get All IPs on the system"""
        for intf, masterIntf in getMasterSlaveInterfaces().items():
            for intType, intDict in getInterfaceIP(intf).items():
                if int(intType) == 2:
                    for ipv4 in intDict:
                        address = f"{ipv4.get('addr')}/{ipv4.get('netmask')}"
                        self.allIPs["ipv4"].setdefault(address, [])
                        self.allIPs["ipv4"][address].append(
                            {"intf": intf, "master": masterIntf if masterIntf else intf}
                        )
                elif int(intType) == 10:
                    for ipv6 in intDict:
                        address = (
                            f"{ipv6.get('addr')}/{ipv6.get('netmask').split('/')[1]}"
                        )
                        self.allIPs["ipv6"].setdefault(address, [])
                        self.allIPs["ipv6"][address].append(
                            {"intf": intf, "master": masterIntf if masterIntf else intf}
                        )

    def __getAllIPsNetNS(self):
        """Mapping for Private NS comes from Agent configuration"""
        if not self.config.has_section("qos"):
            return
        if not self.config.has_option("qos", "interfaces"):
            return
        for intf, params in self.config.get("qos", "interfaces").items():
            for key in ["ipv6", "ipv4"]:
                iprange = params.get(f"{key}_range")
                if isinstance(iprange, list):
                    for ipval in iprange:
                        self.allIPs[key].setdefault(ipval, [])
                        self.allIPs[key][ipval].append(
                            {"master": params["master_intf"], "intf": intf}
                        )
                elif iprange:
                    self.allIPs[key].setdefault(iprange, [])
                    self.allIPs[key][iprange].append(
                        {"master": params["master_intf"], "intf": intf}
                    )

    @staticmethod
    def _getNetmaskBit(ipinput):
        """Get Netmask Bits"""
        return getNetmaskBits(ipinput)

    def getAllIPs(self):
        """Get all IPs"""
        self.allIPs = {"ipv4": {}, "ipv6": {}}
        self.__getAllIPsHost()
        self.__getAllIPsNetNS()

    @staticmethod
    def networkOverlap(net1, net2):
        """Check if 2 networks overlap"""
        try:
            net1Net = getsubnet(net1, strict=False)
            net2Net = getsubnet(net2, strict=False)
            if checkoverlap(net1Net, net2Net):
                return True
        except ValueError:
            pass
        return False

    def findOverlaps(self, iprange, iptype):
        """Find all networks which overlap and add it to service list"""
        for ipPresent in self.allIPs.get(iptype, []):
            if self.networkOverlap(iprange, ipPresent):
                return ipPresent.split("/")[0], self.allIPs[iptype][ipPresent]
        return None, None

    @staticmethod
    def mergeBWDicts(d1, d2):
        int_keys = [
            "availableCapacity",
            "granularity",
            "maximumCapacity",
            "priority",
            "reservableCapacity",
        ]
        for key in int_keys:
            d1[key] = d1.get(key, 0) + d2.get(key, 0)
        return d1

    def getAllOverlaps(self, activeDeltas):
        """Get all overlaps"""
        self.getAllIPs()
        self.totalrequests = {}
        overlapServices = {}
        for _key, vals in activeDeltas.get("output", {}).get("rst", {}).items():
            for _, ipDict in vals.items():
                for iptype, routes in ipDict.items():
                    if "hasService" not in routes:
                        continue
                    uri = routes["hasService"]["uri"]
                    for _, routeInfo in routes.get("hasRoute").items():
                        iprange = (
                            routeInfo.get("routeFrom", {})
                            .get(f"{iptype}-prefix-list", {})
                            .get("value", None)
                        )
                        ipVal, intfArray = self.findOverlaps(iprange, iptype)
                        if ipVal and intfArray:
                            for intfName in intfArray:
                                service = overlapServices.setdefault(
                                    intfName["intf"], {}
                                )
                                intServ = service.setdefault(
                                    uri,
                                    {
                                        "src_ipv4": "",
                                        "src_ipv4_intf": "",
                                        "src_ipv6": "",
                                        "src_ipv6_intf": "",
                                        "dst_ipv4": "",
                                        "dst_ipv6": "",
                                        "master_intf": "",
                                        "rules": "",
                                    },
                                )
                                intServ[f"src_{iptype}"] = ipVal
                                intServ[f"src_{iptype}_intf"] = intfName["intf"]
                                intServ["master_intf"] = intfName["master"]
                                resvRate, _ = self.convertToRate(routes["hasService"])
                                self.totalrequests.setdefault(intfName["master"], 0)
                                self.totalrequests[intfName["master"]] += resvRate
                                # Add dest IPs to overlap info
                                iprange = (
                                    routeInfo.get("routeTo", {})
                                    .get(f"{iptype}-prefix-list", {})
                                    .get("value", None)
                                )
                                intServ[f"dst_{iptype}"] = iprange
                                if intServ["rules"]:
                                    intServ["rules"] = self.mergeBWDicts(
                                        intServ["rules"], routes["hasService"]
                                    )
                                else:
                                    intServ["rules"] = routes["hasService"]
        return overlapServices
