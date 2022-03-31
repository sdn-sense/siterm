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
    """This generates all known default prefixes."""
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

    def genUriRef(self, prefix=None, add=None, custom=None):
        """Generate URIRef and return."""
        if custom:
            return URIRef(custom)
        if not add:
            return URIRef("%s" % self.prefixes[prefix])
        return URIRef("%s%s" % (self.prefixes[prefix], add))

    @staticmethod
    def genLiteral(value, datatype=None):
        """Returns simple Literal RDF out."""
        if datatype:
            return Literal(value, datatype=datatype)
        return Literal(value)


    def _addIsAlias(self, uri, portSwitch):
        if 'isAlias' in portSwitch and portSwitch['isAlias']:
            self.newGraph.add((self.genUriRef('site', uri),
                               self.genUriRef('nml', 'isAlias'),
                               self.genUriRef('', custom=portSwitch['isAlias'])))

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
        self._addNode(**kwargs)
        if not kwargs['hostname'] or not kwargs['portName']:
            return ""
        self.newGraph.add((self.genUriRef('site', ":%s" % kwargs['hostname']),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['portName']))))
        self.newGraph.add((self.genUriRef('site', ":%s:%s" % (kwargs['hostname'], kwargs['portName'])),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        return ":%s:%s" % (kwargs['hostname'], kwargs['portName'])

    def _addSwitchingService(self, **kwargs):
        self._addNode(**kwargs)
        if not kwargs['hostname'] or not kwargs['vsw']:
            return ""
        # vsw == hostname (One switching service per Node
        # Any reason to support more?
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
        """ Add Switching Subnet which comes from delta parsed request """
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
        """ Add Port into Switching Subnet """
        puri = self._addVlanPort(**kwargs)
        self.newGraph.add((self.genUriRef('site', kwargs['subnet']),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', puri)))
        return puri


    # TODO: JOIN BandwidthService with RoutingService.
    # It only needs to know the defaults.
    # Also _addSwitchingService
    def _addBandwidthService(self, **kwargs):
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
        uri = self._addRoutingService(**kwargs)
        if not uri:
            return ""
        self._addL3VPN(**kwargs)
        routingtable = "%s:rt-table+%s" % (uri, kwargs['rt-table'])
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', 'providesRoutingTable'),
                           self.genUriRef('site', routingtable)))
        self.newGraph.add((self.genUriRef('site', routingtable),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingTable')))
        return routingtable

    def _addRoute(self, **kwargs):
        # hostname, routename
        ruri = self._addRoutingTable(**kwargs)
        if not ruri or not kwargs['routename']:
            return ""
        routeuri = "%s:route+%s" % (ruri, kwargs['routename'])
        self.newGraph.add((self.genUriRef('site', ruri),
                           self.genUriRef('mrs', 'hasRoute'),
                           self.genUriRef('site', routeuri)))
        self.newGraph.add((self.genUriRef('site', routeuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'Route')))
        return routeuri

    def _addRouteEntry(self, **kwargs):
        ruri = self._addRoute(**kwargs)
        if not ruri:
            return ""
        routeEntry = "%s:net-address+%s" % (ruri, kwargs['routename'])
        self.newGraph.add((self.genUriRef('site', ruri),
                           self.genUriRef('mrs', kwargs['routetype']),
                           self.genUriRef('site', routeEntry)))
        self.addToGraph(['site', routeEntry],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', routeEntry],
                        ['mrs', 'type'],
                        [kwargs['type']])
        self.addToGraph(['site', routeEntry],
                        ['mrs', 'value'],
                        [kwargs['value']])
        return routeEntry


    def _addVswPort(self, **kwargs):
        uri = self._addPort(**kwargs)
        vsw = self._addSwitchingService(**kwargs)
        if not uri or not vsw:
            return ""
        self.newGraph.add((self.genUriRef('site', vsw),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', uri)))
        return uri

    def _addRstPort(self, **kwargs):
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
        if not kwargs['vlan']:
            return ""
        vlanuri = ":%s:%s:vlanport+%s" % (kwargs['hostname'], kwargs['portName'], kwargs['vlan'])
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
        # vlan key is used as label swapping. change to pass all as kwargs
        uri = self._addSwitchingService(**kwargs)
        if not uri or not kwargs['vsw']:
            return ""
        self._nmlLiteral(uri, 'labelSwapping', str(kwargs['labelswapping']))
        return kwargs['labelswapping']

    def _addNetworkAddress(self, uri, name, value):
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
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', nmlkey),
                           self.genLiteral(value, datatype)))

    def _mrsLiteral(self, uri, mrskey, value, datatype=None):
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', mrskey),
                           self.genLiteral(value, datatype)))
