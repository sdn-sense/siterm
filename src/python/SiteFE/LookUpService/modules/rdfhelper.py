#!/usr/bin/env python3
"""
    RDF Helper, prefixes, add to model.


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import configparser
from rdflib import URIRef, Literal
from rdflib.namespace import XSD

class RDFHelper():
    """RDF Helper preparation class."""
    # pylint: disable=E1101,W0201,W0613

    def getSavedPrefixes(self, additionalhosts=None):
        """Get Saved prefixes from a configuration file."""
        prefixes = {}
        for key in ['mrs', 'nml', 'owl', 'rdf', 'xml', 'xsd', 'rdfs', 'schema', 'sd']:
            prefixes[key] = self.config.get('prefixes', key)
        prefixSite = "%s:%s:%s" % (self.config.get('prefixes', 'site'),
                                   self.config.get(self.sitename, 'domain'),
                                   self.config.get(self.sitename, 'year'))
        prefixes['site'] = prefixSite
        for switchName in self.config.get(self.sitename, 'switch').split(','):
            for key in ['vsw', 'rst']:
                try:
                    prefixes.setdefault(key, {})
                    tKey = self.config.get(switchName, key)
                    if tKey != switchName:
                        self.logger.debug('Config mistake. Hostname != %s (%s != %s)' % (key, switchName, tKey))
                        continue
                    prefixes[key][switchName] = "%s:%s:service+%s" % (prefixes['site'], tKey, key)
                    # This is to be confirmed once we check the L3 request. TODO
                    #if additionalhosts:
                    #    for host in additionalhosts:
                    #        prefixes[key][host] = "%s:service+%s:%s" % (prefixes['site'], key, host)
                except configparser.NoOptionError:
                    self.logger.debug('ERROR: %s parameter is not defined for %s.', key, switchName)
                    continue
        self.prefixes = prefixes

    def __checkifReqKeysMissing(self, reqKeys, allArgs):
        """Check if key is not missing"""
        for key in reqKeys:
            if key not in allArgs or not allArgs.get(key, None):
                self.logger.debug("Key %s is missing in allArgs: %s" % (key, allArgs))
                return True
        return False



    def genUriRef(self, prefix=None, add=None, custom=None):
        """Generate URIRef and return."""
        if custom:
            return URIRef(custom)
        if not add:
            return URIRef("%s" % self.prefixes[prefix])
        if add.startswith(self.prefixes[prefix]):
            return URIRef("%s" % add)
        return URIRef("%s%s" % (self.prefixes[prefix], add))

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
            self.newGraph.add((self.genUriRef('site', kwargs['uri']),
                               self.genUriRef('nml', 'isAlias'),
                               self.genUriRef('', custom=kwargs['isAlias'])))
            if 'hostname' in kwargs and kwargs['hostname'] and \
               'portName' in kwargs and kwargs['portName']:
                self._addRstPort(**kwargs)

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
        self.addToGraph(['site'],
                        ['mrs', 'hasNetworkAddress'],
                        ['site', 'sitename'])
        self.addToGraph(['site', 'sitename'],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', 'sitename'],
                        ['mrs', 'type'],
                        ['sitename'])
        self.addToGraph(['site', 'sitename'],
                        ['mrs', 'value'],
                        [kwargs['sitename']])


    def _addNode(self, **kwargs):
        """Add Node to Model"""
        if not kwargs['hostname']:
            return ""
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('nml', 'hasNode'),
                           self.genUriRef('site', ":%s" % kwargs['hostname'])))
        self.newGraph.add((self.genUriRef('site', ":%s" % kwargs['hostname']),
                           self.genUriRef('nml', 'name'),
                           self.genLiteral(kwargs['hostname'])))
        self.newGraph.add((self.genUriRef('site', ":%s" % kwargs['hostname']),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Node')))
        return ":%s" % kwargs['hostname']

    def _addPort(self, **kwargs):
        """Add Port to Model"""
        self._addNode(**kwargs)
        if not kwargs['hostname'] or not kwargs['portName']:
            return ""
        self.newGraph.add((self.genUriRef('site', ":%s" % kwargs['hostname']),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['portName']))))
        self.newGraph.add((self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['portName'])),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        if 'parent' in kwargs and kwargs['parent']:
            self.newGraph.add((self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['parent'])),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['portName']))))
        return ":%s:%s" % (kwargs['hostname'], kwargs['portName'])

    def _addSwitchingService(self, **kwargs):
        """Add Switching Service to Model"""
        reqKeys = ['hostname', 'vsw']
        if self.__checkifReqKeysMissing(reqKeys, kwargs):
            return ""
        if kwargs['vsw'] != kwargs['hostname']:
            self.logger.debug('Config mistake. Hostname != vsw (%s != %s)' % (kwargs['hostname'], kwargs['vsw']))
            return ""
        svcService = ':%s:service+vsw' % kwargs['hostname']
        self.newGraph.add((self.genUriRef('site', ':%s' % kwargs['hostname']),
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
        subnetUri = "%s%s" % (svcService, kwargs['subnet'])
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
        if not kwargs.get('uri', ''):
            kwargs['uri'] = self._addPort(**kwargs)
        if not kwargs['uri']:
            return ""
        bws = "%s:service+%s" % (kwargs['uri'], 'bw')
        self.newGraph.add((self.genUriRef('site', kwargs['uri']),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', bws)))
        self.newGraph.add((self.genUriRef('site', bws),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'BandwidthService')))
        self.newGraph.add((self.genUriRef('site', bws),
                           self.genUriRef('mrs', 'type'),
                           self.genLiteral('guaranteedCapped')))
        # TODO: In future we should allow not only guaranteedCapped, but also other types.
        # Requires mainly change on Agents to apply diff Traffic Shaping policies
        return bws

    def _addBandwidthServiceParams(self, **kwargs):
        """Add Bandwitdh Service Parameters to Model"""
        bws = self._addBandwidthService(**kwargs)
        for item in [['unit', 'unit', "bps"],
                     ['maximumCapacity', 'maximumCapacity', 10000000000, XSD.long],
                     ['availableCapacity', 'availableCapacity', 10000000000, XSD.long],
                     ['granularity', 'granularity', 1000000, XSD.long],
                     ['reservableCapacity', 'reservableCapacity', 10000000000, XSD.long],
                     ['minReservableCapacity', 'minReservableCapacity', 10000000000, XSD.long],
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
        rst = ':%s:service+%s' % (kwargs['hostname'], kwargs['rstname'])
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
                    self._addNetworkAddress(rst, name, str(kwargs[name]))
        return rst

    def _addL3VPN(self, **kwargs):
        """Add L3 VPN Definition to Model"""
        # Service Definition for L3
        uri = self._addRoutingService(**kwargs)
        if not uri:
            return ""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', ':%s:sd:l3vpn' % kwargs['hostname'])))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % kwargs['hostname']),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % kwargs['hostname']),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/l3-vpn')))
        return ':%s:sd:l3vpn' % kwargs['hostname']

    def _addRoutingTable(self, **kwargs):
        """Add Routing Table to Model"""
        uri = self._addRoutingService(**kwargs)
        if not uri:
            return ""
        self._addL3VPN(**kwargs)
        routingtable = "%s:rt-table+%s" % (uri, kwargs.get('rt-table', ''))
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
            routeuri = "%s:route+%s" % (ruri, kwargs['routename'])
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
            kwargs['uri'] = "%s:net-address+%s" % (ruri, kwargs['routename'])
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
        self.addToGraph(['site', kwargs['uri']],
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
        # TODO: Allow this to be controlled via config, which rst's to include
        # something like: rsts_enabled: ['ipv4'] or ['ipv4', 'ipv6']
        for iptype in ['ipv4', 'ipv6']:
            self.newGraph.add((self.genUriRef('site', ":%s:service+rst-%s" % (kwargs['hostname'], iptype)),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', uri)))
        return uri

    def _addVlanPort(self, **kwargs):
        """Add Vlan Port to Model"""
        if not kwargs['vlan'] and not kwargs['vtype']:
            return ""
        vlanuri = ":%s:%s:%s+%s" % (kwargs['hostname'], kwargs['portName'], kwargs['vtype'], kwargs['vlan'])
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
        labeluri = "%s:label+%s" % (vlanuri, kwargs['vlan'])
        self.newGraph.add((self.genUriRef('site', vlanuri),
                           self.genUriRef('nml', 'hasLabel'),
                           self.genUriRef('site', labeluri)))
        self.newGraph.add((self.genUriRef('site', labeluri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Label')))
        self.newGraph.add((self.genUriRef('site', labeluri),
                           self.genUriRef('nml', 'labeltype'),
                           self.genUriRef('schema', '#vlan')))
        self.newGraph.add((self.genUriRef('site', labeluri),
                           self.genUriRef('nml', 'value'),
                           self.genLiteral(kwargs['vlan'])))
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
                        ['site', '%s:%s' % (uri, name)])
        self.addToGraph(['site', '%s:%s' % (uri, name)],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', "%s:%s" % (uri, name)],
                        ['mrs', 'type'],
                        [sname])
        self.addToGraph(['site', "%s:%s" % (uri, name)],
                        ['mrs', 'value'],
                        [value])

    # ==========================================================
    # These are very general model add ons
    # ==========================================================
    def _nmlLiteral(self, uri, nmlkey, value, datatype=None):
        """Add NML Literal to Model"""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', nmlkey),
                           self.genLiteral(value, datatype)))

    def _mrsLiteral(self, uri, mrskey, value, datatype=None):
        """Add MRS Literal to Model"""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', mrskey),
                           self.genLiteral(value, datatype)))
