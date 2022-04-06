#!/usr/bin/env python3
"""
    Add/Reduce deltas from MRML

    TODO: Rewrite from current state and not add deltas itself;


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from rdflib.namespace import XSD
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getActiveDeltas
from DTNRMLibs.MainUtilities import convertTSToDatetime


class DeltaInfo():
    """ Add Delta info, mainly tag, connID, timeline """
    # pylint: disable=E1101,W0201

    def addSchedulingState(self, timeline, uri, timeuri):
        """ Add Scheduling state into model """
        if not timeline:
            return
        state = 'unknown'
        if 'start' in timeline:
            if timeline['start'] < getUTCnow():
                state = 'active'
            else:
                state = 'scheduled'
        if 'end' in timeline:
            if timeline['end'] < getUTCnow():
                state = 'deactivating'
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('mrs', 'tag'),
                           self.genLiteral('monitor:status:%s' % state)))
        self.newGraph.add((timeuri,
                           self.genUriRef('mrs', 'tag'),
                           self.genLiteral('monitor:status:%s' % state)))

    def addTimeline(self, params, uri):
        """ Add timeline in the model """
        timeline = params.get('_params', {}).get('existsDuring', {})
        if not timeline:
            return
        timeuri = params.get('_params', {}).get('existsDuring', {}).get('uri', '')
        if timeuri:
            timeuri = self.genUriRef(custom=timeuri)
        else:
            timeuri = self.genUriRef('site', "%s:lifetime" % uri)
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
        # end;start
        if 'start' in timeline:
            self.newGraph.add((timeuri,
                               self.genUriRef('nml', 'start'),
                               self.genLiteral(convertTSToDatetime(timeline['start']), datatype=XSD.string)))
        if 'end' in timeline:
            self.newGraph.add((timeuri,
                               self.genUriRef('nml', 'end'),
                               self.genLiteral(convertTSToDatetime(timeline['end']), datatype=XSD.string)))
        self.addSchedulingState(timeline, uri, timeuri)
        return


    def _addParams(self, params, uri):
        """ Add all params, like tag, belongsTo, labelSwapping, timeline """
        if '_params' not in params:
            return
        # ['key', 'type', 'literal']
        for key in [['tag', 'mrs', True], ['labelSwapping', 'nml', True],
                    ['belongsTo', 'nml', False], ['encoding', 'nml', False]]:
            val = ""
            for val in set(params.get('_params', {}).get(key[0], "").split('|')):
                if not val:
                    continue
                if key[2]:
                    val = self.genLiteral(str(val))
                else:
                    val = self.genUriRef('', custom=val)
                self.newGraph.add((self.genUriRef('site', uri),
                                    self.genUriRef(key[1], key[0]),
                                    val))
        self.addTimeline(params, uri)

    def _addService(self, portDict, uri):
        if not portDict.get('hasService', {}):
            return
        portDict['hasService']['uri'] = uri
        bwuri = self._addBandwidthService(**portDict['hasService'])
        self.addTimeline(portDict, bwuri)
        self._addBandwidthServiceParams(**portDict['hasService'])

    def _addNetworkAddr(self, portDict, uri):
        def __validMRMLName(valIn, ipType='ipv4'):
            # TODO: Move to general. reused in many places
            if ipType == 'ipv4':
                return valIn.replace('/', '_')
            return valIn.replace(':', '_').replace('/', '_').replace(' ', '_')
        netDict = portDict.get('hasNetworkAddress', {})
        if not netDict:
            return
        for ipkey in ['ipv4', 'ipv6']:
            ipdict = netDict.get('%s-address' % ipkey, {})
            if not ipdict:
                continue
            for key in ipdict.get('type', 'undefined').split('|'):
                out = [__validMRMLName('%s-address+%s' % (ipkey, ipdict.get('value', 'undefined'))), key]
                self._addNetworkAddress(portDict['uri'], out, ipdict.get('value', 'undefined'))

    def addvswInfo(self, vswDict, uri):
        """ Add vsw Info from params """
        self._addParams(vswDict, uri)
        for key, val in vswDict.items():
            if key == '_params':
                continue
            for port, portDict in val.items():
                if portDict.get('hasLabel', {}).get('labeltype', None) == 'ethernet#vlan':
                    vlan = str(portDict['hasLabel']['value'])
                    portDict['uri'] = self._addVlanPort(hostname=key, portName=port, vlan=vlan, labeltype='ethernet#vlan')
                    self._addVlanLabel(hostname=key, portName=port, vlan=vlan, vtype='vlanport', labeltype='ethernet#vlan')
                    self._addIsAlias(uri=portDict['uri'], isAlias=portDict.get('isAlias'))
                    if key in self.switch.switches['output'].keys():
                        self._addPortSwitchingSubnet(hostname=key, portName=port, vsw=key, subnet=uri, vlan=vlan)
                    self._addParams(portDict, portDict['uri'])
                    self._addService(portDict, portDict['uri'])
                    self._addNetworkAddr(portDict, portDict['uri'])
                else:
                    self.logger.debug('port %s and portDict %s ignored. No vlan label' % (port, portDict))

    def addDeltaInfo(self):
        """Append all deltas to Model."""
        activeDeltas = getActiveDeltas(self)
        for host, vals in activeDeltas.get('output', {}).get('SubnetMapping', {}).items():
            for subnet in vals.get('providesSubnet', {}).keys():
                svcService = self._addSwitchingService(hostname=host, vsw=host)
                subnetUri = subnet.split(svcService)[1]
                uri = self._addSwitchingSubnet(hostname=host, vsw=host, subnet=subnetUri)
                self.addvswInfo(activeDeltas.get('output', {}).get('vsw', {}).get(subnet, {}), uri)
