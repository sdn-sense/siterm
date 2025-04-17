#!/usr/bin/env python3
# pylint: disable=C0301
"""
    Add/Reduce deltas from MRML

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from rdflib.namespace import XSD
from SiteRMLibs.MainUtilities import convertTSToDatetime
from SiteRMLibs.ipaddr import normalizedip


class DeltaInfo():
    """Add Delta info, mainly tag, connID, timeline"""
    # pylint: disable=E1101,W0201

    def addNetworkStatus(self, params, uri):
        """Add Scheduling state into model"""
        # There are 2 ways this can come:
        # 1) via _params dictionary
        netstatus = ''
        if '_params' in params and params['_params'].get('networkstatus', ''):
            netstatus = params['_params']['networkstatus']
        # 2) for service as dictionary and networkstatus key
        elif 'networkstatus' in params:
            netstatus = params['networkstatus']
        if not netstatus:
            return
        self.addToGraph(['site', uri],
                        ['mrs', 'hasNetworkStatus'],
                        ['site', f'{uri}:status'])
        self.addToGraph(['site', f'{uri}:status'],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkStatus'])
        self.addToGraph(['site', f"{uri}:status"],
                        ['mrs', 'type'],
                        ["dataplane"])
        self.setToGraph(['site', f"{uri}:status"],
                        ['mrs', 'value'],
                        [netstatus])

    def addTimeline(self, params, uri):
        """Add timeline in the model"""
        timeline = params.get('_params', {}).get('existsDuring', {})
        if not timeline:
            return
        timeuri = params.get('_params', {}).get('existsDuring', {}).get('uri', '')
        if timeuri:
            timeuri = self.genUriRef(custom=timeuri)
        else:
            timeuri = self.genUriRef('site', f"{uri}:lifetime")
        self.newGraph.add((self.genUriRef('nml', 'Lifetime'),
                          self.genUriRef('rdf', 'type'),
                          self.genUriRef('rdfs', 'Class')))
        self.newGraph.add((self.genUriRef('nml', 'Lifetime'),
                          self.genUriRef('rdf', 'type'),
                          self.genUriRef('rdfs', 'Resource')))

        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'existsDuring'),
                           timeuri))
        self.newGraph.add((timeuri,
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Lifetime')))
        if 'start' in timeline:
            self.setToGraph(['site', f"{uri}:lifetime"],
                            ['nml', 'start'],
                            [convertTSToDatetime(timeline['start'])])
        if 'end' in timeline:
            self.setToGraph(['site', f"{uri}:lifetime"],
                            ['nml', 'end'],
                            [convertTSToDatetime(timeline['end'])])
        return


    def _addParams(self, params, uri, sublevel=False):
        """Add all params, like tag, belongsTo, labelSwapping, timeline"""
        if '_params' not in params:
            return
        for key in [['tag', 'mrs', True, None], ['labelSwapping', 'nml', True, XSD.boolean],
                    ['belongsTo', 'nml', False, None], ['encoding', 'nml', False, None]]:
            val = ""
            for val in set(params.get('_params', {}).get(key[0], "").split('|')):
                if not val:
                    continue
                if key[2]:
                    val = self.genLiteral(str(val), key[3])
                else:
                    val = self.genUriRef('', custom=val)
                self.newGraph.add((self.genUriRef('site', uri),
                                    self.genUriRef(key[1], key[0]),
                                    val))
        if not sublevel:
            self.addTimeline(params, uri)
            self.addNetworkStatus(params, uri)
            self._addNetworkAddrVsw(params, uri)

    def _addService(self, portDict, uri):
        if not portDict.get('hasService', {}):
            return
        portDict['hasService']['uri'] = uri
        bwuri = self._addBandwidthService(**portDict['hasService'])
        portDict['hasService']['bwuri'] = bwuri
        self.addTimeline(portDict, bwuri)
        self._addBandwidthServiceParams(**portDict['hasService'])
        # TODO: This should depend on switch config if this is configurable
        # self.addNetworkStatus(portDict['hasService'], bwuri)

    def _addNetworkAddr(self, portDict, uri):
        """Add Network delta info"""
        del uri
        netDict = portDict.get('hasNetworkAddress', {})
        if not netDict:
            return
        for ipkey in ['ipv4', 'ipv6']:
            ipdict = netDict.get(f'{ipkey}-address', {})
            if not ipdict:
                continue
            val = normalizedip(ipdict.get('value', ''))
            uri = ipdict.get('uri', '')
            if val and uri:
                self._addVals(ipkey, ipkey, val, portDict['uri'][len(self.prefixes['site']):])
                self._addParams(ipdict, uri)

    def _addNetworkAddrVsw(self, params, uri):
        """Add Network delta info"""
        portDict = params.get('_params', {})
        if not portDict:
            return
        netDict = portDict.get('hasNetworkAddress', {})
        if not netDict:
            return
        for ipkey in ['ipv4', 'ipv6']:
            ipdict = netDict.get(f'{ipkey}-address', {})
            if not ipdict:
                continue
            val = normalizedip(ipdict.get('value', ''))
            if val and uri:
                ipdict.setdefault('_params', {}).setdefault('tag', params.get('_params', {}).get('tag', None))
                self._addVals(ipkey, ipkey, val, uri, **{'labeluri': ipdict.get('uri', ''), 'delta': True})
                self._addParams(ipdict, ipdict.get('uri', ''), True)

    def addvswInfo(self, vswDict, uri):
        """Add vsw Info from params"""
        self._addParams(vswDict, uri)
        for key, val in vswDict.items():
            if key == '_params':
                continue
            if not isinstance(val, dict):
                continue
            for port, portDict in val.items():
                if portDict.get('hasLabel', {}).get('labeltype', None) == 'ethernet#vlan':
                    vlan = str(portDict['hasLabel']['value'])
                    if 'uri' in portDict and self.checkIfStarted(portDict):
                        self.URIs['vlans'].setdefault(key, {}).setdefault(port, {}).setdefault(int(vlan), portDict['uri'])
                    portDict['uri'] = self._addVlanPort(hostname=key, portName=port, vlan=vlan,
                                                        vtype='vlanport', labeltype='ethernet#vlan', uri=portDict.get('uri', ''))
                    self._addVlanLabel(hostname=key, portName=port, vlan=vlan, vtype='vlanport', labeltype='ethernet#vlan', uri=portDict['uri'])
                    self._addIsAlias(uri=portDict['uri'], isAlias=portDict.get('isAlias'))
                    if key in self.switch.switches['output'].keys():
                        self._addPortSwitchingSubnet(hostname=key, portName=port, vsw=key, vtype='vlanport', subnet=uri, vlan=vlan, uri=portDict['uri'])
                    self._addParams(portDict, portDict['uri'])
                    self._addService(portDict, portDict['uri'])
                    self._addNetworkAddr(portDict, portDict['uri'])
                else:
                    self.logger.debug(f'port {port} and portDict {portDict} ignored. No vlan label')

    def addRouteTables(self):
        """Add Route tables"""
        for host, vals in self.activeDeltas.get('output', {}).get('RoutingMapping', {}).items():
            for routeTable, iptypes in vals.get('providesRoutingTable', {}).items():
                for iptype in iptypes.keys():
                    self._addRoutingTable(hostname=host, rstname=f"rst-{iptype}", rtableuri=routeTable)
                    routedict = self.activeDeltas.get('output', {}).get('rst', {}).get(routeTable, {}).get(host, {}).get(iptype, {})
                    self._addParams(routedict, routeTable)
                    for route in list(routedict.get('hasRoute', {})):
                        self._addRoute(hostname=host, rstname=f"rst-{iptype}", rtableuri=routeTable, routeuri=route)

    def addRoutes(self):
        """Add individual routes"""
        for host, vals in self.activeDeltas.get('output', {}).get('RoutingMapping', {}).items():
            for routeTable, iptypes in vals.get('providesRoute', {}).items():
                for iptype in iptypes.keys():
                    routedict = self.activeDeltas.get('output', {}).get('rst', {}).get(routeTable, {}).get(host, {}).get(iptype, {})
                    self._addParams(routedict, routeTable)
                    rtableuri = routedict.get("belongsToRoutingTable", "")
                    self._addParams(routedict, rtableuri)
                    for route, routeInfo in routedict.get('hasRoute', {}).items():
                        self._addProvidesRoute(hostname=host, rstname=f"rst-{iptype}", routeuri=route)
                        self._addBandwidthServiceRoute(**{'routeuri': route, 'uri': routedict.get('hasService', {}).get('uri', '')})
                        self.addNetworkStatus(routedict.get('hasService', {}), routedict.get('hasService', {}).get('uri', ''))
                        self._addBandwidthServiceParams(**routedict.get('hasService', {}))
                        for key, val in routeInfo.items():
                            for _, entrVal in val.items():
                                netadd = {'hostname': host,
                                          'rstname': f"rst-{iptype}",
                                          'rtableuri': rtableuri,
                                          'routeuri': route,
                                          'routetype': key,
                                          'uri': entrVal.get('key', ''),
                                          'type': entrVal.get('type', ''),
                                          'value': entrVal.get('value', '')}
                                self._addRouteEntry(**netadd)

    def addDeltaInfo(self):
        """Append all deltas to Model."""
        # Virtual Switching Info
        for host, vals in self.activeDeltas.get('output', {}).get('SubnetMapping', {}).items():
            for subnet in vals.get('providesSubnet', {}).keys():
                svcService = self._addSwitchingService(hostname=host, vsw=host)
                subnetUri = subnet.split(svcService)[1]
                uri = self._addSwitchingSubnet(hostname=host, vsw=host, subnet=subnetUri)
                self.addvswInfo(self.activeDeltas.get('output', {}).get('vsw', {}).get(subnet, {}), uri)
        # Add Kube Info (for hosts without vsw)
        for urn, vals in self.activeDeltas.get('output', {}).get('kube', {}).items():
            self.addvswInfo(vals, urn)
        # Add Single port info
        for urn, vals in self.activeDeltas.get('output', {}).get('singleport', {}).items():
            self.addvswInfo(vals, urn)
        # Routing Service Info
        self.addRouteTables()
        self.addRoutes()
