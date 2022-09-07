#!/usr/bin/env python3
"""
Policy Service which manipulates delta, connection states in DB.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import os
import sys
import copy
import tempfile
import pprint
import time
import argparse
from rdflib import Graph
from rdflib import URIRef
from rdflib.plugins.parsers.notation3 import BadSyntax
from dateutil import parser
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.MainUtilities import getCurrentModel, getActiveDeltas, writeActiveDeltas
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.CustomExceptions import OverlapException
from SiteFE.PolicyService.deltachecks import ConflictChecker
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper  # TODO: Move to general

def getError(ex):
    """Get Error from Exception."""
    errors = {IOError: -1, KeyError: -2, AttributeError: -3, IndentationError: -4,
              ValueError: -5, BadSyntax: -6, OverlapException: -7}
    out = {'errType': 'Unrecognized', 'errNo': -100, 'errMsg': 'Unset'}
    out['errType'] = str(ex.__class__)
    if ex.__class__ in errors:
        out['errNo'] = str(errors[ex.__class__])
    if hasattr(ex, 'message'):
        out['errMsg'] = ex.message
    else:
        out['errMsg'] = str(ex)
    return out

class PolicyService(RDFHelper):
    """Policy Service to accept deltas."""
    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='PolicyService')
        self.siteDB = contentDB(config=self.config)
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        self.stateMachine = StateMachine(self.config)
        self.hosts = {}
        for siteName in self.config.get('general', 'sites'):
            workDir = os.path.join(self.config.get(siteName, 'privatedir'), "PolicyService/")
            createDirs(workDir)
        self.getSavedPrefixes(self.hosts.keys())
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []
        self.conflictChecker = ConflictChecker()
        self.currentActive = getActiveDeltas(self)
        self.newActive = {}
        self._refreshHosts()

    def _refreshHosts(self):
        """Refresh all hosts informations"""
        self.hosts = {}
        for host, hostDict in getAllHosts(self.sitename, self.logger).items():
            self.hosts.setdefault(host, hostDict)
            self.hosts[host]['hostinfo'] = evaldict(hostDict['hostinfo'])

    def __clean(self):
        """Clean params of PolicyService"""
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []

    def intOut(self, inport, out):
        """
        SetDefault for out hostname, port, server, interface and use
        in output dictionary.
        """
        tmp = [_f for _f in str(inport)[len(self.prefixes['site']):].split(':') if _f]
        for item in tmp:
            if not len(item.split('+')) > 1:
                out = out.setdefault(item, {})
        return out

    def addIsAlias(self, gIn, bidPort, returnout):
        """Add is Alias to activeDeltas output"""
        del gIn
        if 'isAlias' in self.bidPorts.get(URIRef(bidPort), []) or 'isAlias' in self.scannedPorts.get(bidPort, []):
            returnout['isAlias'] = str(bidPort)

    def queryGraph(self, graphIn, sub=None, pre=None, obj=None, search=None, allowMultiple=True):
        """Search inside the graph based on provided parameters."""
        foundItems = []
        self.logger.debug(f'Searching for subject: {sub} predica: {pre} object: {obj} searchLine: {search}')
        for sIn, pIn, oIn in graphIn.triples((sub, pre, obj)):
            if search:
                if search == pIn:
                    self.logger.debug('Found item with search parameter')
                    self.logger.debug(f"s(subject) {sIn}")
                    self.logger.debug(f"p(predica) {pIn}")
                    self.logger.debug(f"o(object ) {oIn}")
                    self.logger.debug("-" * 50)
                    foundItems.append(oIn)
            else:
                self.logger.debug('Found item without search parameter')
                self.logger.debug(f"s(subject) {sIn}")
                self.logger.debug(f"p(predica) {pIn}")
                self.logger.debug(f"o(object ) {oIn}")
                self.logger.debug("-" * 50)
                foundItems.append(oIn)
        if not allowMultiple:
            if len(foundItems) > 1:
                #return foundItems
                raise Exception(f'Search returned multiple entries. Not Supported. Out: {foundItems}')
        return foundItems

    def getTimeScheduling(self, gIn, connectionID, connOut):
        """Identifying lifetime of the service.
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}{'existsDuring'}"))
        for timeline in out:
            times = connOut.setdefault('_params', {}).setdefault('existsDuring', {'uri': str(timeline)})
            for timev in ['end', 'start']:
                tout = self.queryGraph(gIn, timeline, search=URIRef(f"{self.prefixes['nml']}{timev}"))
                temptime = None
                try:
                    temptime = int(time.mktime(parser.parse(str(tout[0])).timetuple()))
                except Exception:
                    temptime = int(tout[0])
                if time.daylight:
                    temptime -= 3600
                times[timev] = temptime

    def parseModel(self, gIn):
        """Parse delta request and generateout"""
        self.__clean()
        out = {}
        for key in ['vsw', 'rst']:
            for switchName in self.config.get(self.sitename, 'switch'):
                if switchName not in self.prefixes.get(key, {}):
                    self.logger.debug('Warning: %s parameter is not defined for %s.', key, switchName)
                    continue
                self.prefixes['main'] = self.prefixes[key][switchName]
                if key == 'vsw':
                    self.logger.info('Parsing L2 information from model')
                    self.parsel2Request(gIn, out, switchName)
                elif key == 'rst':
                    self.logger.info('Parsing L3 information from model')
                    self.parsel3Request(gIn, out, switchName)
        return out

    def getRoute(self, gIn, connID, returnout):
        """Get all routes from model for specific connID"""
        returnout.setdefault('hasRoute', {})
        routeout = returnout['hasRoute'].setdefault(str(connID), {})
        if str(connID) in self.scannedRoutes:
            return str(connID)
        for rtype in ['nextHop', 'routeFrom', 'routeTo']:
            out = self.queryGraph(gIn, connID, search=URIRef(f"{self.prefixes['mrs']}{rtype}"))
            for item in out:
                mrstypes = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{'type'}"))
                mrsvals = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{'value'}"))
                if mrstypes and mrsvals and len(mrstypes) == len(mrsvals):
                    for ind in range(len(mrstypes)):
                        mrtype = str(mrstypes[ind])
                        mrval = str(mrsvals[ind])
                        if mrtype and mrval:
                            routeVals = routeout.setdefault(rtype, {}).setdefault(mrtype, {})
                            routeVals['type'] = mrtype
                            routeVals['value'] = mrval
                            routeVals['key'] = str(item)
                else:
                    self.logger.warning(f'Either val or type not defined. Key: {str(item)}, Type: {mrstypes}, Val: {mrsvals}')
        self.scannedRoutes.append(str(connID))
        return ""

    def getRouteTable(self, gIn, connID, returnout):
        """Get all route tables from model for specific connID and call getRoute"""
        out = self.queryGraph(gIn, connID, search=URIRef(f"{self.prefixes['mrs']}{'hasRoute'}"))
        tmpRet = []
        for item in out:
            tmpRet.append(self.getRoute(gIn, item, returnout))
        return tmpRet


    def parsel3Request(self, gIn, returnout, switchName):
        """Parse Layer 3 Delta Request."""
        self.logger.info(f"Lets try to get connection ID subject for {self.prefixes['main']}")
        connectionID = None
        for iptype in ['ipv4', 'ipv6']:
            uri = f"{self.prefixes['main']}-{iptype}"
            for rsttype in [{'key': 'providesRoute', 'call': self.getRoute},
                            {'key': 'providesRoutingTable', 'call': self.getRouteTable}]:
                out = self.queryGraph(gIn, URIRef(uri), search=URIRef(f"{self.prefixes['mrs']}{rsttype['key']}"))
                for connectionID in out:
                    if connectionID.startswith(f"{uri}:rt-table+vrf-") or \
                       connectionID.endswith('rt-table+main'):
                        # Ignoring default vrf and main table.
                        # This is not allowed to modify.
                        continue
                    self._recordMapping(connectionID, returnout, 'RoutingMapping', rsttype['key'], iptype)
                    returnout.setdefault('rst', {})
                    connOut = returnout['rst'].setdefault(str(connectionID), {}).setdefault(switchName, {}).setdefault(iptype, {})
                    self._hasService(gIn, connectionID, connOut)
                    connOut[rsttype['key']] = str(connectionID)
                    rettmp = rsttype['call'](gIn, connectionID, connOut)
                    if rettmp and rsttype['key'] == 'providesRoutingTable':
                        # We need to know mapping back, which route belongs to which routing table
                        # There is no such mapping in json, so we manually add this from providesRoutingTable
                        returnout['rst'].setdefault(str(rettmp[0]), {}).setdefault(switchName, {}).setdefault(iptype, {}).setdefault('belongsToRoutingTable', str(connectionID))

    def _hasTags(self, gIn, bidPort, returnout):
        """Query Graph and get Tags"""
        scanVals = returnout.setdefault('_params', {})
        for tag, pref in {'tag': 'mrs', 'belongsTo': 'nml', 'encoding': 'nml'}.items():
            out = self.queryGraph(gIn, bidPort, search=URIRef(f'{self.prefixes[pref]}{tag}'), allowMultiple=True)
            if out:
                scanVals[tag] = str("|".join(out))

    def _hasLabel(self, gIn, bidPort, returnout):
        """Query Graph and get Labels"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}{'hasLabel'}"))
        if not out and str(bidPort).rsplit(':', maxsplit=1)[-1].startswith('vlanport+'):
            # This is a hack, because Orchestrator does not provide full info
            # In future - we should merge delta with model, and parse only delta info
            # from full model.
            scanVals = returnout.setdefault('hasLabel', {})
            scanVals['labeltype'] = 'ethernet#vlan'
            scanVals['value'] = int(str(bidPort).rsplit(':', maxsplit=1)[-1][9:])
        for item in out:
            scanVals = returnout.setdefault('hasLabel', {})
            out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['nml']}{'labeltype'}"))
            if out:
                scanVals['labeltype'] = 'ethernet#vlan'
            out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['nml']}{'value'}"))
            if out:
                scanVals['value'] = int(out[0])

    def _hasService(self, gIn, bidPort, returnout):
        """Query Graph and get Services"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}{'hasService'}"))
        for item in out:
            scanVals = returnout.setdefault('hasService', {})
            scanVals['bwuri'] = str(item)
            self.getTimeScheduling(gIn, item, returnout)
            for key in ['availableCapacity', 'granularity', 'maximumCapacity',
                        'priority', 'reservableCapacity', 'type', 'unit']:
                out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{key}"))
                if out:
                    try:
                        scanVals[key] = int(out[0])
                    except ValueError:
                        scanVals[key] = str(out[0])

    def _hasNetwork(self, gIn, bidPort, returnout):
        """Query Graph and get hasNetworkAddress"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['mrs']}{'hasNetworkAddress'}"))
        for item in out:
            scanVals = returnout.setdefault('hasNetworkAddress', {})
            # We only add params we care, which are: ipv4-address, ipv6-address
            name = str(item).rsplit(':', maxsplit=1)[-1].split('+')[0]
            if name in ['ipv4-address', 'ipv6-address']:
                vals = scanVals.setdefault(name, {})
                out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{'type'}"),
                                      allowMultiple=True)
                if out:
                    vals['type'] = "|".join([str(item) for item in out])
                out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{'value'}"))
                if out:
                    vals['value'] = str(out[0])

    def _recordMapping(self, subnet, returnout, mappingKey, subKey, val = ""):
        """Query Graph and add all mappings"""
        returnout = self.intOut(subnet, returnout.setdefault(mappingKey, {}))
        returnout.setdefault(subKey, {})
        returnout[subKey].setdefault(str(subnet), {})
        returnout[subKey][str(subnet)][val] = ""

    def parsePorts(self, gIn, connectionID, connOut):
        """Get all ports for any connection and scan all of them"""
        for key in ['hasBidirectionalPort', 'isAlias']:
            tmpPorts = self.queryGraph(gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}{key}"), allowMultiple=True)
            for port in tmpPorts:
                if port not in self.bidPorts and port not in self.scannedPorts:
                    self.bidPorts.setdefault(port, [])
                    self.bidPorts[port].append(key)
                if port in self.scannedPorts:
                    self.scannedPorts[port].append(key)
                if key == 'isAlias':
                    connOut['isAlias'] = str(port)

    def _portScanFinish(self, bidPort):
        """Check if port was already scanned"""
        if bidPort not in self.scannedPorts:
            self.scannedPorts[bidPort] = self.bidPorts[bidPort]
        if bidPort in self.bidPorts:
            del self.bidPorts[bidPort]


    def parsel2Request(self, gIn, returnout, switchName):
        """Parse L2 request."""
        del switchName
        self.logger.info(f"Lets try to get connection ID subject for {self.prefixes['main']}")
        connectionID = None
        out = self.queryGraph(gIn, URIRef(self.prefixes['main']),
                              search=URIRef(f"{self.prefixes['mrs']}providesSubnet"))
        for connectionID in out:
            self._recordMapping(connectionID, returnout, 'SubnetMapping', 'providesSubnet')
            returnout.setdefault('vsw', {})
            connOut = returnout['vsw'].setdefault(str(connectionID), {})
            self._hasTags(gIn, connectionID, connOut)
            self.logger.info(f'This is our connection ID: {connectionID}')
            out = self.queryGraph(gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}{'labelSwapping'}"))
            if out:
                connOut.setdefault('_params', {}).setdefault('labelSwapping', str(out[0]))

            # Get All Ports
            self.parsePorts(gIn, connectionID, connOut)
            # Get time scheduling details for connection.
            self.getTimeScheduling(gIn, connectionID, connOut)
            # =======================================================
            while self.bidPorts:
                for bidPort in list(self.bidPorts.keys()):
                    # Preset defaults in out (hostname,port)
                    if not str(bidPort).startswith(self.prefixes['site']):
                        # For L3 - it can include other endpoint port,
                        # We dont need to parse that and it is isAlias in dict
                        self._portScanFinish(bidPort)
                        continue
                    portOut = self.intOut(bidPort, connOut)
                    # Parse all ports in port definition
                    self.parsePorts(gIn, bidPort, portOut)
                    # Get time scheduling information from delta
                    self.getTimeScheduling(gIn, bidPort, portOut)
                    # Get all tags for Port
                    self._hasTags(gIn, bidPort, portOut)
                    # Get All Labels
                    self._hasLabel(gIn, bidPort, portOut)
                    # Get all Services
                    self._hasService(gIn, bidPort, portOut)
                    # Get all Network address configs
                    self._hasNetwork(gIn, bidPort, portOut)
                    # Move port to finished scan ports
                    self._portScanFinish(bidPort)
        return returnout

    def generateActiveConfigDict(self, currentGraph):
        """Generate new config from parser model."""
        changesApplied = False
        self.currentActive = getActiveDeltas(self)
        self.newActive = copy.deepcopy(self.currentActive)
        modelParseRan = False
        for delta in self.dbI.get('deltas', limit=1, search=[['state', 'activating'], ['modadd', 'add']],
                                  orderby=['updatedate', 'DESC']):
            # Deltas keep string in DB, so we need to eval that
            # 1. Get delta content for reduction, addition
            # 2. Add into model and see if it overlaps with any
            delta['content'] = evaldict(delta['content'])
            for key in ['reduction', 'addition']:
                if delta.get("content", {}).get(key, {}):
                    tmpFile = ""
                    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                        tmpFile = fd.name
                        try:
                            fd.write(delta["content"][key])
                        except ValueError:
                            fd.write(decodebase64(delta["content"][key]))
                    gIn = Graph()
                    gIn.parse(tmpFile, format='turtle')
                    if key == 'reduction':
                        currentGraph -= gIn
                    elif key == 'addition':
                        currentGraph += gIn
                    os.unlink(tmpFile)
            # Now we parse new model and generate new currentActive config
            self.newActive['output'] = self.parseModel(currentGraph)
            modelParseRan = True
            # Now we ready to check if any of deltas overlap
            # if they do - means new delta should not be added
            # And we should get again clean model for next delta check
            try:
                self.conflictChecker.checkConflicts(self, self.newActive['output'], self.currentActive['output'])
                self.stateMachine._modelstatechanger(self.dbI, 'added', **delta)
                changesApplied = True
            except OverlapException as ex:
                self.stateMachine._modelstatechanger(self.dbI, 'failed', **delta)
                # If delta apply failed we return right away without writing new Active config
                self.logger.info(f"There was failure applying delta. Failure {ex}")
                # We return True, so model is regenerated again from scratch
                return True

        if not modelParseRan:
            self.newActive['output'] = self.parseModel(currentGraph)

        if self.newActive['output'] != self.currentActive['output']:
            writeActiveDeltas(self, self.newActive['output'])
            self.currentActive['output'] = copy.deepcopy(self.newActive['output'])
        # 3. Check if any delta expired, remove it from dictionary
        self.logger.info('Conflict Check of expired entities')
        newconf, cleaned = self.conflictChecker.checkActiveConfig(self.currentActive['output'])
        if cleaned:
            self.logger.info('IMPORTANT: State changed. Writing new config to DB.')
            self.currentActive['output'] = newconf
            writeActiveDeltas(self, self.currentActive['output'])
            changesApplied = True

        return changesApplied


    def startwork(self, currentGraph):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        self.__clean()
        # Committed to activating...
        # committing, committed, activating, activated, remove, removing, cancel
        # 1. First getall in activating, modadd or remove and apply to model
        # generate new out
        changesApplied = self.generateActiveConfigDict(currentGraph)
        for job in [['committing', self.stateMachine.committing],
                    ['committed', self.stateMachine.committed],
                    ['activating', self.stateMachine.activating],
                    ['activated', self.stateMachine.activated],
                    ['remove', self.stateMachine.remove],
                    ['removed', self.stateMachine.removed]]:
            self.logger.info(f"Starting check on {job[0]} deltas")
            job[1](self.dbI)
        return changesApplied

    def deltaToModel(self, currentGraph, deltaPath, action):
        """Add delta to current Model. If no delta provided, returns current Model"""
        if not currentGraph:
            _, currentGraph = getCurrentModel(self, True)
            self._refreshHosts()
            self.getSavedPrefixes(self.hosts.keys())
        if deltaPath and action:
            gIn = Graph()
            gIn.parse(deltaPath, format='turtle')
            if action == 'reduction':
                currentGraph -= gIn
            elif action == 'addition':
                currentGraph += gIn
            else:
                raise Exception(f'Unknown delta action. Action submitted {action}')
        return currentGraph


    def acceptDelta(self, deltapath):
        """Accept delta."""
        self._refreshHosts()
        currentGraph = self.deltaToModel(None, None, None)
        self.currentActive = getActiveDeltas(self)
        self.newActive = {'output': {}}
        deltapath = self.siteDB.moveFile(deltapath,
                                         os.path.join(self.config.get(self.sitename, 'privatedir'), "PolicyService/"))
        fileContent = self.siteDB.getFileContentAsJson(deltapath)
        self.logger.info(f'Called Accept Delta. Content Location: {deltapath}')
        toDict = dict(fileContent)
        toDict["State"] = "accepting"
        toDict['Type'] = 'submission'
        toDict['modadd'] = 'idle'
        try:
            for key in ['reduction', 'addition']:
                if toDict.get("Content", {}).get(key, {}):
                    self.logger.debug(f"Got Content {toDict['Content'][key]} for key {key}")
                    tmpFile = ""
                    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                        tmpFile = fd.name
                        try:
                            fd.write(toDict["Content"][key])
                        except ValueError:
                            fd.write(decodebase64(toDict["Content"][key]))
                    currentGraph = self.deltaToModel(currentGraph, tmpFile, key)
                    os.unlink(tmpFile)
            self.newActive['output'] = self.parseModel(currentGraph)
            try:
                self.conflictChecker.checkConflicts(self, self.newActive['output'], self.currentActive['output'])
            except OverlapException as ex:
                self.logger.info(f"There was failure accepting delta. Failure {ex}")
                toDict["State"] = "failed"
                toDict["Error"] = getError(ex)
                self.stateMachine.failed(self.dbI, toDict)
                return toDict
        except IOError as ex:
            toDict["State"] = "failed"
            toDict["Error"] = getError(ex)
            self.stateMachine.failed(self.dbI, toDict)
        else:
            toDict["State"] = "accepted"
            self.stateMachine.accepted(self.dbI, toDict)
            # =================================
        return toDict


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if args:
        if args.sitename:
            policer = PolicyService(config, args.sitename)
            if args.action == 'accept':
                out = policer.acceptDelta(args.delta)
                pprint.pprint(out)
            elif args.action in ['addition', 'reduction']:
                newModel = policer.deltaToModel(None, args.delta, args.action)
                out = policer.parseModel(newModel)
                pprint.pprint(out)
        elif args.action == 'fullRun':
            for sitename in config.get('general', 'sites'):
                policer = PolicyService(config, sitename)
                currentGraph = policer.deltaToModel(None, None, None)
                policer.startwork(currentGraph)

def get_parser():
    """Returns the argparse parser."""
    # pylint: disable=line-too-long
    oparser = argparse.ArgumentParser(description="This daemon is used for delta reduction, addition parsing",
                                      prog=os.path.basename(sys.argv[0]), add_help=True)
    # Main arguments
    oparser.add_argument('--action', dest='action', default='', help='Actions to execute. Options: [accept, addition, reduction, fullRun]')
    oparser.add_argument('--sitename', dest='sitename', default='',  help='Sitename of FE. Must be present in configuration and database.')
    oparser.add_argument('--delta', dest='delta', default='', help='Delta path. In case of accept action - need to be json format from DB. Otherwise - delta from Orchestrator')
    return oparser

if __name__ == '__main__':
    argparser = get_parser()
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    if len(sys.argv) == 1:
        argparser.print_help()
    inargs = argparser.parse_args(sys.argv[1:])
    getLoggingObject(logType='StreamLogger', service='PolicyService')
    execute(args=inargs)
