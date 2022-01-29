#!/usr/bin/env python3
"""
    Add/Reduce deltas from MRML

    TODO: Rewrite from current state and not add deltas itself;


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow

class DeltaInfo():
    """ Add Delta info, mainly tag, connID, timeline """
    # pylint: disable=E1101,W0201,E0203

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
        self.newGraph.add((self.genUriRef('site', timeuri),
                           self.genUriRef('mrs', 'tag'),
                           self.genLiteral('monitor:status:%s' % state)))

    def addTimeline(self, timeline, uri):
        """ Add timeline in the model """
        if not timeline:
            return
        timeuri = "%s:lifetime" % uri
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('nml', 'existsDuring'),
                           self.genUriRef('site', timeuri)))
        self.newGraph.add((self.genUriRef('site', timeuri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'Lifetime')))
        # end;start
        if 'start' in timeline:
            self.newGraph.add((self.genUriRef('site', timeuri),
                               self.genUriRef('nml', 'start'),
                               self.genLiteral(timeline['start'])))
        if 'end' in timeline:
            self.newGraph.add((self.genUriRef('site', timeuri),
                               self.genUriRef('nml', 'end'),
                               self.genLiteral(timeline['end'])))
        self.addSchedulingState(timeline, uri, timeuri)
        return


    def _addParams(self, params, uri):
        """ Add all params, like tag, belongsTo, labelSwapping, timeline """
        for key in [['tag', 'mrs'], ['belongsTo', 'nml'], ['labelSwapping', 'nml']]:
            if key[0] in params:
                self.newGraph.add((self.genUriRef('site', uri),
                                   self.genUriRef(key[1], key[0]),
                                   self.genUriRef('', custom=params[key[0]])))
        if 'existsDuring' in params:
            self.addTimeline(params['existsDuring'], uri)

    def addService(self, serviceDict, uri):
        return

    def addvswInfo(self, vswDict, uri):
        """ Add vsw Info from params """
        import pdb; pdb.set_trace()
        for key, val in vswDict.items():
            if key == '_params':
                # It get's full uri here.
                self._addParams(val, uri)
            else:
                for port, portDict in val.items():
                    if portDict.get('hasLabel', {}).get('labeltype', None) == 'ethernet#vlan':
                        vlan = portDict['hasLabel']['value']
                        porturi = self._addVlanPort(hostname=key, portName=port, vlan=vlan)
                        if key in self.switch.switches['output'].keys():
                            self._addPortSwitchingSubnet(hostname=key, portName=port, vsw=key, subnet=uri, vlan=vlan)
                        self._addParams(portDict.get('_params', {}), porturi)
                    else:
                        self.logger.debug('port %s and portDict %s ignored. No vlan label' % (port, portDict))

    def addDeltaInfo(self):
        """Append all deltas to Model."""
        activeDeltas = self.dbI.get('activeDeltas')
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            activeDeltas['output'] = evaldict(activeDeltas['output'])
        print(activeDeltas)
        for host, vals in activeDeltas['output'].get('SubnetMapping', {}).items():
            for subnet in vals.get('providesSubnet', {}).keys():
                svcService = self._addSwitchingService(hostname=host, vsw=host)
                subnetUri = subnet.split(svcService)[1]
                uri = self._addSwitchingSubnet(hostname=host, vsw=host, subnet=subnetUri)
                self.addvswInfo(activeDeltas.get('output', {}).get('vsw', {}).get(subnet, {}), uri)
