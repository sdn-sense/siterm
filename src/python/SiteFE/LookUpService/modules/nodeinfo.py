#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    Add Node Information to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.MainUtilities import getAllHosts, strtolist, getFileContentAsJson


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

    def __recordHostUsedVlans(self, nodeDict):
        """Record all host used vlans"""
        # Record used vlans
        for _intfKey, intfDict in list(nodeDict.get('hostinfo', {}).get("NetInfo", {}).get("interfaces", {}).items()):
            if "vlans" in intfDict and intfDict["vlans"]:
                for _vlanName, vlanDict in list(intfDict["vlans"].items()):
                    vlanid = vlanDict.get("vlanid", None)
                    if vlanid is None:
                        continue
                    self.usedVlans['system'].setdefault(nodeDict['hostname'], [])
                    if vlanid not in self.usedVlans['system'][nodeDict['hostname']]:
                        self.usedVlans['system'][nodeDict['hostname']].append(vlanid)

    def addNodeInfo(self):
        """Add Agent Node Information"""
        jOut = getAllHosts(self.dbI)
        for _nodeHostname, nodeDict in list(jOut.items()):
            nodeDict["hostinfo"] = getFileContentAsJson(nodeDict["hostinfo"])
            # ==================================================================================
            # Record used vlans
            # ==================================================================================
            self.__recordHostUsedVlans(nodeDict)
            # ==================================================================================
            # General Node Information
            # ==================================================================================
            self.defineNodeInformation(nodeDict)
            # ==================================================================================
            # Define Host Information and all it's interfaces.
            # ==================================================================================
            self.defineHostInfo(nodeDict, nodeDict["hostinfo"])

    def addIntfInfo(self, hostname, inputDict, prefixuri):
        """This will add all information about specific interface."""
        # We limit what to add, and right now add only mac-address
        # If there will be need in future to add more, we can extend it;
        for item in inputDict.get('17', []):
            if 'mac-address' not in item:
                continue
            if item['mac-address']:
                self._addNetworkAddress(prefixuri, 'mac-address', item['mac-address'])
        # Add mtu and txqueuelen
        for item in inputDict.get('2', []):
            if 'MTU' in item:
                self._addHasNetworkAttribute(prefixuri, 'MTU', 'mtu', item['MTU'])
            if 'txqueuelen' in item:
                self._addHasNetworkAttribute(prefixuri, 'txqueuelen', 'txqueuelen', item['txqueuelen'])
            if item.get('ipv4-address'):
                splt = item['ipv4-address'].split('/')
                if len(splt) == 2:
                    # Record IP Address as used
                    self.recordSystemIPs(hostname, 'ipv4', [{'address': splt[0], 'masklen': splt[1]}])
        for item in inputDict.get('10', []):
            if item.get('ipv6-address'):
                splt = item['ipv6-address'].split('/')
                if len(splt) == 2:
                    self.recordSystemIPs(hostname, 'ipv6', [{'address': splt[0], 'masklen': splt[1]}])

    def defineNodeInformation(self, nodeDict):
        """Define node information."""
        self.hosts[nodeDict["hostname"]] = []
        hosturi = self._addNode(hostname=nodeDict["hostname"])
        # Add Node metadata information
        self._addNodeMetadata(hostname=nodeDict["hostname"], nodeDict=nodeDict)

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

    def addMonName(self, intfKey, uri):
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
        # ==========================================================================================
        if "isAlias" in intfDict:
            isAlias = intfDict["isAlias"].lstrip(":")
            if not isAlias.startswith('urn:ogf:network'):
                isAlias = f"urn:ogf:network:{isAlias}"
            self._addIsAlias(uri=newuri, isAlias=isAlias)
        else:
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
            vlanRange = self.filterOutAvailbVlans(hostname, intfDict['vlan_range_list'])
            self._nmlLiteral(
                f"{newuri}:vlan-range",
                "values",
                ",".join(map(str, vlanRange)),
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
            self.addIntfInfo(nodeDict["hostname"], intfDict, newuri)
            self.addMonName(intfKey, newuri)
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
                    if 'vlan_range_list' in intfDict and intfDict["vlan_range_list"]:
                        if vlanDict["vlanid"] not in intfDict["vlan_range_list"]:
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

                    self.newGraph.add((
                            self.genUriRef("site", vlanuri),
                            self.genUriRef("nml", "hasLabel"),
                            self.genUriRef("site", f"{vlanuri}:label+{vlanDict['vlanid']}"),))
                    self.newGraph.add((
                            self.genUriRef("site", f"{vlanuri}:label+{vlanDict['vlanid']}"),
                            self.genUriRef("rdf", "type"),
                            self.genUriRef("nml", "Label"),))
                    self.newGraph.add((
                            self.genUriRef("site", f"{vlanuri}:label+{vlanDict['vlanid']}"),
                            self.genUriRef("nml", "labeltype"),
                            self.genUriRef("schema", "#vlan"),))
                    self.newGraph.set((
                            self.genUriRef("site", f"{vlanuri}:label+{vlanDict['vlanid']}"),
                            self.genUriRef("nml", "value"),
                            self.genLiteral(str(vlanDict["vlanid"])),))
                    # Add hasNetworkAddress for vlan
                    self.addIntfInfo(nodeDict["hostname"], vlanDict, vlanuri)
                    # Now the mapping of the interface information:
                    self.addMonName(vlanName, vlanuri)
