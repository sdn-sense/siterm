#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    Add Node Information to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.ipaddr import validMRMLName
from SiteRMLibs.MainUtilities import evaldict, getAllHosts, strtolist


def ignoreInterface(intfKey, intfDict, hostinfo):
    """
    Check if ignore interface for putting it inside model.
    If ends with -ifb - means interface is for QoS, ignoring
    If int dict does not have switch/switch_port defined - ignored
    """
    returnMsg = False
    if intfKey.endswith("-ifb"):
        returnMsg = True
    elif "switch" not in list(intfDict.keys()):
        returnMsg = True
    elif "switch_port" not in list(intfDict.keys()):
        returnMsg = True
    if intfKey not in hostinfo.get("Summary", {}).get("config", {}).get(
        "agent", {}
    ).get("interfaces", []):
        returnMsg = True
    return returnMsg


class NodeInfo:
    """Module for Node Info add to MRML"""

    # pylint: disable=E1101,W0201

    @staticmethod
    def __getRstsEnabled(hostinfo):
        """Get RSTS Enabled from Agent Config"""
        rstsEnabled = (
            hostinfo.get("Summary", {})
            .get("config", {})
            .get("agent", {})
            .get("rsts_enabled", [])
        )
        return strtolist(rstsEnabled, ",")

    def addNodeInfo(self):
        """Add Agent Node Information"""
        jOut = getAllHosts(self.dbI)
        for _, nodeDict in list(jOut.items()):
            nodeDict["hostinfo"] = evaldict(nodeDict["hostinfo"])
            # ==================================================================================
            # General Node Information
            # ==================================================================================
            self.defineNodeInformation(nodeDict)
            # ==================================================================================
            # Define Host Information and all it's interfaces.
            # ==================================================================================
            self.defineHostInfo(nodeDict, nodeDict["hostinfo"])
            # ==================================================================================
            # Define Routing Service information
            # ==================================================================================
            self.defineLayer3MRML(nodeDict, nodeDict["hostinfo"])

    def defineNodeInformation(self, nodeDict):
        """Define node information."""
        self.hosts[nodeDict["hostname"]] = []
        hosturi = self._addNode(hostname=nodeDict["hostname"])
        # Node General description

        self._nmlLiteral(hosturi, "hostname", nodeDict["hostname"])
        self._nmlLiteral(hosturi, "insertdate", nodeDict["insertdate"])
        # Provide location information about site Frontend
        try:
            self._nmlLiteral(
                hosturi, "latitude", self.config.get(self.sitename, "latitude")
            )
            self._nmlLiteral(
                hosturi, "longitude", self.config.get(self.sitename, "longitude")
            )
        except NoOptionError:
            self.logger.debug(
                "Either one or both (latitude,longitude) are not defined. Continuing as normal"
            )

    def addMonName(self, nodeDict, intfKey, uri, main=True):
        """Add Mon name to model for SENSE RT Monitoring mapping"""
        self.addToGraph(
            ["site", uri],
            ["mrs", "hasNetworkAddress"],
            ["site", f"{uri}:sense-rtmon+realportname"],
        )
        self.addToGraph(
            ["site", f"{uri}:sense-rtmon+realportname"],
            ["rdf", "type"],
            ["mrs", "NetworkAddress"],
        )
        self.addToGraph(
            ["site", f"{uri}:sense-rtmon+realportname"],
            ["mrs", "type"],
            ["sense-rtmon:name"],
        )
        self.setToGraph(
            ["site", f"{uri}:sense-rtmon+realportname"], ["mrs", "value"], [intfKey]
        )

    def _defL3IPv6(self, hostname, route):
        """Define L3 IPv6 Routing information inside the model for host"""
        out = {
            "hostname": hostname,
            "rstname": f"rst-{route['iptype']}",
            "iptype": route["iptype"],
        }
        for tablegress in ["table+defaultIngress", "table+defaultEgress"]:
            out["rt-table"] = tablegress
            if "RTA_GATEWAY" in list(route.keys()):
                out["routename"] = "default"
                out["routetype"] = "routeTo"
                out["type"] = f"{route['iptype']}-address"
                out["value"] = route["RTA_GATEWAY"]
                self._addRouteEntry(**out)
            elif "RTA_DST" in route.keys() and "dst_len" in route.keys():
                out["routename"] = validMRMLName(
                    f"{route['RTA_DST']}/{route['dst_len']}"
                )
                out["routetype"] = "routeTo"
                out["type"] = f"{route['iptype']}-prefix-list"
                out["value"] = f"{route['RTA_DST']}/{route['dst_len']}"
                self._addRouteEntry(**out)

    def _defL3IPv4(self, hostname, route):
        """Define L3 IPv4 Routing information inside the model for host"""
        if "RTA_DST" in route.keys() and route["RTA_DST"] == "169.254.0.0":
            # The 169.254.0.0/16 network is used for Automatic Private IP Addressing, or APIPA.
            # We do not need this information inside the routed template
            return

        out = {
            "hostname": hostname,
            "rstname": f"rst-{route['iptype']}",
            "iptype": route["iptype"],
        }
        for tablegress in ["table+defaultIngress", "table+defaultEgress"]:
            out["rt-table"] = tablegress
            if "RTA_GATEWAY" in list(route.keys()):
                out["routename"] = "default"
                out["routetype"] = "routeTo"
                out["type"] = f"{route['iptype']}-address"
                out["value"] = route["RTA_GATEWAY"]
                self._addRouteEntry(**out)
            elif "RTA_PREFSRC" in route.keys() and "dst_len" in route.keys():
                out["routename"] = validMRMLName(
                    f"{route['RTA_PREFSRC']}/{route['dst_len']}"
                )
                out["routetype"] = "routeTo"
                out["type"] = f"{route['iptype']}-prefix-list"
                out["value"] = f"{route['RTA_PREFSRC']}/{route['dst_len']}"
                self._addRouteEntry(**out)
                # nextHop to default route? Is it needed?

    def defineLayer3MRML(self, nodeDict, hostinfo):
        """Define Layer 3 Routing Service for hostname"""
        del nodeDict
        rstsEnabled = self.__getRstsEnabled(hostinfo)
        for route in hostinfo.get("NetInfo", {}).get("routes", []):
            if route.get("iptype") in rstsEnabled:
                if route.get("iptype") == "ipv4":
                    self._defL3IPv4(hostinfo["hostname"], route)
                elif route.get("iptype") == "ipv6":
                    self._defL3IPv6(hostinfo["hostname"], route)

    def addAgentConfigtoMRML(self, intfDict, newuri, hostname, intf):
        """Agent Configuration params to Model."""
        # Add floating ip pool list for interface from the agent
        # ==========================================================================================
        for key in [
            "ipv4-address-pool-list",
            "ipv4-subnet-pool-list",
            "ipv6-address-pool-list",
            "ipv6-subnet-pool-list",
        ]:
            if key in list(intfDict.keys()):
                self._addNetworkAddress(
                    newuri, key[:-5], ",".join(map(str, intfDict[key]))
                )

        # Add is Alias - So that it has link to Switch.
        # We could use LLDP Info In future.
        self._addIsAlias(
            uri=newuri,
            isAlias=f"{self.prefixes['site']}:{intfDict['switch']}:{intfDict['switch_port']}",
        )

        # BANDWIDTH Service for INTERFACE
        # ==========================================================================================
        if 'bwParams' in intfDict and intfDict['bwParams']:
            bws = self._addBandwidthService(hostname=hostname, portName=intf)
            intfDict['bwParams']['bwuri'] = bws
            self._addBandwidthServiceParams(**intfDict['bwParams'])
            # ==========================================================================================
        if "capacity" in list(intfDict.keys()):
            self._mrsLiteral(bws, "capacity", intfDict["capacity"])
        if "vlan_range_list" in list(intfDict.keys()):
            self.newGraph.add(
                (self.genUriRef("site", newuri),
                 self.genUriRef("nml", "hasLabelGroup"),
                self.genUriRef("site", f"{newuri}:vlan-range"),
                ))

            self.newGraph.add(
                (self.genUriRef("site", f"{newuri}:vlan-range"),
                 self.genUriRef("rdf", "type"),
                 self.genUriRef("nml", "LabelGroup"),
                ))

            self.newGraph.add(
                (self.genUriRef("site", f"{newuri}:vlan-range"),
                 self.genUriRef("nml", "labeltype"),
                 self.genUriRef("schema", "#vlan"),
                ))
            self._nmlLiteral(
                f"{newuri}:vlan-range",
                "values",
                ",".join(map(str, intfDict["vlan_range_list"])),
            )

        self.shared = "notshared"
        if "shared" in intfDict and intfDict["shared"]:
            self.shared = "shared"
        self._mrsLiteral(newuri, "type", self.shared)

    def defineHostInfo(self, nodeDict, hostinfo):
        """Define Host information inside MRML.
        Add All interfaces info.
        """
        rstsEnabled = self.__getRstsEnabled(hostinfo)
        for intfKey, intfDict in list(
            hostinfo.get("NetInfo", {}).get("interfaces", {}).items()
        ):
            # We exclude QoS interfaces from adding them to MRML.
            # Even so, I still want to have this inside DB for debugging purposes
            if ignoreInterface(intfKey, intfDict, hostinfo):
                continue
            self.hosts[nodeDict["hostname"]].append(
                {
                    "switchName": intfDict["switch"],
                    "switchPort": intfDict["switch_port"],
                    "intfKey": intfKey,
                }
            )

            newuri = self._addRstPort(
                hostname=nodeDict["hostname"],
                portName=intfKey,
                parent=intfDict.get("parent", False),
                nodetype="server",
                rsts_enabled=rstsEnabled,
            )
            # Create new host definition
            # =====================================================================
            # Add most of the agent configuration to MRML
            # =====================================================================
            self.addAgentConfigtoMRML(intfDict, newuri, nodeDict["hostname"], intfKey)
            # Now lets also list all interface information to MRML
            self.addMonName(nodeDict, intfKey, newuri, True)
            # List each VLAN:
            if "vlans" in list(intfDict.keys()):
                for vlanName, vlanDict in list(intfDict["vlans"].items()):
                    # We exclude QoS interfaces from adding them to MRML.
                    # Even so, I still want to have this inside DB for debugging purposes
                    if vlanName.endswith("-ifb"):
                        continue
                    if not isinstance(vlanDict, dict):
                        continue
                    if "vlanid" not in vlanDict:
                        continue
                    vlanuri = self._addVlanPort(
                        hostname=nodeDict["hostname"],
                        portName=intfKey,
                        vtype="vlanport",
                        vlan=vlanDict["vlanid"],
                    )
                    self._addRstPort(
                        hostname=nodeDict["hostname"],
                        portName=intfKey,
                        vtype="vlanport",
                        vlan=vlanDict["vlanid"],
                        nodetype="server",
                        rsts_enabled=rstsEnabled,
                    )
                    self._mrsLiteral(vlanuri, "type", self.shared)

                    self.newGraph.add(
                        (
                            self.genUriRef("site", vlanuri),
                            self.genUriRef("nml", "hasLabel"),
                            self.genUriRef("site", f"{vlanuri}:vlan"),
                        )
                    )
                    self.newGraph.add(
                        (
                            self.genUriRef("site", f"{vlanuri}:vlan"),
                            self.genUriRef("rdf", "type"),
                            self.genUriRef("nml", "Label"),
                        )
                    )
                    self.newGraph.add(
                        (
                            self.genUriRef("site", f"{vlanuri}:vlan"),
                            self.genUriRef("nml", "labeltype"),
                            self.genUriRef("schema", "#vlan"),
                        )
                    )
                    self.newGraph.set(
                        (
                            self.genUriRef("site", f"{vlanuri}:vlan"),
                            self.genUriRef("nml", "value"),
                            self.genLiteral(str(vlanDict["vlanid"])),
                        )
                    )
                    # Add hasNetworkAddress for vlan
                    # Now the mapping of the interface information:
                    self.addMonName(nodeDict, vlanName, vlanuri, False)
