#!/usr/bin/env python3
"""
    RDF Helper, prefixes, add to model.


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import configparser
from rdflib import URIRef, Literal

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
                    prefixes[key][switchName] = "%s:service+%s:%s" % (prefixes['site'], key, tKey)
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
    def genLiteral(value):
        """Returns simple Literal RDF out."""
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
            self.newGraph.bind(prefix, val)

    def _addSite(self, hostname=None, portName=None, vsw=None, vlan=None):
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Topology')))

    def _addNode(self, hostname=None, portName=None, vsw=None, vlan=None):
        if not hostname:
            return ""
        self.newGraph.add((self.genUriRef('site'),
                           self.genUriRef('nml', 'hasNode'),
                           self.genUriRef('site', ":%s" % hostname)))
        self.newGraph.add((self.genUriRef('site', ":%s" % hostname),
                           self.genUriRef('nml', 'name'),
                           self.genLiteral(hostname)))
        self.newGraph.add((self.genUriRef('site', ":%s" % hostname),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Node')))
        return ":%s" % hostname

    def _addPort(self, hostname=None, portName=None, vsw=None, vlan=None):
        self._addNode(hostname)
        if not hostname or not portName:
            return ""
        self.newGraph.add((self.genUriRef('site', ":%s" % hostname),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', ":%s:%s" % (hostname, portName))))
        self.newGraph.add((self.genUriRef('site', ":%s:%s" % (hostname, portName)),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        return ":%s:%s" % (hostname, portName)

    def _addSwitchingService(self, hostname=None, portName=None, vsw=None, vlan=None):
        self._addNode(hostname)
        if not hostname or not vsw:
            return ""
        svcService = ':%s:service+vsw:%s' % (hostname, vsw)
        self.newGraph.add((self.genUriRef('site', ':%s' % hostname),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', svcService)))
        self.newGraph.add((self.genUriRef('site', svcService),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'SwitchingService')))
        self.newGraph.add((self.genUriRef('site', svcService),
                           self.genUriRef('nml', 'encoding'),
                           self.genUriRef('schema')))
        return svcService

    def _addBandwidthService(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = self._addPort(hostname, portName)
        if not uri:
            return ""
        bws = "%s:%s" % (uri, 'bandwidthService')
        self.newGraph.add((self.genUriRef('site', uri),
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

    def _addRoutingService(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = self._addNode(hostname)
        if not uri:
            return ""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', ':%s:service+rst' % hostname)))
        self.newGraph.add((self.genUriRef('site', ':%s:service+rst' % hostname),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingService')))
        return ':%s:service+rst' % hostname

    def _addL3VPN(self, hostname=None, portName=None, vsw=None, vlan=None):
        # Service Definition for L3
        uri = self._addRoutingService(hostname)
        if not uri:
            return ""
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', ':%s:sd:l3vpn' % hostname)))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % hostname),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', ':%s:sd:l3vpn' % hostname),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/l3-vpn')))
        return ':%s:sd:l3vpn' % hostname

    def _addRoutingTable(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = self._addRoutingService(hostname)
        if not uri:
            return ""
        self._addL3VPN(hostname)
        routingtable = ":%s:%s" % (hostname, portName)
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', 'providesRoutingTable'),
                           self.genUriRef('site', routingtable)))
        self.newGraph.add((self.genUriRef('site', routingtable),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'RoutingTable')))
        return routingtable

    def _addRoute(self, hostname=None, portName=None, vsw=None, vlan=None):
        ruri = self._addRoutingTable(hostname, portName)
        if not ruri or not vsw:
            return ""
        routeuri = "%s:route+%s" % (ruri, vsw)
        self.newGraph.add((self.genUriRef('site', routeuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'Route')))
        self.newGraph.add((self.genUriRef('site', ruri),
                           self.genUriRef('mrs', 'hasRoute'),
                           self.genUriRef('site', routeuri)))
        return routeuri


    def _addVswPort(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = self._addPort(hostname, portName)
        if not uri or not vsw:
            return ""
        self.newGraph.add((self.genUriRef('site', ':%s:service+vsw:%s' % (hostname, vsw)),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', uri)))
        return uri

    def _addRstPort(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = ''
        if vlan:
            uri = self._addVlanPort(hostname, portName, vsw, vlan)
        else:
            uri = self._addPort(hostname, portName)
        if not uri:
            return ""
        self.newGraph.add((self.genUriRef('site', ":%s:service+rst" % hostname),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', uri)))
        return uri

    def _addVlanPort(self, hostname=None, portName=None, vsw=None, vlan=None):
        uri = self._addPort(hostname, portName)
        if not uri or not vlan:
            return ""
        vlanuri = ":%s:%s:vlanport+%s" % (hostname, portName, vlan)
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'hasBidirectionalPort'),
                           self.genUriRef('site', vlanuri)))
        self.newGraph.add((self.genUriRef('site', vlanuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        return vlanuri

    def _addLabelSwapping(self, hostname=None, portName=None, vsw=None, vlan=None):
        # vlan key is used as label swapping. change to pass all as kwargs
        uri = self._addSwitchingService(hostname, None, vsw)
        if not uri or not vlan:
            return ""
        self._nmlLiteral(uri, 'labelSwapping', vlan)
        return vlan

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
    def _nmlLiteral(self, uri, nmlkey, value):
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', nmlkey),
                           self.genLiteral(value)))

    def _mrsLiteral(self, uri, mrskey, value):
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', mrskey),
                           self.genLiteral(value)))
