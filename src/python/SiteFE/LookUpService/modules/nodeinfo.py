#!/usr/bin/env python3
"""
    Add Node Information to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
# TODO: interface and vlan IP address set in correct way (same as switches do)
# TODO: vlans bidirectional on node? or only on Interface? I suspect only interface

import configparser
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.FECalls import getAllHosts

def ignoreInterface(intfKey, intfDict):
    """Check if ignore interface for putting it inside model."""
    returnMsg = False
    if intfKey.endswith('-ifb'):
        returnMsg = True
    elif 'switch' not in list(intfDict.keys()):
        returnMsg = True
    elif 'switch_port' not in list(intfDict.keys()):
        returnMsg = True
    return returnMsg


class NodeInfo():
    """ Module for Node Info add to MRML """
    # pylint: disable=E1101,W0201

    def addNodeInfo(self):
        jOut = getAllHosts(self.sitename, self.logger)
        for _, nodeDict in list(jOut.items()):
            nodeDict['hostinfo'] = evaldict(nodeDict['hostinfo'])
            # ==================================================================================
            # General Node Information
            # ==================================================================================
            self.defineNodeInformation(nodeDict)
            # ==================================================================================
            # Define Host Information and all it's interfaces.
            # ==================================================================================
            self.defineHostInfo(nodeDict, nodeDict['hostinfo'])
            # ==================================================================================
            # Define Routing Service information
            # ==================================================================================
            self.defineLayer3MRML(nodeDict, nodeDict['hostinfo'])

    def defineNodeInformation(self, nodeDict):
        """Define node information."""
        self.hosts[nodeDict['hostname']] = []
        hosturi = self._addNode(hostname=nodeDict['hostname'])
        # Node General description

        self._nmlLiteral(hosturi, 'hostname', nodeDict['hostname'])
        self._nmlLiteral(hosturi, 'insertdate', nodeDict['insertdate'])
        # Provide location information about site Frontend
        try:
            self._nmlLiteral(hosturi, 'latitude', self.config.get(self.sitename, 'latitude'))
            self._nmlLiteral(hosturi, 'longitude', self.config.get(self.sitename, 'longitude'))
        except configparser.NoOptionError:
            self.logger.debug('Either one or both (latitude,longitude) are not defined. Continuing as normal')

    def addIntfInfo(self, inputDict, prefixuri, main=True):
        """This will add all information about specific interface."""
        # '2' is for ipv4 information
        # Also can be added bytes_received, bytes_sent, dropin, dropout
        # errin, errout, packets_recv, packets_sent
        # But adding such values means we will always get a new model once
        # a single packet get's transferred
        mappings = {}
        if main:
            mappings = {'2': ['address', 'MTU', 'UP', 'broadcast', 'txqueuelen',
                              'duplex', 'netmask', 'speed', 'ipv4-address', 'ipv6-address'],
                        '10': ['address', 'broadcast', 'netmask'],
                        '17': ['address', 'broadcast', 'netmask', 'mac-address']}
        else:
            mappings = {'2': ['address', 'MTU', 'UP', 'broadcast', 'duplex',
                              'netmask', 'speed', 'txqueuelen', 'ipv4-address', 'ipv6-address'],
                        '10': ['address', 'broadcast', 'netmask'],
                        '17': ['address', 'broadcast', 'netmask']}
        for dKey, dMappings in list(mappings.items()):
            for mapping in dMappings:
                if dKey not in list(inputDict.keys()):
                    continue
                if mapping in list(inputDict[dKey].keys()) and inputDict[dKey][mapping]:
                    mName = mapping
                    value = inputDict[dKey][mapping]
                    if dKey == '10':
                        mName = 'ipv6-%s' % mapping
                    if dKey == '17' and mapping == 'address':
                        mName = 'mac-%s' % mapping
                    elif dKey == '17':
                        mName = 't17-%s' % mapping
                    if dKey == '2' and mapping == 'address':
                        mName = 'ipv4-address-system'
                        value = inputDict[dKey][mapping].split('/')[0]
                    self._addNetworkAddress(prefixuri, mName, value)

    def defineLayer3MRML(self, nodeDict, hostinfo):
        """Define Layer 3 Routing Service for hostname"""
        def __validMRMLName(valIn):
            return valIn.replace(':', '_').replace('/', '-').replace('.', '_').replace(' ', '_')

        for route in hostinfo.get('NetInfo', {}).get('routes', []):
            if 'RTA_DST' in route.keys() and route['RTA_DST'] == '169.254.0.0':
                # The 169.254.0.0/16 network is used for Automatic Private IP Addressing, or APIPA.
                # We do not need this information inside the routed template
                continue
            out = {'hostname': hostinfo['hostname'],
                   'rstname': 'rst-%s' % route['iptype'],
                   'iptype': route['iptype']}
            for tablegress in['table+defaultIngress', 'table+defaultEgress']:
                out['rt-table'] = tablegress
                if 'RTA_GATEWAY' in list(route.keys()):
                    out['routename'] = 'default'
                    out['routetype'] = 'routeTo'
                    out['type'] = '%s-address' % route['iptype']
                    out['value'] = route['RTA_GATEWAY']
                    self._addRouteEntry(**out)
                    # Do we really need this?
                    #for vals in [['to', 'ipv4-prefix-list', '0.0.0.0/0'],
                    #             ['black-hole', 'routing-policy', 'drop'],
                    #             ['local', 'routing-policy', 'local']]:
                    #    self._addNetworkAddress('%s:%s' % (routename, vals[0]), [vals[0], vals[1]], vals[2])
                elif 'RTA_PREFSRC'  in route.keys() and 'dst_len' in route.keys():
                    out['routename'] = __validMRMLName("%s_%s" % (route['RTA_PREFSRC'], route['dst_len']))
                    out['routetype'] = 'routeTo'
                    out['type'] = '%s-prefix-list' % route['iptype']
                    out['value'] = "%s_%s" % (route['RTA_PREFSRC'], route['dst_len'])
                    self._addRouteEntry(**out)
                    # nextHop to default route? Is it needed?

    def addAgentConfigtoMRML(self, intfDict, newuri, hostname, intf):
        """Agent Configuration params to Model."""
        # Add floating ip pool list for interface from the agent
        # ==========================================================================================
        if 'ipv4-floatingip-pool' in list(intfDict.keys()):
            self._addNetworkAddress(newuri, 'ipv4-floatingip-pool', str(intfDict["ipv4-floatingip-pool"]))

        # Add is Alias - So that it has link to Switch.
        # We could use LLDP Info In future.
        self._addIsAlias(newuri, {'isAlias': "%s:%s:%s" % (self.prefixes['site'],
                                                           intfDict['switch'],
                                                           intfDict['switch_port'])})

        # BANDWIDTH Service for INTERFACE
        # ==========================================================================================
        bws = self._addBandwidthService(hostname=hostname, portName=intf)

        for item in [['unit', 'unit', "mbps"],
                     ['max_bandwidth', 'maximumCapacity', 10000000000],
                     ['available_bandwidth', 'availableCapacity', 10000000000],
                     ['granularity', 'granularity', 1000000],
                     ['reservable_bandwidth', 'reservableCapacity', 10000000000],
                     ['min_bandwidth', 'minReservableCapacity', 10000000000]]:
            value = item[2]
            if item[0] in list(intfDict.keys()):
                value = intfDict[item[0]]
            try:
                value = int((int(value) // 1000000))
            except ValueError:
                value = str(value)
            self._mrsLiteral(bws, item[1], value)
            # ==========================================================================================
        if 'capacity' in list(intfDict.keys()):
            self._mrsLiteral(bws, 'capacity', intfDict['capacity'])
        if 'vlan_range' in list(intfDict.keys()):
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('nml', 'hasLabelGroup'),
                               self.genUriRef('site', "%s:vlan-range" % newuri)))

            self.newGraph.add((self.genUriRef('site', "%s:vlan-range" % newuri),
                               self.genUriRef('rdf', 'type'),
                               self.genUriRef('nml', 'LabelGroup')))

            self.newGraph.add((self.genUriRef('site', "%s:vlan-range" % newuri),
                               self.genUriRef('nml', 'labeltype'),
                               self.genUriRef('schema', '#vlan')))
            self._nmlLiteral("%s:vlan-range" % newuri, 'values', intfDict['vlan_range'])

        self.shared = 'notshared'
        if 'shared' in intfDict:
            if intfDict['shared']:
                self.shared = 'shared'
            self._mrsLiteral(newuri, 'type', self.shared)

    def defineHostInfo(self, nodeDict, hostinfo):
        """Define Host information inside MRML.
        Add All interfaces info.
        """
        for intfKey, intfDict in list(hostinfo['NetInfo']["interfaces"].items()):
            # We exclude QoS interfaces from adding them to MRML.
            # Even so, I still want to have this inside DB for debugging purposes
            if ignoreInterface(intfKey, intfDict):
                continue
            self.hosts[nodeDict['hostname']].append({'switchName': intfDict['switch'],
                                                     'switchPort': intfDict['switch_port'],
                                                     'intfKey': intfKey})

            newuri = self._addRstPort(hostname=nodeDict['hostname'], portName=intfKey)
            # Create new host definition
            # =====================================================================
            # Add most of the agent configuration to MRML
            # =====================================================================
            self.addAgentConfigtoMRML(intfDict, newuri, nodeDict['hostname'], intfKey)
            # Now lets also list all interface information to MRML
            self.addIntfInfo(intfDict, newuri)
            # List each VLAN:
            if 'vlans' in list(intfDict.keys()):
                for vlanName, vlanDict in list(intfDict['vlans'].items()):
                    # We exclude QoS interfaces from adding them to MRML.
                    # Even so, I still want to have this inside DB for debugging purposes
                    if vlanName.endswith('-ifb'):
                        continue
                    if not isinstance(vlanDict, dict):
                        continue
                    # '2' is for ipv4 information
                    vlanName = vlanName.split('.')
                    vlanuri = self._addVlanPort(hostname=nodeDict['hostname'], portName=intfKey, vlan=vlanName[1])
                    self._addRstPort(hostname=nodeDict['hostname'], portName=intfKey, vlan=vlanName[1])
                    self._mrsLiteral(vlanuri, 'type', self.shared)

                    if 'vlanid' in list(vlanDict.keys()):
                        self.newGraph.add((self.genUriRef('site', vlanuri),
                                           self.genUriRef('nml', 'hasLabel'),
                                           self.genUriRef('site', "%s:vlan" % vlanuri)))
                        self.newGraph.add((self.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.genUriRef('rdf', 'type'),
                                           self.genUriRef('nml', 'Label')))
                        self.newGraph.add((self.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.genUriRef('nml', 'labeltype'),
                                           self.genUriRef('schema', '#vlan')))
                        self.newGraph.add((self.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.genUriRef('nml', 'value'),
                                           self.genLiteral(vlanDict['vlanid'])))
                    # Add hasNetworkAddress for vlan
                    # Now the mapping of the interface information:
                    self.addIntfInfo(vlanDict, vlanuri, False)
