#!/usr/bin/env python3
"""
    LookUpService gets all information and prepares MRML schema.
    TODO: Append switch information;

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
UpdateDate      : 2021/11/08
"""
from __future__ import division
import os
import tempfile
import datetime
import importlib
import configparser
from rdflib import Graph
from rdflib import URIRef, Literal
from rdflib.compare import isomorphic
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import generateHash
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getUTCnow


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


class prefixDB():
    """This generates all known default prefixes."""
    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.prefixes = {}
        self.getSavedPrefixes()

    def getSavedPrefixes(self):
        """Get Saved prefixes from a configuration file."""
        prefixes = {}
        for key in ['mrs', 'nml', 'owl', 'rdf', 'xml', 'xsd', 'rdfs', 'schema', 'sd']:
            prefixes[key] = self.config.get('prefixes', key)
        prefixSite = "%s:%s:%s" % (self.config.get('prefixes', 'site'),
                                   self.config.get(self.sitename, 'domain'),
                                   self.config.get(self.sitename, 'year'))
        prefixes['site'] = prefixSite
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


class LookUpService():
    """Lookup Service prepares MRML model about the system."""
    def __init__(self, config, logger, sitename):
        self.sitename = sitename
        self.logger = logger
        self.config = config
        self.prefixDB = prefixDB(config, sitename)
        self.dbI = getDBConn('LookUpService')
        self.newGraph = None
        self.shared = False
        self.hosts = {}
        self.renewSwitchConfig = True
        self.switchConfig = {'out': {}, 'method': None}
        self._getSwitchPlugin()

    def _getSwitchPlugin(self):
        switchPlugin = self.config.get(self.sitename, 'plugin')
        self.logger.info('Will load %s switch plugin' % switchPlugin)
        method = importlib.import_module("DTNRMLibs.Backends.%s" % switchPlugin.lower())
        self.switchConfig['class'] = method.Switch(self.config, self.logger, {}, self.sitename)

    def generateHostIsalias(self, **kwargs):
        """Generate Host Alias from configuration."""
        if 'isAlias' in kwargs['portSwitch'] and \
           kwargs['portSwitch']['isAlias']:
            self.newGraph.add((self.prefixDB.genUriRef('site', kwargs['newuri']),
                               self.prefixDB.genUriRef('nml', 'isAlias'),
                               self.prefixDB.genUriRef('', custom=kwargs['portSwitch']['isAlias'])))
        elif kwargs['portSwitch'] in list(self.hosts.keys()):
            for item in self.hosts[kwargs['portSwitch']]:
                if item['switchName'] == kwargs['switchName'] and item['switchPort'] == kwargs['portName']:
                    suri = "%s:%s" % (kwargs['newuri'], item['intfKey'])
                    self.newGraph.add((self.prefixDB.genUriRef('site', kwargs['newuri']),
                                       self.prefixDB.genUriRef('nml', 'isAlias'),
                                       self.prefixDB.genUriRef('site', suri)))

    def addToGraph(self, sub, pred, obj):
        """Add to graph new info.

        Input:
        sub (list) max len 2
        pred (list) max len 2
        obj (list) max len 2 if 1 will use Literal value
        """
        if len(obj) == 1 and len(sub) == 1:
            self.newGraph.add((self.prefixDB.genUriRef(sub[0]),
                               self.prefixDB.genUriRef(pred[0], pred[1]),
                               self.prefixDB.genLiteral(obj[0])))
        elif len(obj) == 1 and len(sub) == 2:
            self.newGraph.add((self.prefixDB.genUriRef(sub[0], sub[1]),
                               self.prefixDB.genUriRef(pred[0], pred[1]),
                               self.prefixDB.genLiteral(obj[0])))
        elif len(obj) == 2 and len(sub) == 1:
            self.newGraph.add((self.prefixDB.genUriRef(sub[0]),
                               self.prefixDB.genUriRef(pred[0], pred[1]),
                               self.prefixDB.genUriRef(obj[0], obj[1])))
        elif len(obj) == 2 and len(sub) == 2:
            self.newGraph.add((self.prefixDB.genUriRef(sub[0], sub[1]),
                               self.prefixDB.genUriRef(pred[0], pred[1]),
                               self.prefixDB.genUriRef(obj[0], obj[1])))
        else:
            raise Exception('Failing to add object to graph due to mismatch')

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

    def addSwitchIntfInfo(self, switchName, portName, portSwitch, newuri):
        """ Add switch info (not for raw switches) """
        if 'vlan_range' in list(portSwitch.keys()) and \
           portSwitch['vlan_range']:
            self.addToGraph(['site', newuri],
                            ['nml', 'hasLabelGroup'],
                            ['site', '%s:%s' % (newuri, "vlan-range")])
            self.addToGraph(['site', '%s:%s' % (newuri, "vlan-range")],
                            ['rdf', 'type'],
                            ['nml', 'LabelGroup'])
            self.addToGraph(['site', "%s:%s" % (newuri, "vlan-range")],
                            ['nml', 'labeltype'],
                            ['schema', '#vlan'])
            self.addToGraph(['site', "%s:%s" % (newuri, "vlan-range")],
                            ['nml', 'values'],
                            [portSwitch['vlan_range']])
            # Generate host alias or adds' isAlias
            self.generateHostIsalias(portSwitch=portSwitch, switchName=switchName,
                                     portName=portName, newuri=newuri)
            for key, val in portSwitch.items():
                if key == 'vlan_range':
                    continue
                if key == 'channel-member':
                    # This is very specific to Dell Force 10. TODO: What about others providing
                    # port channel? Might need to change it.
                    # Are there any specifics how port channel and channel members should be
                    # listed in mrml?
                    # Based on discussions with Xi - it should be: nml:hasBidirectionalPort
                    # TODO: Change to use of nml:hasBidirectionalPort
                    tmpVal = ""
                    for key1, val1 in val.items():
                        tmpVal += ",".join(["%s_%s" % (key1, val2.replace("/", "-")) for val2 in val1])
                    val = tmpVal
                self.addToGraph(['site', newuri],
                                ['mrs', 'hasNetworkAddress'],
                                ['site', '%s:%s' % (newuri, key)])
                self.addToGraph(['site', '%s:%s' % (newuri, key)],
                                ['rdf', 'type'],
                                ['mrs', 'NetworkAddress'])
                self.addToGraph(['site', "%s:%s" % (newuri, key)],
                                ['mrs', 'type'],
                                [key])
                self.addToGraph(['site', "%s:%s" % (newuri, key)],
                                ['mrs', 'value'],
                                [val])

    def _deltaReduction(self, dbObj, delta, mainGraphName):
        """Delta reduction."""
        delta['content'] = evaldict(delta['content'])
        self.logger.info('Working on %s delta reduction in state' % delta['uid'])
        mainGraph = Graph()
        mainGraph.parse(mainGraphName, format='turtle')
        reduction = delta['content']['reduction']
        tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        tmpFile.write(reduction)
        tmpFile.close()
        tmpGraph = Graph()
        tmpGraph.parse(tmpFile.name, format='turtle')
        os.unlink(tmpFile.name)
        self.logger.info('Main Graph len: %s Reduction Len: %s', len(mainGraph), len(tmpGraph))
        mainGraph -= tmpGraph
        dbObj.update('deltasmod', [{'uid': delta['uid'], 'updatedate': getUTCnow(), 'modadd': 'removed'}])
        return mainGraph

    def _addDeltaStatesInModel(self, mainGraph, state, addition):
        """Add Delta States into Model."""
        # Issue details: https://github.com/sdn-sense/siterm/issues/73
        for conn in addition:
            if 'timestart' in list(conn.keys()) and state == 'committed':
                if conn['timestart'] < getUTCnow():
                    state = 'activating'
                else:
                    state = 'scheduled'
            elif 'timeend' in list(conn.keys()) and conn['timeend'] < getUTCnow() and state == 'activated':
                state = 'deactivating'
            # Add new State under SwitchSubnet
            mainGraph.add((self.prefixDB.genUriRef(custom=conn['connectionID']),
                           self.prefixDB.genUriRef('mrs', 'tag'),
                           self.prefixDB.genLiteral('monitor:status:%s' % state)))
            # If timed delta, add State under lifetime resource
            if 'timestart' in list(conn.keys()) or 'timeend' in list(conn.keys()):
                mainGraph.add((self.prefixDB.genUriRef(custom="%s:lifetime" % conn['connectionID']),
                               self.prefixDB.genUriRef('mrs', 'tag'),
                               self.prefixDB.genLiteral('monitor:status:%s' % state)))
        return mainGraph


    def _deltaAddition(self, dbObj, delta, mainGraphName, updateState=True):
        """Delta addition lookup."""
        delta['content'] = evaldict(delta['content'])
        self.logger.info('Working on %s delta addition in state' % delta['uid'])
        mainGraph = Graph()
        mainGraph.parse(mainGraphName, format='turtle')
        addition = delta['content']['addition']
        tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        tmpFile.write(addition)
        tmpFile.close()
        tmpGraph = Graph()
        tmpGraph.parse(tmpFile.name, format='turtle')
        os.unlink(tmpFile.name)
        self.logger.info('Main Graph len: %s Addition Len: %s', len(mainGraph), len(tmpGraph))
        mainGraph += tmpGraph
        # Add delta states for that specific delta
        mainGraph = self._addDeltaStatesInModel(mainGraph, delta['state'], evaldict(delta['addition']))
        if updateState:
            dbObj.update('deltasmod', [{'uid': delta['uid'], 'updatedate': getUTCnow(), 'modadd': 'added'}])
        return mainGraph

    def appendDeltas(self, dbObj, mainGraphName):
        """Append all deltas to Model."""
        for modstate in ['added', 'add', 'remove']:
            for delta in dbObj.get('deltas', search=[['modadd', modstate]], limit=10):
                writeFile = False
                if delta['deltat'] == 'reduction':
                    if delta['state'] == 'failed':
                        continue
                    mainGraph = self._deltaReduction(dbObj, delta, mainGraphName)
                    writeFile = True
                elif delta['deltat'] in ['addition', 'modify'] and \
                (delta['modadd'] in ['add'] or delta['state'] in ['activated', 'activating', 'committed']):
                    mainGraph = self._deltaAddition(dbObj, delta, mainGraphName)
                    writeFile = True
                if writeFile:
                    with open(mainGraphName, "w") as fd:
                        fd.write(mainGraph.serialize(format='turtle'))

    @staticmethod
    def getCurrentModel(dbObj):
        """Get Current Model from DB."""
        currentModel = dbObj.get('models', orderby=['insertdate', 'DESC'], limit=1)
        currentGraph = Graph()
        if currentModel:
            try:
                currentGraph.parse(currentModel[0]['fileloc'], format='turtle')
            except IOError:
                currentGraph = Graph()
        return currentModel, currentGraph

    def checkForModelDiff(self, dbObj, saveName):
        """Check if models are different."""
        currentModel, currentGraph = self.getCurrentModel(dbObj)
        newGraph = Graph()
        newGraph.parse(saveName, format='turtle')
        return isomorphic(currentGraph, newGraph), currentModel

    def getModelSavePath(self):
        """Get Model Save Location."""
        now = datetime.datetime.now()
        saveDir = "%s/%s" % (self.config.get(self.sitename, "privatedir"), "LookUpService")
        createDirs(saveDir)
        return "%s/%s-%s-%s:%s:%s:%s.mrml" % (saveDir, now.year, now.month,
                                              now.day, now.hour, now.minute, now.second)

    def defineMRMLServices(self):
        """Defined Topology and Main Services available."""
        # Add main Topology
        self.newGraph.add((self.prefixDB.genUriRef('site'),
                           self.prefixDB.genUriRef('rdf', 'type'),
                           self.prefixDB.genUriRef('nml', 'Topology')))
        # Add Service
        for switchName in self.config.get(self.sitename, 'switch').split(','):
            try:
                vsw = self.config.get(switchName, 'vsw')
            except configparser.NoOptionError:
                self.logger.debug('ERROR: vsw parameter is not defined for %s.', switchName)
                continue
            self.newGraph.add((self.prefixDB.genUriRef('site'),
                               self.prefixDB.genUriRef('nml', 'hasService'),
                               self.prefixDB.genUriRef('site', ':service+vsw:%s' % vsw)))
            self.newGraph.add((self.prefixDB.genUriRef('site', ':service+vsw:%s' % vsw),
                               self.prefixDB.genUriRef('rdf', 'type'),
                               self.prefixDB.genUriRef('nml', 'SwitchingService')))

            # Add lableSwapping flag
            labelswap = "false"
            try:
                labelswap = self.config.get(switchName, 'labelswapping')
            except configparser.NoOptionError:
                self.logger.debug('Labelswapping parameter is not defined. By default it is set to False.')
            self.newGraph.add((self.prefixDB.genUriRef('site', ':service+vsw:%s' % vsw),
                               self.prefixDB.genUriRef('nml', 'labelSwapping'),
                               self.prefixDB.genLiteral(labelswap)))
            # Add base encoding for service
            self.newGraph.add((self.prefixDB.genUriRef('site', ':service+vsw:%s' % vsw),
                               self.prefixDB.genUriRef('nml', 'encoding'),
                               self.prefixDB.genUriRef('schema')))

    def defineMRMLPrefixes(self):
        """Define all known prefixes."""
        for prefix, val in list(self.prefixDB.prefixes.items()):
            self.newGraph.bind(prefix, val)

    def defineNodeInformation(self, nodeDict):
        """Define node information."""
        self.hosts[nodeDict['hostname']] = []
        self.newGraph.add((self.prefixDB.genUriRef('site'),
                           self.prefixDB.genUriRef('nml', 'hasNode'),
                           self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname'])))
        # Node General description
        self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.prefixDB.genUriRef('nml', 'name'),
                           self.prefixDB.genLiteral(nodeDict['hostname'])))
        self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.prefixDB.genUriRef('rdf', 'type'),
                           self.prefixDB.genUriRef('nml', 'Node')))
        self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.prefixDB.genUriRef('nml', 'insertTime'),
                           self.prefixDB.genLiteral(nodeDict['insertdate'])))
        # Provide location information about site Frontend
        try:
            self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.prefixDB.genUriRef('nml', 'latitude'),
                               self.prefixDB.genLiteral(self.config.get(self.sitename, 'latitude'))))
            self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.prefixDB.genUriRef('nml', 'longitude'),
                               self.prefixDB.genLiteral(self.config.get(self.sitename, 'longitude'))))
        except configparser.NoOptionError:
            self.logger.debug('Either one or both (latitude,longitude) are not defined. Continuing as normal')

    def defineLayer3MRML(self, nodeDict):
        """Define Layer 3 Routing Service for hostname"""
        hostinfo = evaldict(nodeDict['hostinfo'])
        self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                           self.prefixDB.genUriRef('nml', 'hasService'),
                           self.prefixDB.genUriRef('site', ':%s:service+rst' % nodeDict['hostname'])))
        self.newGraph.add((self.prefixDB.genUriRef('site', ':%s:service+rst' % nodeDict['hostname']),
                           self.prefixDB.genUriRef('rdf', 'type'),
                           self.prefixDB.genUriRef('mrs', 'RoutingService')))
        # Service Definition for L3
        self.newGraph.add((self.prefixDB.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                           self.prefixDB.genUriRef('sd', 'hasServiceDefinition'),
                           self.prefixDB.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname'])))
        self.newGraph.add((self.prefixDB.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname']),
                           self.prefixDB.genUriRef('rdf', 'type'),
                           self.prefixDB.genUriRef('sd', 'ServiceDefinition')))
        self.newGraph.add((self.prefixDB.genUriRef('site', ':%s:sd:l3vpn' % nodeDict['hostname']),
                           self.prefixDB.genUriRef('sd', 'serviceType'),
                           self.prefixDB.genLiteral('http://services.ogf.org/nsi/2019/08/descriptions/l3-vpn')))

        for tablegress in['table+defaultIngress', 'table+defaultEgress']:
            routingtable = ":%s:%s" % (nodeDict['hostname'], tablegress)
            self.newGraph.add((self.prefixDB.genUriRef('site', ':%s:service+rst' % nodeDict['hostname']),
                               self.prefixDB.genUriRef('mrs', 'providesRoutingTable'),
                               self.prefixDB.genUriRef('site', routingtable)))
            self.newGraph.add((self.prefixDB.genUriRef('site', routingtable),
                               self.prefixDB.genUriRef('rdf', 'type'),
                               self.prefixDB.genUriRef('mrs', 'RoutingTable')))
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
                self.newGraph.add((self.prefixDB.genUriRef('site', routename),
                                   self.prefixDB.genUriRef('rdf', 'type'),
                                   self.prefixDB.genUriRef('mrs', 'Route')))
                self.newGraph.add((self.prefixDB.genUriRef('site', routingtable),
                                   self.prefixDB.genUriRef('mrs', 'hasRoute'),
                                   self.prefixDB.genUriRef('site', routename)))
                if 'RTA_GATEWAY' in list(routeinfo.keys()):
                    self.newGraph.add((self.prefixDB.genUriRef('site', routename),
                                       self.prefixDB.genUriRef('mrs', 'routeTo'),
                                       self.prefixDB.genUriRef('site', '%s:%s' % (routename, 'to'))))
                    self.newGraph.add((self.prefixDB.genUriRef('site', routename),
                                       self.prefixDB.genUriRef('mrs', 'nextHop'),
                                       self.prefixDB.genUriRef('site', '%s:%s' % (routename, 'black-hole'))))
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
                    self.newGraph.add((self.prefixDB.genUriRef('site', routename),
                                       self.prefixDB.genUriRef('mrs', 'routeTo'),
                                       self.prefixDB.genUriRef('site', '%s:%s' % (routename, 'to'))))
                    self.newGraph.add((self.prefixDB.genUriRef('site', routename),
                                       self.prefixDB.genUriRef('mrs', 'nextHop'),
                                       self.prefixDB.genUriRef('site', defaultroutename)))
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['rdf', 'type'],
                                    ['mrs', 'NetworkAddress'])
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['mrs', 'type'],
                                    ['ipv4-prefix-list'])
                    self.addToGraph(['site', '%s:%s' % (routename, 'to')],
                                    ['mrs', 'value'],
                                    ['%s/%s' % (routeinfo['RTA_DST'], routeinfo['dst_len'])])

