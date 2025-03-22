#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    RDF Helper, prefixes, add to model.


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import json
from rdflib import URIRef, Literal
from rdflib.namespace import XSD
from SiteRMLibs.ipaddr import normalizedip
from SiteRMLibs.ipaddr import normalizeipdict
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.ipaddr import validMRMLName
from SiteRMLibs.ipaddr import makeUrl
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.CustomExceptions import NoSectionError
from SiteRMLibs.MainUtilities import strtolist


def generateVal(cls, inval, inkey, esc=False):
    """Generate mrml valid val/key for ipv4/ipv6"""
    if isinstance(inval, dict) and inkey == 'ipv4':
        return _genIPv4(cls, inval, inkey, esc)
    if isinstance(inval, dict) and inkey == 'ipv6':
        return _genIPv6(cls, inval, inkey, esc)
    if isinstance(inval, (dict, list)):
        cls.logger.info(f'Out is dictionary/list, but vals unknown. Return as str {inval}')
        return str(inval)
    if isinstance(inval, (int, float)):
        return inval
    if isinstance(inval, str):
        for call in [int, float]:
            try:
                return call(inval)
            except ValueError:
                continue
    return str(inval)

def _genIPv4(cls, inval, inkey, esc=True):
    """
    Generate Interface IPv4 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 32
        if 'masklen' in inval:
            subnet = inval['masklen']
        if 'address' in inval:
            if esc:
                return validMRMLName(f"{inval['address']}/{subnet}")
            return f"{inval['address']}/{subnet}"
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv4(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug(f'No IPv4 value. Return empty String. This might break things. Input: {inval} {inkey}')
    return ''

def _genIPv6(cls, inval, inkey, esc=True):
    """
    Generate Interface IPv6 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 64 # Default we will use /64 just to secure code from diff ansible-switch outputs
        if 'subnet' in inval:
            subnet = inval['subnet'].split('/')[-1]
        if 'masklen' in inval:
            subnet = inval['masklen']
        if 'address' in inval:
            if esc:
                return validMRMLName(f"{inval['address']}/{subnet}")
            return f"{inval['address']}/{subnet}"
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv6(cls, val, inkey), 'val': normalizeipdict(val)} for val in inval]
        return tmpKeys
    cls.logger.debug(f'No IPv6 value. Return empty String. This might break things. Input: {inval} {inkey}')
    return ''

