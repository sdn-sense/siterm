#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    RDF Helper, prefixes, add to model.


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from rdflib import URIRef, Literal
from rdflib.namespace import XSD
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.MainUtilities import strtolist

class RDFHelper():
    """RDF Helper preparation class."""
    # pylint: disable=E1101,W0201,W0613

    def getSavedPrefixes(self, additionalhosts=None):
        """Get Saved prefixes from a configuration file."""
        prefixes = {}
        for key in ['mrs', 'nml', 'owl', 'rdf', 'xml', 'xsd', 'rdfs', 'schema', 'sd']:
            prefixes[key] = self.config.get('prefixes', key)
        prefixSite = (f"{self.config.get('prefixes', 'site')}"
                      f":{self.config.get(self.sitename, 'domain')}"
                      f":{self.config.get(self.sitename, 'year')}")
        prefixes['site'] = prefixSite
        for switchName in self.config.get(self.sitename, 'switch'):
            for key in ['vsw', 'rst']:
                try:
                    tKey = self.config.get(switchName, key)
                    if tKey != switchName:
                        self.logger.debug(f'Config mistake. Hostname != {key} ({switchName} != {tKey})')
                        continue
                    prefixes.setdefault(key, {})
                    prefixes[key][switchName] = f"{prefixes['site']}:{tKey}:service+{key}"
                except NoOptionError:
                    self.logger.debug('ERROR: %s parameter is not defined for %s.', key, switchName)
                    continue
        self.prefixes = prefixes

    def __checkifReqKeysMissing(self, reqKeys, allArgs):
        """Check if key is not missing"""
        for key in reqKeys:
            if key not in allArgs or not allArgs.get(key, None):
                self.logger.debug(f"Key {key} is missing in allArgs: {allArgs}")
                return True
        return False

    def genUriRef(self, prefix=None, add=None, custom=None):
        """Generate URIRef and return."""
        if custom:
            return URIRef(custom)
        if not add:
            return URIRef(f"{self.prefixes[prefix]}")
        if add.startswith(self.prefixes[prefix]):
            return URIRef(f"{add}")
        return URIRef(f"{self.prefixes[prefix]}{add}")

    @staticmethod
    def genLiteral(value, datatype=None):
        """Returns simple Literal RDF out."""
        if datatype:
            return Literal(value, datatype=datatype)
        return Literal(value)

    def _addIsAlias(self, **kwargs):
        """Add isAlias to model"""
        if 'isAlias' in kwargs and kwargs['isAlias'] and \
           'uri' in kwargs and kwargs['uri']:
            self.newGraph.set((self.genUriRef('site', kwargs['uri']),
                               self.genUriRef('nml', 'isAlias'),
                               self.genUriRef('', custom=kwargs['isAlias'])))
            if 'hostname' in kwargs and kwargs['hostname'] and \
               'portName' in kwargs and kwargs['portName']:
                self._addRstPort(**kwargs)

    def setToGraph(self, sub, pred, obj):
        """Set (Means remove old and then add new) to the graph
        Input:
        sub (list) max len 2
        pred (list) max len 2
        obj (list) max len 2 if 1 will use Literal value
        """
        if len(obj) == 1 and len(sub) == 1:
            sub = self.genUriRef(sub[0])
            pred = self.genUriRef(pred[0], pred[1])
            obj = self.genLiteral(obj[0])
        elif len(obj) == 1 and len(sub) == 2:
            sub = self.genUriRef(sub[0], sub[1])
            pred = self.genUriRef(pred[0], pred[1])
            obj = self.genLiteral(obj[0])
        self.newGraph.set((sub, pred, obj))

    def addToGraph(self, sub, pred, obj):
        """Add to graph new info.
        Input:
        sub (list) max len 2
        pred (list) max len 2
        obj (list) max len 2 if 1 will use Literal value
        """
        if len(obj) == 1 and len(sub) == 1:
            self.newGraph.add((self.genUriRef(sub[0]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genLiteral(obj[0])))
        elif len(obj) == 1 and len(sub) == 2:
            self.newGraph.add((self.genUriRef(sub[0], sub[1]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genLiteral(obj[0])))
        elif len(obj) == 2 and len(sub) == 1:
            self.newGraph.add((self.genUriRef(sub[0]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genUriRef(obj[0], obj[1])))
        elif len(obj) == 2 and len(sub) == 2:
            self.newGraph.add((self.genUriRef(sub[0], sub[1]),
                               self.genUriRef(pred[0], pred[1]),
                               self.genUriRef(obj[0], obj[1])))
        else:
            raise Exception('Failing to add object to graph due to mismatch')

    def defineMRMLPrefixes(self):
        """Define all known prefixes."""
        self.getSavedPrefixes()
        for prefix, val in list(self.prefixes.items()):
            if isinstance(val, dict):
                continue
            self.newGraph.bind(prefix, val)

    def _addSite(self, **kwargs):
        """Add Site to Model"""
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Topology')))
        for uri in ['sitename', 'version', 'webdomain']:
            if uri not in kwargs:
                continue
            self.addToGraph(['site'],
                            ['mrs', 'hasNetworkAddress'],
                            ['site', f':{uri}'])
            self.addToGraph(['site', f':{uri}'],
                            ['rdf', 'type'],
                            ['mrs', 'NetworkAddress'])
            self.addToGraph(['site', f":{uri}"],
                            ['mrs', 'type'],
                            [uri])
            self.setToGraph(['site', f":{uri}"],
                            ['mrs', 'value'],
                            [kwargs[uri]])

    def _updateVersion(self, **kwargs):
        """Update Version in model"""
        self.newGraph.set((self.genUriRef('site', ':version'),
                           self.genUriRef('mrs', 'value'),
                           self.genLiteral(kwargs['version'])))

    def _addNode(self, **kwargs):
        """Add Node to Model"""
        if not kwargs['hostname']:
            return ""
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('nml', 'hasNode'),
                           self.genUriRef('site', f":{kwargs['hostname']}")))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}"),
                           self.genUriRef('nml', 'name'),
                           self.genLiteral(f"{self.sitename}:{kwargs['hostname']}")))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}"),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Node')))
        return f":{kwargs['hostname']}"

    def _addPort(self, **kwargs):
        """Add Port to Model"""
        self._addNode(**kwargs)
        if not kwargs['hostname'] or not kwargs['portName']:
            return ""
        newuri = f":{kwargs['hostname']}:{self.switch.getSystemValidPortName(kwargs['portName'])}"
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}"),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', newuri)))
        self.newGraph.add((self.genUriRef('site', newuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        if 'parent' in kwargs and kwargs['parent']:
            self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:{kwargs['parent']}"),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', newuri)))
        return newuri

    def _addSwitchingService(self, **kwargs):
        """Add Switching Service to Model"""
        reqKeys = ['hostname', 'vsw']
        if self.__checkifReqKeysMissing(reqKeys, kwargs):
            return ""
        if kwargs['vsw'] != kwargs['hostname']:
            self.logger.debug(f"Config mistake. Hostname != vsw ({kwargs['hostname']} != {kwargs['vsw']})")
            return ""
        svcService = f":{kwargs['hostname']}:service+vsw"
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}"),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', svcService)))
        self.newGraph.add((self.genUriRef('site', svcService),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'SwitchingService')))
        self.newGraph.add((self.genUriRef('site', svcService),
                           self.genUriRef('nml', 'encoding'),
                           self.genUriRef('schema')))
        return svcService

    def _addSwitchingSubnet(self, **kwargs):
        """Add Switching Subnet which comes from delta parsed request"""
        svcService = self._addSwitchingService(**kwargs)
        subnetUri = f"{svcService}{kwargs['subnet']}"
        self.newGraph.add((self.genUriRef('site', svcService),
                           self.genUriRef('mrs', 'providesSubnet'),
                           self.genUriRef('site', subnetUri)))
        self.newGraph.add((self.genUriRef('site', subnetUri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'SwitchingSubnet')))

        self.newGraph.add((self.genUriRef('mrs', 'SwitchingSubnet'),
                          self.genUriRef('rdf', 'type'),
                          self.genUriRef('rdfs', 'Class')))
        self.newGraph.add((self.genUriRef('mrs', 'SwitchingSubnet'),
                          self.genUriRef('rdf', 'type'),
                          self.genUriRef('rdfs', 'Resource')))
        return subnetUri

    def _addPortSwitchingSubnet(self, **kwargs):
        """Add Port into Switching Subnet"""
        puri = self._addVlanPort(**kwargs)
        self.newGraph.add((self.genUriRef('site', kwargs['subnet']),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', puri)))
        return puri


    # TODO: JOIN BandwidthService with RoutingService.
    # It only needs to know the defaults.
    # Also _addSwitchingService
    def _addBandwidthService(self, **kwargs):
        """Add Bandwidth Service to Model"""
        if kwargs.get('bwuri', ''):
            return kwargs['bwuri']
        if not kwargs.get('uri', ''):
            kwargs['uri'] = self._addPort(**kwargs)
        if not kwargs['uri']:
            return ""
        bws = f"{kwargs['uri']}:service+{'bw'}"
        self.newGraph.add((self.genUriRef('site', kwargs['uri']),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', bws)))
        self.newGraph.add((self.genUriRef('site', bws),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'BandwidthService')))
        self.newGraph.add((self.genUriRef('site', bws),
                           self.genUriRef('mrs', 'type'),
                           self.genLiteral('guaranteedCapped')))
        # add
        # TODO: In future we should allow not only guaranteedCapped, but also other types.
        # Requires mainly change on Agents to apply diff Traffic Shaping policies
        return bws

    def _addBandwidthServiceRoute(self, **kwargs):
        if not kwargs.get('routeuri', '') or not kwargs.get('uri', ''):
            return
        self.newGraph.add((self.genUriRef('site', kwargs['routeuri']),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', kwargs['uri'])))


    def _addBandwidthServiceParams(self, **kwargs):
        """Add Bandwitdh Service Parameters to Model"""
        bws = self._addBandwidthService(**kwargs)
        for item in [['unit', 'unit', "mbps"],
                     ['maximumCapacity', 'maximumCapacity', 100000, XSD.long],
                     ['availableCapacity', 'availableCapacity', 100000, XSD.long],
                     ['granularity', 'granularity', 1000, XSD.long],
                     ['reservableCapacity', 'reservableCapacity', 100000, XSD.long],
                     ['minReservableCapacity', 'minReservableCapacity', 1000, XSD.long],
                     ['type', 'type', 'guaranteedCapped'],
                     ['priority', 'priority', 0]]:
            if item[0] not in kwargs:
                kwargs[item[0]] = item[2]
            if len(item) == 4:
                # Means XSD type is defined.
                self._mrsLiteral(bws, item[1], str(kwargs[item[0]]), item[3])
            else:
                self._mrsLiteral(bws, item[1], str(kwargs[item[0]]))

    def _addRoutingService(self, **kwargs):
        """Add Routing Service"""
        uri = self._addNode(**kwargs)
        if not uri:
            return ""
        rst = f":{kwargs['hostname']}:service+{kwargs['rstname']}"
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', rst)))
        self.newGraph.add((self.genUriRef('site', rst),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingService')))
        if 'iptype' in kwargs:
            for keytype in ['%s-subnet-pool', '%s-address-pool']:
                name = keytype % kwargs['iptype']
                if name in kwargs:
                    self._addNetworkAddress(rst, name, kwargs[name])
        if 'private_asn' in kwargs:
            self._addNetworkAddress(rst, 'private_asn', str(kwargs['private_asn']))
        return rst

    def _addL3VPN(self, **kwargs):
        """Add L3 VPN Definition to Model"""
        # Service Definition for L3
        uri = self._addRoutingService(**kwargs)
        if not uri:
            return ""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', f":{kwargs['hostname']}:sd:l3vpn")))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:l3vpn"),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:l3vpn"),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/l3-vpn')))
        return f":{kwargs['hostname']}:sd:l3vpn"

    def _addRoutingTable(self, **kwargs):
        """Add Routing Table to Model"""
        uri = self._addRoutingService(**kwargs)
        if not uri:
            return ""
        self._addL3VPN(**kwargs)
        routingtable = f"{uri}:rt-table+{kwargs.get('rt-table', '')}"
        if 'rtableuri' in kwargs and kwargs['rtableuri']:
            routingtable = kwargs['rtableuri']
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', 'providesRoutingTable'),
                           self.genUriRef('site', routingtable)))
        self.newGraph.add((self.genUriRef('site', routingtable),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingTable')))
        return routingtable

    def _addRoute(self, **kwargs):
        """Add Route To Model"""
        ruri = self._addRoutingTable(**kwargs)
        if not ruri:
            return ""
        routeuri = ""
        if 'routeuri' in kwargs and kwargs['routeuri']:
            routeuri = kwargs['routeuri']
        elif kwargs.get('routename', False):
            routeuri = f"{ruri}:route+{kwargs['routename']}"
        else:
            return ""
        self.newGraph.add((self.genUriRef('site', ruri),
                           self.genUriRef('mrs', 'hasRoute'),
                           self.genUriRef('site', routeuri)))
        self.newGraph.add((self.genUriRef('site', routeuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'Route')))
        return routeuri

    def _addProvidesRoute(self, **kwargs):
        """Add Provides Route to Model"""
        suri = self._addRoutingService(**kwargs)
        if not suri or not kwargs['routeuri']:
            return ""
        self.newGraph.add((self.genUriRef('site', suri),
                           self.genUriRef('mrs', 'providesRoute'),
                           self.genUriRef('site', kwargs['routeuri'])))
        return kwargs['routeuri']

    def _addRouteEntry(self, **kwargs):
        """Add Route Entry"""
        ruri = self._addRoute(**kwargs)
        if not ruri:
            return ""
        if 'uri' not in kwargs:
            kwargs['uri'] = f"{ruri}:net-address+{kwargs['routename']}"
        self.newGraph.add((self.genUriRef('site', ruri),
                           self.genUriRef('mrs', kwargs['routetype']),
                           self.genUriRef('site', kwargs['uri'])))
        self._addNetworkAddressEntry(**kwargs)
        return kwargs['uri']

    def _addNetworkAddressEntry(self, **kwargs):
        """Add Network Address Entry to model"""
        self.addToGraph(['site', kwargs['uri']],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', kwargs['uri']],
                        ['mrs', 'type'],
                        [kwargs['type']])
        self.setToGraph(['site', kwargs['uri']],
                        ['mrs', 'value'],
                        [kwargs['value']])


    def _addVswPort(self, **kwargs):
        """Add VSW Port to Model"""
        uri = self._addPort(**kwargs)
        vsw = self._addSwitchingService(**kwargs)
        if not uri or not vsw:
            return ""
        self.newGraph.add((self.genUriRef('site', vsw),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', uri)))
        return uri

    def _addRstPort(self, **kwargs):
        """Add RST Port to Model"""
        uri = ''
        if 'vlan' in kwargs:
            uri = self._addVlanPort(**kwargs)
        else:
            uri = self._addPort(**kwargs)
        if not uri:
            return ""
        iptypes = []
        if kwargs.get('nodetype', '') == 'switch' and kwargs.get('hostname', 'no-host') in self.prefixes.get('rst', {}):
            try:
                iptypes = self.config.get(kwargs['hostname'], 'rsts_enabled')
            except NoOptionError:
                iptypes = []
        elif kwargs.get('nodetype', '') == 'server' and kwargs.get('rsts_enabled', ''):
            iptypes = kwargs.get('rsts_enabled')
        for iptype in strtolist(iptypes, ','):
            if iptype not in ['ipv4', 'ipv6']:
                continue
            self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:service+rst-{iptype}"),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', uri)))
        return uri

    def _addVlanPort(self, **kwargs):
        """Add Vlan Port to Model"""
        if not kwargs['vlan'] and not kwargs['vtype']:
            return ""
        uri = self._addPort(**kwargs)
        vlanuri = f"{uri}:{kwargs['vtype']}+{kwargs['vlan']}"
        if not kwargs['portName'].startswith('Vlan_'):
            uri = self._addPort(**kwargs)
            self.newGraph.add((self.genUriRef('site', uri),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', vlanuri)))
        self.newGraph.add((self.genUriRef('site', vlanuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        return vlanuri

    def _addVlanLabel(self, **kwargs):
        """Add Vlan Label to Model"""
        vlanuri = self._addVlanPort(**kwargs)
        if not vlanuri:
            return ""
        labeluri = f"{vlanuri}:label+{kwargs['vlan']}"
        self.newGraph.add((self.genUriRef('site', vlanuri),
                           self.genUriRef('nml', 'hasLabel'),
                           self.genUriRef('site', labeluri)))
        self.newGraph.add((self.genUriRef('site', labeluri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Label')))
        self.newGraph.add((self.genUriRef('site', labeluri),
                           self.genUriRef('nml', 'labeltype'),
                           self.genUriRef('schema', '#vlan')))
        self.newGraph.set((self.genUriRef('site', labeluri),
                           self.genUriRef('nml', 'value'),
                           self.genLiteral(str(kwargs['vlan']))))
        return labeluri

    def _addLabelSwapping(self, **kwargs):
        """Add Label Swapping to Model"""
        # vlan key is used as label swapping. change to pass all as kwargs
        reqKeys = ['switchingserviceuri', 'labelswapping']
        if self.__checkifReqKeysMissing(reqKeys, kwargs):
            return ""
        self._nmlLiteral(kwargs['switchingserviceuri'], 'labelSwapping', str(kwargs['labelswapping']))
        return kwargs['labelswapping']

    def _addNetworkAddress(self, uri, name, value):
        """Add NetworkAddress to Model"""
        sname = name
        if isinstance(name, list):
            sname = name[1]
            name = name[0]
        self.addToGraph(['site', uri],
                        ['mrs', 'hasNetworkAddress'],
                        ['site', f'{uri}:{name}'])
        self.addToGraph(['site', f'{uri}:{name}'],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', f"{uri}:{name}"],
                        ['mrs', 'type'],
                        [sname])
        self.setToGraph(['site', f"{uri}:{name}"],
                        ['mrs', 'value'],
                        [value])

    # ==========================================================
    # These are very general model add ons
    # ==========================================================
    def _nmlLiteral(self, uri, nmlkey, value, datatype=None):
        """Add NML Literal to Model"""
        self.newGraph.set((self.genUriRef('site', uri),
                           self.genUriRef('nml', nmlkey),
                           self.genLiteral(value, datatype)))

    def _mrsLiteral(self, uri, mrskey, value, datatype=None):
        """Add MRS Literal to Model"""
        self.newGraph.set((self.genUriRef('site', uri),
                           self.genUriRef('mrs', mrskey),
                           self.genLiteral(value, datatype)))
