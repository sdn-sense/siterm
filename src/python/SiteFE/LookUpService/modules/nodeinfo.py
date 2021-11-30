import configparser
from DTNRMLibs.MainUtilities import evaldict

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

    def defineNodeInformation(self, nodeDict):
        """Define node information."""
        self.hosts[nodeDict['hostname']] = []
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('nml', 'hasNode'),
                           self.genUriRef('site', ":%s" % nodeDict['hostname'])))
        # Node General description
        self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.genUriRef('nml', 'name'),
                           self.genLiteral(nodeDict['hostname'])))
        self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Node')))
        self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.genUriRef('nml', 'insertTime'),
                           self.genLiteral(nodeDict['insertdate'])))
        # Provide location information about site Frontend
        try:
            self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.genUriRef('nml', 'latitude'),
                               self.genLiteral(self.config.get(self.sitename, 'latitude'))))
            self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.genUriRef('nml', 'longitude'),
                               self.genLiteral(self.config.get(self.sitename, 'longitude'))))
        except configparser.NoOptionError:
            self.logger.debug('Either one or both (latitude,longitude) are not defined. Continuing as normal')

    def addIntfInfo(self, inputDict, prefixuri, main=True):
        """This will add all information about specific interface."""
        # '2' is for ipv4 information
        # Also can be added bytes_received, bytes_sent, dropin, dropout
        # errin, errout, packets_recv, packets_sent
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
                    self.addToGraph(['site', prefixuri],
                                    ['mrs', 'hasNetworkAddress'],
                                    ['site', '%s:%s' % (prefixuri, mName)])
                    self.addToGraph(['site', '%s:%s' % (prefixuri, mName)],
                                    ['rdf', 'type'],
                                    ['mrs', 'NetworkAddress'])
                    self.addToGraph(['site', "%s:%s" % (prefixuri, mName)],
                                    ['mrs', 'type'],
                                    [mName])
                    self.addToGraph(['site', "%s:%s" % (prefixuri, mName)],
                                    ['mrs', 'value'],
                                    [value])

    def defineLayer3MRML(self, nodeDict):
        """Define Layer 3 Routing Service for hostname"""
        hostinfo = evaldict(nodeDict['hostinfo'])
        self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', ':%s:service+rst' % nodeDict['hostname'])))
        self.newGraph.add((self.genUriRef('site', ':%s:service+rst' % nodeDict['hostname']),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingService')))
        # Service Definition for L3
        self.newGraph.add((self.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname'])))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname']),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname']),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/l3-vpn')))

        for tablegress in['table+defaultIngress', 'table+defaultEgress']:
            routingtable = ":%s:%s" % (nodeDict['hostname'], tablegress)
            self.newGraph.add((self.genUriRef('site', ':%s:service+rst' % nodeDict['hostname']),
                               self.genUriRef('mrs', 'providesRoutingTable'),
                               self.genUriRef('site', routingtable)))
            self.newGraph.add((self.genUriRef('site', routingtable),
                               self.genUriRef('rdf', 'type'),
                               self.genUriRef('mrs', 'RoutingTable')))
            for routeinfo in hostinfo['NetInfo']["routes"]:
                routename = ""
                if 'RTA_DST' in list(routeinfo.keys()) and routeinfo['RTA_DST'] == '169.254.0.0':
                    # The 169.254.0.0/16 network is used for Automatic Private IP Addressing, or APIPA.
                    # We do not need this information inside the routed template
                    continue
                if 'RTA_GATEWAY' in list(routeinfo.keys()):
                    routename = routingtable + ":route+default"
                else:
                    # Ignore unreachable routes from preparing inside the model
                    if 'RTA_PREFSRC' not in list(routeinfo.keys()):
                        continue
                    routename = routingtable + ":route+%s_%s" % (routeinfo['RTA_PREFSRC'], routeinfo['dst_len'])
                self.newGraph.add((self.genUriRef('site', routename),
                                   self.genUriRef('rdf', 'type'),
                                   self.genUriRef('mrs', 'Route')))
                self.newGraph.add((self.genUriRef('site', routingtable),
                                   self.genUriRef('mrs', 'hasRoute'),
                                   self.genUriRef('site', routename)))
                if 'RTA_GATEWAY' in list(routeinfo.keys()):
                    self.newGraph.add((self.genUriRef('site', routename),
                                       self.genUriRef('mrs', 'routeTo'),
                                       self.genUriRef('site', '%s:%s' % (routename, 'to'))))
                    self.newGraph.add((self.genUriRef('site', routename),
                                       self.genUriRef('mrs', 'nextHop'),
                                       self.genUriRef('site', '%s:%s' % (routename, 'black-hole'))))
                    for vals in [['to', 'ipv4-prefix-list', '0.0.0.0/0'],
                                 ['black-hole', 'routing-policy', 'drop'],
                                 ['local', 'routing-policy', 'local']]:
                        self.addToGraph(['site', '%s:%s' % (routename, vals[0])],
                                        ['rdf', 'type'],
                                        ['mrs', 'NetworkAddress'])
                        self.addToGraph(['site', '%s:%s' % (routename, vals[0])],
                                        ['mrs', 'type'],
                                        [vals[1]])
                        self.addToGraph(['site', '%s:%s' % (routename, vals[0])],
                                        ['mrs', 'value'],
                                        [vals[2]])
                else:
                    defaultroutename = routingtable + ":route+default:local"
                    self.newGraph.add((self.genUriRef('site', routename),
                                       self.genUriRef('mrs', 'routeTo'),
                                       self.genUriRef('site', '%s:%s' % (routename, 'to'))))
                    self.newGraph.add((self.genUriRef('site', routename),
                                       self.genUriRef('mrs', 'nextHop'),
                                       self.genUriRef('site', defaultroutename)))
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['rdf', 'type'],
                                    ['mrs', 'NetworkAddress'])
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['mrs', 'type'],
                                    ['ipv4-prefix-list'])
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['mrs', 'value'],
                                    ['%s/%s' % (routeinfo['RTA_DST'], routeinfo['dst_len'])])

    def addAgentConfigtoMRML(self, intfDict, newuri):
        """Agent Configuration params to Model."""
        switchName = intfDict['switch']
        switchPort = intfDict['switch_port']
        # Add floating ip pool list for interface from the agent
        # ==========================================================================================
        if 'ipv4-floatingip-pool' in list(intfDict.keys()):
            self.addToGraph(['site', newuri],
                            ['mrs', 'hasNetworkAddress'],
                            ['site', "%s:%s" % (newuri, 'ipv4-floatingip-pool')])
            self.addToGraph(['site', "%s:%s" % (newuri, 'ipv4-floatingip-pool')],
                            ['rdf', 'type'],
                            ['mrs', 'NetworkAddress'])
            self.addToGraph(['site', "%s:%s" % (newuri, 'ipv4-floatingip-pool')],
                            ['mrs', 'type'],
                            ["ipv4-floatingip-pool"])
            self.addToGraph(['site', "%s:%s" % (newuri, 'ipv4-floatingip-pool')],
                            ['mrs', 'value'],
                            [str(intfDict["ipv4-floatingip-pool"])])
        # Add vlan range for interface from the agent
        # ==========================================================================================
        if 'vlan_range' in list(intfDict.keys()):
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('nml', 'hasService'),
                               self.genUriRef('site', "%s:%s" % (newuri, 'bandwidthService'))))
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('nml', 'isAlias'),
                               self.genUriRef('site', ":%s:%s:+" % (switchName, switchPort))))
            # BANDWIDTH Service for INTERFACE
            # ==========================================================================================
            bws = "%s:%s" % (newuri, 'bandwidthService')
            self.newGraph.add((self.genUriRef('site', bws),
                               self.genUriRef('rdf', 'type'),
                               self.genUriRef('mrs', 'BandwidthService')))
            self.newGraph.add((self.genUriRef('site', bws),
                               self.genUriRef('mrs', 'type'),
                               self.genLiteral('guaranteedCapped')))

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
                self.newGraph.add((self.genUriRef('site', bws),
                                   self.genUriRef('mrs', item[1]),
                                   self.genLiteral(value)))
            # ==========================================================================================
        if 'capacity' in list(intfDict.keys()):
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('mrs', 'capacity'),
                               self.genLiteral(intfDict['capacity'])))
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
            self.newGraph.add((self.genUriRef('site', "%s:vlan-range" % newuri),
                               self.genUriRef('nml', 'values'),
                               self.genLiteral(intfDict['vlan_range'])))
        self.shared = False
        if 'shared' in list(intfDict.keys()):
            self.shared = 'notshared'
            if intfDict['shared']:
                self.shared = 'shared'
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('mrs', 'type'),
                               self.genLiteral(self.shared)))

    def defineHostInfo(self, nodeDict):
        """Define Host information inside MRML.

        Add All interfaces info.
        """
        hostinfo = evaldict(nodeDict['hostinfo'])
        for intfKey, intfDict in list(hostinfo['NetInfo']["interfaces"].items()):
            # We exclude QoS interfaces from adding them to MRML.
            # Even so, I still want to have this inside DB for debugging purposes
            if ignoreInterface(intfKey, intfDict):
                continue
            switchName = intfDict['switch']
            switchPort = intfDict['switch_port']
            self.hosts[nodeDict['hostname']].append({'switchName': switchName,
                                                     'switchPort': switchPort,
                                                     'intfKey': intfKey})
            newuri = ":%s:%s:%s:%s" % (switchName, switchPort, nodeDict['hostname'], intfKey)
            # Create new host definition
            self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', newuri)))
            self.newGraph.add((self.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', newuri)))
            # Specific node information.
            self.newGraph.add((self.genUriRef('site', newuri),
                               self.genUriRef('rdf', 'type'),
                               self.genUriRef('nml', 'BidirectionalPort')))
            # =====================================================================
            # Add most of the agent configuration to MRML
            # =====================================================================
            self.addAgentConfigtoMRML(intfDict, newuri)
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
                    vlanuri = ":%s:%s:%s:%s:vlanport+%s" % (switchName, switchPort,
                                                            nodeDict['hostname'], intfKey, vlanName[1])
                    self.newGraph.add((self.genUriRef('site', vlanuri),
                                       self.genUriRef('rdf', 'type'),
                                       self.genUriRef('nml', 'BidirectionalPort')))
                    self.newGraph.add((self.genUriRef('site', newuri),
                                       self.genUriRef('nml', 'hasService'),
                                       self.genUriRef('site', "%s:%s" % (newuri, 'bandwidthService'))))
                    if self.shared:
                        self.newGraph.add((self.genUriRef('site', vlanuri),
                                           self.genUriRef('mrs', 'type'),
                                           self.genLiteral(self.shared)))
                    self.newGraph.add((self.genUriRef('site', ":%s" % nodeDict['hostname']),
                                       self.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.genUriRef('site', vlanuri)))
                    self.newGraph.add((self.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                                       self.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.genUriRef('site', vlanuri)))
                    self.newGraph.add((self.genUriRef('site', newuri),
                                       self.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.genUriRef('site', vlanuri)))
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
