#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Routing Service (BGP Control) preparation/comparison
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
UpdateDate              : 2022/05/09
"""

import traceback

from SiteRMLibs.ipaddr import normalizedip
from SiteRMLibs.MainUtilities import generateMD5


def dictCompare(inDict, oldDict):
    """Compare dict and set any remaining items
    from current ansible yaml as absent in new one if
    it's status is present.
    Return True if there is a difference, False if not"""
    # If equal - return
    eqval = False
    if inDict == oldDict:
        return eqval
    for key, val in oldDict.items():
        if isinstance(val, dict):
            eqval = dictCompare(inDict.setdefault(key, {}), val)
            if not inDict[key]:
                # if it is empty after back from loop, delete
                del inDict[key]
            # If val has state and it is absent, delete inDictKey also
            if "state" in val and val["state"] == "absent":
                # Means everything already below is absent
                del inDict[key]
            continue
        if val == "present" and key not in inDict.keys():
            # Means current state is present, but model does not know anything
            inDict[key] = "absent"
            eqval = True
        elif val not in ["present", "absent"]:
            # Ensure we pre-keep all other keys
            inDict[key] = val
    return eqval


class RoutingService:
    """Routing Service Class. Adds all activeDelta params,
    compares with running active config, make things absent if they
    are not existing anymore"""

    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    @staticmethod
    def generateGroupName(activeInfo, line):
        """Generate group name for BGP"""
        # In case all the rest parameters are empty, we set DEFAULT group name;
        if all(not activeInfo.get(k) for k in ("ipv6_network", "neighbor", "prefix_list", "route_map")):
            # This should never reach, but just in case not to delete any provisioned ones.
            return "DEFAULT"
        try:
            groupName = line.split("table+")[1].split(":")[0]
            return groupName
        except Exception as ex:
            print(f"Full traceback: {traceback.format_exc()}")
            raise Exception(f"Error while generating group name: {ex}") from ex

    def _getDefaultBGP(self, host, emptydict=False):
        """Default yaml dict setup"""
        if emptydict:
            tmpD = {}
        else:
            tmpD = self.yamlconfuuid.setdefault(self.acttype, {}).setdefault(self.connID, {})
            tmpD = tmpD.setdefault(host, {})
            tmpD = tmpD.setdefault("sense_bgp", {})
        tmpD["asn"] = self.getConfigValue(host, "private_asn")
        tmpD["belongsTo"] = self.connID
        if not tmpD["asn"]:
            del tmpD["asn"]
        tmpD["vrf"] = self.getConfigValue(host, "vrf")
        if not tmpD["vrf"]:
            del tmpD["vrf"]
        if tmpD:
            tmpD["state"] = "present"
        return tmpD

    def _addOwnRoutes(self, host, rDict):
        """Add Routes"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ["ipv4", "ipv6"]:
            val = rDict.get("routeFrom", {}).get(f"{iptype}-prefix-list", {}).get("value", None)
            if val and not isinstance(val, list):
                val = [val]
            if val:
                for v in val:
                    v = normalizedip(v)
                    bgpdict.setdefault(f"{iptype}_network", {})
                    bgpdict[f"{iptype}_network"][v] = "present"

    def _addNeighbors(self, host, ruid, rDict):
        """Add Neighbors"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ["ipv4", "ipv6"]:
            remasn = rDict.get("routeTo", {}).get("bgp-private-asn", {}).get("value", None)
            remip = rDict.get("nextHop", {}).get(f"{iptype}-address", {}).get("value", None)
            if remasn and remip:
                remip = normalizedip(remip)
                neighbor = bgpdict.setdefault("neighbor", {}).setdefault(iptype, {}).setdefault(remip, {})
                if neighbor:
                    raise Exception("Neighbor already defined. MultiPath neighbors not supported")
                neighbor.setdefault("remote_asn", remasn)
                neighbor.setdefault("state", "present")
                neighbor.setdefault(
                    "route_map",
                    {
                        "in": {f"sense-{ruid}-mapin": "present"},
                        "out": {f"sense-{ruid}-mapout": "present"},
                    },
                )

    def _addPrefixList(self, host, ruid, rDict):
        """Add Prefix Lists"""
        bgpdict = self._getDefaultBGP(host)
        keymaps = [["routeFrom", "mapout"], ["routeTo", "mapin"]]
        for iptype in ["ipv4", "ipv6"]:
            for routeFromTo, mapdir in keymaps:
                rList = rDict.get(routeFromTo, {}).get(f"{iptype}-prefix-list", {}).get("value", None)
                if rList and not isinstance(rList, list):
                    rList = [rList]
                if rList:
                    for r in rList:
                        prefList = bgpdict.setdefault("prefix_list", {}).setdefault(iptype, {})
                        newRoute = prefList.setdefault(r, {})
                        newRoute[f"sense-{ruid}-{mapdir}"] = "present"
                        self._addRouteMap(
                            host,
                            f"sense-{ruid}-{mapdir}",
                            f"sense-{ruid}-{mapdir}",
                            iptype,
                        )

    def _addRouteMap(self, host, match, name, iptype):
        """Add Route Maps"""
        permitst = 10
        bgpdict = self._getDefaultBGP(host)
        if name and match:
            routeMap = bgpdict.setdefault("route_map", {}).setdefault(iptype, {})
            permitst += len(routeMap.get(name, {}))
            routeMap.setdefault(name, {}).setdefault(int(permitst), {match: "present"})

    def _addparamsrst(self, connDict, switches):
        """Wrapper for add params, to put individual request info too inside dictionary"""
        for host, hostDict in connDict.items():
            if host not in switches:
                continue
            self._getDefaultBGP(host)
            for _, rFullDict in hostDict.items():
                if not self.checkIfStarted(rFullDict):
                    continue
                for rtag, rDict in rFullDict.get("hasRoute", {}).items():
                    ruid = generateMD5(rtag)
                    self._getDefaultBGP(host)
                    self._addOwnRoutes(host, rDict)
                    self._addNeighbors(host, ruid, rDict)
                    self._addPrefixList(host, ruid, rDict)

    def addrst(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for rst)"""
        if self.acttype in activeConfig:
            for connID, connDict in activeConfig[self.acttype].items():
                self.connID = connID
                self._addparamsrst(connDict, switches)
                if self.firstrun and connID not in self.forceapply:
                    self.logger.debug(f"First run, will force apply {self.acttype} for {connID}.")
                    self.forceapply.append(connID)

    def compareBGP(self, switch, runningConf, uuid):
        """Compare L3 BGP"""
        # If runningConf is empty, then it is different
        if not runningConf:
            self.logger.debug(f"Running config for {uuid} is empty. Return True")
            return True
        tmpD = self.yamlconfuuid.setdefault(self.acttype, {}).setdefault(uuid, {}).setdefault(switch, {})
        tmpD = tmpD.setdefault("sense_bgp", {})
        # If equal - return no difference
        if tmpD == runningConf:
            self.logger.debug(f"Running conf and new conf are equals for {uuid}. Return False")
            return False
        different = False
        for key, val in runningConf.items():
            # ipv6_network, ipv4_network, neighbor, prefix_list, route_map
            if not val:
                continue
            if key in [
                "ipv6_network",
                "ipv4_network",
                "prefix_list",
                "route_map",
                "neighbor",
            ]:
                yamlOut = tmpD.setdefault(key, {})
                equal = dictCompare(yamlOut, val)
                if equal:
                    self.logger.debug(f"There is {key} change for {uuid}. Will return True")
                    different = True
            else:
                tmpD[key] = val
        # Compare empty dict with prepared new conf:
        if self._getDefaultBGP(switch, True) == tmpD:
            self.logger.debug(f"Def BGP and new BGP is empty for {uuid}. Will return False")
            different = False
        # In case of new - keys not equal, need to write
        if tmpD.keys() != runningConf.keys():
            self.logger.debug(f"Keys for new BGP are not equal for {uuid}. Will return True")
            different = True
        return different