class RDFHelper():
    """RDF Helper preparation class."""
    # pylint: disable=E1101,W0201,W0613

    def generateKey(self, inval, inkey):
        """Generate keys for mrml and escape special charts"""
        if isinstance(inval, str):
            return replaceSpecialSymbols(inval)
        if isinstance(inval, int):
            return str(inval)
        if inkey == 'ipv4':
            if not isinstance(inval, list):
                # Diff switches return differently. Make it always list in case dict
                # e.g. Dell OS 9 returns dict if 1 IP set, List if 2
                # Arista EOS always returns list.
                inval = [inval]
            return _genIPv4(self, inval, inkey)
        if inkey == 'ipv6':
            if not isinstance(inval, list):
                # Diff switches return differently. Make it always list in case dict
                # e.g. Dell OS 9 returns dict if 1 IP set, List if 2
                # Arista EOS always returns list.
                inval = [inval]
            return _genIPv6(self, inval, inkey)
        self.logger.debug(f'Generate Keys return empty. Unexpected. Input: {inval} {inkey}')
        return ""

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
                    self.logger.debug('Warning: %s parameter is not defined for %s.', key, switchName)
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

    def _addVals(self, key, subkey, val, newuri, **kwargs):
        if not subkey:
            return
        if key in ['ipv4', 'ipv6']:
            tmpVal = None
            if isinstance(val, dict):
                tmpVal = f"{val.get('address', '')}/{val.get('masklen', '')}"
                if tmpVal == "/":
                    return
                tmpVal = normalizedip(tmpVal)
            elif isinstance(val, str):
                tmpVal = normalizedip(val)
            else:
                self.logger.info(f'Unexpected value for IP. Skipping entry. Input data: {key}, {subkey}, {val}, {newuri}')
            if not tmpVal:
                return
            labeluri = self.URIs.get('ips', {}).get(tmpVal, {}).get('uri', f"{newuri}:{key}-address+{validMRMLName(tmpVal)}")
            reptype = self.URIs.get('ips', {}).get(tmpVal, {}).get('type', f'{key}-address')

        elif key == 'sense-rtmon':
            labeluri = f"{newuri}:{key}+{subkey}"
            reptype = f'{key}:name'
        elif key == 'macaddress':
            labeluri = f"{newuri}:mac-address+{subkey}"
            reptype = 'mac-address'
        else:
            labeluri = f"{newuri}:{key}+{subkey}"
            reptype = key
        if 'labeluri' in kwargs and kwargs['labeluri']:
            labeluri = kwargs['labeluri']
        val = generateVal(self, val, key, False)
        self.addToGraph(['site', newuri],
                        ['mrs', 'hasNetworkAddress'],
                        ['site', labeluri])
        self.addToGraph(['site', labeluri],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        for typeval in reptype.split('|'):
            self.addToGraph(['site', labeluri],
                            ['mrs', 'type'],
                            [typeval])
        self.setToGraph(['site', labeluri],
                        ['mrs', 'value'],
                        [val])

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

    def _addMetadataService(self, uri=""):
        """Add Metadat Service"""
        metaService = f"{uri}:service+metadata"
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'hasService'),
                           self.genUriRef('site', metaService)))
        self.newGraph.add((self.genUriRef('site', metaService),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('mrs', 'MetadataService')))
        self.newGraph.add((self.genUriRef('site', metaService),
                           self.genUriRef('mrs', 'type'),
                           self.genLiteral('sense-metadata')))
        return metaService

    def _addMetadata(self, **kwargs):
        """Add Frontend Metadata to Model"""
        metaService = self._addMetadataService()
        # Add hasNetworkAddress and hasNetworkAttribute
        if 'version' in kwargs and kwargs['version']:
            self._addHasNetworkAttribute(metaService, 'version', '/version', kwargs['version'])
        if 'webdomain' in kwargs and kwargs['webdomain']:
            self._addNetworkAddress(metaService, ['webdomain', 'metadata:webdomain'], makeUrl(kwargs['webdomain']))
            if 'sitename' in kwargs and kwargs['sitename']:
                self._addHasNetworkAttribute(metaService, 'sitename', '/sitename', kwargs['sitename'])
                nodeExporter = makeUrl(kwargs["webdomain"], f"{kwargs['sitename']}/sitefe/json/frontend/metrics")
                self._addHasNetworkAttribute(metaService, 'nodeExporter', 'metadata:/nodeExporter', nodeExporter)
        # Add all metadata from frontend configuration;
        try:
            metadata = self.config.get(kwargs.get('sitename', None), 'metadata')
            for key, vals in metadata.items():
                self._addHasNetworkAttribute(metaService, key, f'/{key}', json.dumps(vals))
        except (NoSectionError, NoOptionError):
            pass

    def _addNodeMetadata(self, **kwargs):
        """Add Node Metadata to Model"""
        # if node_exporter defined, add metrics url
        conf = kwargs.get('nodeDict', {}).get('hostinfo', {}).get('Summary', {}).get('config', {})
        nodeExporter = conf.get('general', {}).get('node_exporter', '')
        if nodeExporter:
            metaService = self._addMetadataService(uri=f":{kwargs['hostname']}")
            nodeExporter = makeUrl(nodeExporter, "metrics")
            self._addHasNetworkAttribute(metaService, 'nodeExporter', 'metadata:/nodeExporter', nodeExporter)
        # Allow agent also add metadata information (future use is to tell that Multus is available)
        for key, vals in conf.get('general', {}).get('metadata', {}).items():
            metaService = self._addMetadataService(uri=f":{kwargs['hostname']}")
            self._addHasNetworkAttribute(metaService, key, f'/{key}', json.dumps(vals))

    def _updateVersion(self, **kwargs):
        """Update Version in model"""
        self.newGraph.set((self.genUriRef('site', ':service+metadata:version'),
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
        # Add mrs:NetworkAddress (nml:hostname is for legacy)
        self._addNetworkAddress(f":{kwargs['hostname']}", "fqdn", kwargs['hostname'])
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
        kwargs['uri'] = svcService
        self._addMultiPointService(**kwargs)
        self._addDebugIPService(**kwargs)
        return svcService

    def _addMultiPointService(self, **kwargs):
        """Add MultiPoint Service to Model"""
        if not kwargs.get('vswmp', ''):
            return
        self.newGraph.add((self.genUriRef('site', kwargs['uri']),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswmp']}")))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswmp']}"),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswmp']}"),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2018/06/descriptions/l2-mp-es')))

    def _addDebugIPService(self, **kwargs):
        """Add DebugIP Service to model"""
        if not kwargs.get('vswdbip', ''):
            return
        self.newGraph.add((self.genUriRef('site', kwargs['uri']),
                           self.genUriRef('sd', 'hasServiceDefinition'),
                           self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswdbip']}")))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswdbip']}"),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.genUriRef('site', f":{kwargs['hostname']}:sd:{kwargs['vswdbip']}"),
                           self.genUriRef('sd', 'serviceType'),
                           self.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/config-debug-ip')))

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
                     ['granularity', 'granularity', 100, XSD.long],
                     ['reservableCapacity', 'reservableCapacity', 100000, XSD.long],
                     ['minReservableCapacity', 'minReservableCapacity', 100, XSD.long],
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
        if kwargs.get('rt-table', None):
            routingtable = f"{uri}:rt-table+{kwargs.get('rt-table')}"
        elif 'rtableuri' in kwargs and kwargs['rtableuri']:
            routingtable = kwargs['rtableuri']
        else:
            return ""
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

    def __getVlanURI(self, porturi, **kwargs):
        """Get Vlan URI"""
        if 'uri' in kwargs and kwargs['uri']:
            return kwargs['uri']
        sysPort = self.switch.getSystemValidPortName(kwargs['portName'])
        vlanuri = self.URIs.get('vlans', {}).get(kwargs['hostname'], {}).get(sysPort, {}).get(int(kwargs['vlan']), '')
        if not vlanuri:
            vlanuri = f"{porturi}:{kwargs['vtype']}+{kwargs['vlan']}"
        return vlanuri

    def _addVlanPort(self, **kwargs):
        """Add Vlan Port to Model"""
        if not kwargs['vlan'] and not kwargs['vtype']:
            return ""
        uri = self._addPort(**kwargs)
        vlanuri = self.__getVlanURI(uri, **kwargs)
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
        self._nmlLiteral(kwargs['switchingserviceuri'], 'labelSwapping', str(kwargs['labelswapping']), XSD.boolean)
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

    def _addHasNetworkAttribute(self, uri, name, vtype, value):
        """Add NetworkAttribute to Model"""
        self.addToGraph(['site', uri],
                        ['mrs', 'hasNetworkAttribute'],
                        ['site', f'{uri}:{name}'])
        self.addToGraph(['site', f'{uri}:{name}'],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAttribute'])
        self.addToGraph(['site', f'{uri}:{name}'],
                        ['mrs', 'type'],
                        ["metadata:directory"])
        self.addToGraph(['site', f'{uri}:{name}'],
                        ['mrs', 'tag'],
                        [vtype])
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
