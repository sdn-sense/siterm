#!/usr/bin/env python3
# pylint: disable=E1101
"""
    Node information which was received from the agent.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""

from SiteRMLibs.MainUtilities import evaldict, getAllHosts, getFileContentAsJson


class Node:
    """Add Node information from Database which was sent
    by the Agent running on it.
    """

    def nodeinfo(self, output=None):
        """put  all node information from node reported stats."""
        nodesInfo = getAllHosts(self.dbI)
        if not output:
            output = self.output
        for _, nodeDict in list(nodesInfo.items()):
            hostinfo = getFileContentAsJson(nodeDict["hostinfo"])
            for intfKey, intfDict in list(hostinfo.get("NetInfo", {}).get("interfaces", {}).items()):
                breakLoop = False
                for key in [
                    "switch_port",
                    "switch",
                    "vlan_range_list",
                    "available_bandwidth",
                ]:
                    if key not in list(intfDict.keys()):
                        breakLoop = True
                if breakLoop:
                    continue
                if intfDict["switch"] in list(output["ports"].keys()):
                    if intfDict["switch_port"] not in list(output["ports"][intfDict["switch"]].keys()):
                        self.logger.debug(
                            "Frontend Config is not configured to use this Port %s",
                            intfDict["switch_port"],
                        )
                        continue
                    switch = intfDict["switch"]
                    switchp = intfDict["switch_port"]
                    switchDict = self.output["ports"][switch].setdefault(switchp, {})
                    switchDict["destport"] = intfKey
                    switchDict["hostname"] = nodeDict["hostname"]
                    switchDict["vlan_range_list"] = intfDict["vlan_range_list"]
                    switchDict["capacity"] = intfDict["available_bandwidth"]
                    if "isAlias" in list(intfDict.keys()):
                        switchDict["isAlias"] = intfDict["isAlias"]
        if self.config.has_option(self.site, "l3_routing_map"):
            routingMap = self.config.get(self.site, "l3_routing_map")
            output["l3_routing"] = evaldict(routingMap)
        return output