# Server routing dict
#[{'dst_len': 0, 'RTA_GATEWAY': '198.32.43.1'},'dst_len': 23, 'RTA_DST': '172.16.0.0', 'RTA_PREFSRC': '172.16.1.38'},
# {'dst_len': 16, 'RTA_DST': '172.17.0.0', 'RTA_PREFSRC': '172.17.0.1'},
# {'dst_len': 24, 'RTA_DST': '198.32.43.0', 'RTA_PREFSRC': '198.32.43.14'}]

# Swith rounting dict
#{'s0': {'ip': [{'ip': '0.0.0.0/0', 'routerIP': '192.168.255.254'},
#               {'vrf': 'lhcone', 'ip': '0.0.0.0/0', 'routerIP': '192.84.86.238'}],
#        'ipv6': [{'vrf': 'lhcone', 'ip': '::/0', 'routerIP': '2605:d9c0:0:ff02::'},
#                 {'vrf': 'lhcone', 'ip': '2605:d9c0:2::/48', 'routerIntf': 'NULL 0'}]}}



    def addSwitchInfo(self, jOut):
        """Add All Switch information from switch lookup plugin."""
        # Get switch information...
        switchInfo = self.switchConfig['out']
        if self.renewSwitchConfig:
            self.switchConfig['out'] = self.switchConfig['class'].getinfo(jOut, self.renewSwitchConfig)
            switchInfo = self.switchConfig['out']
            self.renewSwitchConfig = False
        else:
            self.logger.info('Will not reload switch configuration. Model has not changed last run.')
        # Add Switch information to MRML
        for switchName, switchDict in list(switchInfo['ports'].items()):
            self.logger.debug('Working on %s and %s' % (switchName, switchDict))
            try:
                vsw = self.config.get(switchName, 'vsw')
            except configparser.NoOptionError:
                self.logger.debug('ERROR: vsw parameter is not defined for %s.', switchName)
                continue
            for portName, portSwitch in list(switchDict.items()):
                if 'hostname' in portSwitch and 'isAlias' not in portSwitch:
                    newuri = ":%s:%s:%s" % (switchName, portName, portSwitch['hostname'])
                else:
                    newuri = ":%s:%s" % (switchName, portName)
                self.newGraph.add((self.prefixDB.genUriRef('site'),
                                   self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                                   self.prefixDB.genUriRef('site', newuri)))
                self.newGraph.add((self.prefixDB.genUriRef('site', ':service+vsw:%s' % vsw),
                                   self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                                   self.prefixDB.genUriRef('site', newuri)))
                self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                                   self.prefixDB.genUriRef('rdf', 'type'),
                                   self.prefixDB.genUriRef('nml', 'BidirectionalPort')))
                if switchName in list(switchInfo['ports'].keys()):
                    if portName in list(switchInfo['ports'][switchName].keys()):
                        # Add information about bidirection switch port
                        self.addSwitchIntfInfo(switchName, portName, portSwitch, newuri)
                    else:
                        self.logger.debug('Port %s is not in switchInfo' % portName)
                else:
                    self.logger.debug('switchName $%s is not in switchInfo' % switchName)

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
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('nml', 'hasService'),
                               self.prefixDB.genUriRef('site', "%s:%s" % (newuri, 'bandwidthService'))))
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('nml', 'isAlias'),
                               self.prefixDB.genUriRef('site', ":%s:%s:+" % (switchName, switchPort))))
            # BANDWIDTH Service for INTERFACE
            # ==========================================================================================
            bws = "%s:%s" % (newuri, 'bandwidthService')
            self.newGraph.add((self.prefixDB.genUriRef('site', bws),
                               self.prefixDB.genUriRef('rdf', 'type'),
                               self.prefixDB.genUriRef('mrs', 'BandwidthService')))
            self.newGraph.add((self.prefixDB.genUriRef('site', bws),
                               self.prefixDB.genUriRef('mrs', 'type'),
                               self.prefixDB.genLiteral('guaranteedCapped')))

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
                self.newGraph.add((self.prefixDB.genUriRef('site', bws),
                                   self.prefixDB.genUriRef('mrs', item[1]),
                                   self.prefixDB.genLiteral(value)))
            # ==========================================================================================
        if 'capacity' in list(intfDict.keys()):
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('mrs', 'capacity'),
                               self.prefixDB.genLiteral(intfDict['capacity'])))
        if 'vlan_range' in list(intfDict.keys()):
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('nml', 'hasLabelGroup'),
                               self.prefixDB.genUriRef('site', "%s:vlan-range" % newuri)))
            self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan-range" % newuri),
                               self.prefixDB.genUriRef('rdf', 'type'),
                               self.prefixDB.genUriRef('nml', 'LabelGroup')))
            self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan-range" % newuri),
                               self.prefixDB.genUriRef('nml', 'labeltype'),
                               self.prefixDB.genUriRef('schema', '#vlan')))
            self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan-range" % newuri),
                               self.prefixDB.genUriRef('nml', 'values'),
                               self.prefixDB.genLiteral(intfDict['vlan_range'])))
        self.shared = False
        if 'shared' in list(intfDict.keys()):
            self.shared = 'notshared'
            if intfDict['shared']:
                self.shared = 'shared'
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('mrs', 'type'),
                               self.prefixDB.genLiteral(self.shared)))

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
            self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                               self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                               self.prefixDB.genUriRef('site', newuri)))
            self.newGraph.add((self.prefixDB.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                               self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                               self.prefixDB.genUriRef('site', newuri)))
            # Specific node information.
            self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                               self.prefixDB.genUriRef('rdf', 'type'),
                               self.prefixDB.genUriRef('nml', 'BidirectionalPort')))
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
                    self.newGraph.add((self.prefixDB.genUriRef('site', vlanuri),
                                       self.prefixDB.genUriRef('rdf', 'type'),
                                       self.prefixDB.genUriRef('nml', 'BidirectionalPort')))
                    self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                                       self.prefixDB.genUriRef('nml', 'hasService'),
                                       self.prefixDB.genUriRef('site', "%s:%s" % (newuri, 'bandwidthService'))))
                    if self.shared:
                        self.newGraph.add((self.prefixDB.genUriRef('site', vlanuri),
                                           self.prefixDB.genUriRef('mrs', 'type'),
                                           self.prefixDB.genLiteral(self.shared)))
                    self.newGraph.add((self.prefixDB.genUriRef('site', ":%s" % nodeDict['hostname']),
                                       self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.prefixDB.genUriRef('site', vlanuri)))
                    self.newGraph.add((self.prefixDB.genUriRef('site', ":%s:service+rst" % nodeDict['hostname']),
                                       self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.prefixDB.genUriRef('site', vlanuri)))
                    self.newGraph.add((self.prefixDB.genUriRef('site', newuri),
                                       self.prefixDB.genUriRef('nml', 'hasBidirectionalPort'),
                                       self.prefixDB.genUriRef('site', vlanuri)))
                    if 'vlanid' in list(vlanDict.keys()):
                        self.newGraph.add((self.prefixDB.genUriRef('site', vlanuri),
                                           self.prefixDB.genUriRef('nml', 'hasLabel'),
                                           self.prefixDB.genUriRef('site', "%s:vlan" % vlanuri)))
                        self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.prefixDB.genUriRef('rdf', 'type'),
                                           self.prefixDB.genUriRef('nml', 'Label')))
                        self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.prefixDB.genUriRef('nml', 'labeltype'),
                                           self.prefixDB.genUriRef('schema', '#vlan')))
                        self.newGraph.add((self.prefixDB.genUriRef('site', "%s:vlan" % vlanuri),
                                           self.prefixDB.genUriRef('nml', 'value'),
                                           self.prefixDB.genLiteral(vlanDict['vlanid'])))
                    # Add hasNetworkAddress for vlan
                    # Now the mapping of the interface information:
                    self.addIntfInfo(vlanDict, vlanuri, False)

    def startwork(self):
        """Main start."""
        self.logger.info('Started LookupService work')
        dbObj = getVal(self.dbI, **{'sitename': self.sitename})
        workDir = self.config.get(self.sitename, 'privatedir') + "/LookUpService/"
        createDirs(workDir)
        self.newGraph = Graph()
        jOut = getAllHosts(self.sitename, self.logger)
        # ==================================================================================
        # 1. Define Basic MRML Prefixes
        # ==================================================================================
        self.defineMRMLPrefixes()
        # ==================================================================================
        # 2. Define Basic MRML Definition
        # ==================================================================================
        self.defineMRMLServices()
        self.hosts = {}

        for _, nodeDict in list(jOut.items()):
            # ==================================================================================
            # 3. Define Node inside yaml
            # ==================================================================================
            self.defineNodeInformation(nodeDict)
            # ==================================================================================
            # 4. Define Routing Service information
            # ==================================================================================
            self.defineLayer3MRML(nodeDict)
            # ==================================================================================
            # 5. Define Host Information and all it's interfaces.
            # ==================================================================================
            self.defineHostInfo(nodeDict)
        # ==================================================================================
        # 6. Define Switch information from Switch Lookup Plugin
        # ==================================================================================
        self.addSwitchInfo(jOut)

        saveName = self.getModelSavePath()
        with open(saveName, "w") as fd:
            fd.write(self.newGraph.serialize(format='turtle'))
        hashNum = generateHash(self.newGraph.serialize(format='turtle'))

        # Append all deltas to the model
        self.appendDeltas(dbObj, saveName)
        if dbObj.get('models', limit=1, search=[['uid', hashNum]]):
            raise Exception('hashNum %s is already in database...' % hashNum)

        self.logger.info('Checking if new model is different from previous')
        modelsEqual, modelinDB = self.checkForModelDiff(dbObj, saveName)
        lastKnownModel = {'uid': hashNum, 'insertdate': getUTCnow(),
                          'fileloc': saveName, 'content': str(self.newGraph.serialize(format='turtle'))}
        if modelsEqual:
            if modelinDB[0]['insertdate'] < int(getUTCnow() - 3600):
                # Force to update model every hour, Even there is no update;
                self.logger.info('Forcefully update model in db as it is older than 1h')
                dbObj.insert('models', [lastKnownModel])
                # Also next run get new info from switch plugin
                self.renewSwitchConfig = True
            else:
                self.logger.info('Models are equal.')
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
        else:
            self.logger.info('Models are different. Update DB')
            dbObj.insert('models', [lastKnownModel])
            # Also next run get new info from switch plugin
            self.renewSwitchConfig = True

        self.logger.debug('Last Known Model: %s' % str(lastKnownModel['fileloc']))
        # Clean Up old models (older than 24h.)
        for model in dbObj.get('models', limit=100, orderby=['insertdate', 'ASC']):
            if model['insertdate'] < int(getUTCnow() - 86400):
                self.logger.debug('delete %s', model['fileloc'])
                try:
                    os.unlink(model['fileloc'])
                except OSError as ex:
                    self.logger.debug('Got OS Error removing this model %s. Exc: %s' % (model, str(ex)))
                dbObj.delete('models', [['id', model['id']]])


def execute(config=None, logger=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if not logger:
        component = 'LookUpService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component), config.get(component, 'logLevel'))
    for siteName in config.get('general', 'sites').split(','):
        policer = LookUpService(config, logger, siteName)
        policer.startwork()


if __name__ == '__main__':
    execute(logger=getStreamLogger())
