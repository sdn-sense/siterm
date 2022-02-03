#!/usr/bin/env python3
"""
Policy Service which manipulates delta, connection states in DB.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import os
import sys
import tempfile
import pprint
import time
from rdflib import Graph
from rdflib import URIRef
from rdflib.plugins.parsers.notation3 import BadSyntax
from dateutil import parser
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.MainUtilities import getCurrentModel, getActiveDeltas, writeActiveDeltas
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal
from SiteFE.PolicyService.deltachecks import ConflictChecker
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper  # TODO: Move to general

def getError(ex):
    """Get Error from Exception."""
    errors = {IOError: -1, KeyError: -2, AttributeError: -3, IndentationError: -4,
              ValueError: -5, BadSyntax: -6}
    out = {'errType': 'Unrecognized', 'errNo': -100, 'errMsg': 'Unset'}
    if ex.__class__ in list(errors.keys()):
        out['errType'] = str(ex.__class__)
        out['errNo'] = str(errors[ex.__class__])
    if hasattr(ex, 'message'):
        out['errMsg'] = ex.message
    return out

class PolicyService(RDFHelper):
    """Policy Service to accept deltas."""
    def __init__(self, config, logger, sitename):
        self.sitename = sitename
        self.logger = logger
        self.config = config
        self.siteDB = contentDB(logger=self.logger, config=self.config)
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        self.stateMachine = StateMachine(self.logger, self.config)
        self.hosts = getAllHosts(self.sitename, self.logger)
        for siteName in self.config.get('general', 'sites').split(','):
            workDir = os.path.join(self.config.get(siteName, 'privatedir'), "PolicyService/")
            createDirs(workDir)
        self.getSavedPrefixes(self.hosts.keys())
        self.bidPorts = {}
        self.scannedPorts = {}
        self.conflictChecker = ConflictChecker()

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
        """ Add is Alias to activeDeltas output """
        if 'isAlias' in self.bidPorts.get(URIRef(bidPort), []) or 'isAlias' in self.scannedPorts.get(bidPort, []):
            returnout['isAlias'] = str(bidPort)

    def queryGraph(self, graphIn, sub=None, pre=None, obj=None, search=None, allowMultiple=True):
        """Search inside the graph based on provided parameters."""
        foundItems = []
        self.logger.debug('Searching for subject: %s predica: %s object: %s searchLine: %s' % (sub, pre, obj, search))
        for sIn, pIn, oIn in graphIn.triples((sub, pre, obj)):
            if search:
                if search == pIn:
                    self.logger.debug('Found item with search parameter')
                    self.logger.debug("s(subject) %s" % sIn)
                    self.logger.debug("p(predica) %s" % pIn)
                    self.logger.debug("o(object ) %s" % oIn)
                    self.logger.debug("-" * 50)
                    foundItems.append(oIn)
            else:
                self.logger.debug('Found item without search parameter')
                self.logger.debug("s(subject) %s" % sIn)
                self.logger.debug("p(predica) %s" % pIn)
                self.logger.debug("o(object ) %s" % oIn)
                self.logger.debug("-" * 50)
                foundItems.append(oIn)
        if not allowMultiple:
            if len(foundItems) > 1:
                #return foundItems
                raise Exception('Search returned multiple entries. Not Supported. Out: %s' % foundItems)
        return foundItems

    def getTimeScheduling(self, gIn, connectionID, connOut):
        """Identifying lifetime of the service.
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'], 'existsDuring')))
        for timeline in out:
            times = connOut.setdefault('_params', {}).setdefault('existsDuring', {'uri': str(timeline)})
            for timev in ['end', 'start']:
                tout = self.queryGraph(gIn, timeline, search=URIRef('%s%s' % (self.prefixes['nml'], timev)))
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
        out = {}
        for key in ['vsw', 'rst']:
            for switchName in self.config.get(self.sitename, 'switch').split(','):
                if switchName not in self.prefixes[key]:
                    self.logger.debug('ERROR: %s parameter is not defined for %s.', key, switchName)
                    continue
                self.prefixes['main'] = self.prefixes[key][switchName]
                if key == 'vsw':
                    self.logger.info('Parsing L2 information from delta')
                    self.parsel2Request(gIn, out)
                elif key == 'rst':
                    self.logger.info('Parsing L3 information from delta')
                    self.parsel3Request(gIn, out)
        self.logger.info(pprint.pprint(out))
        return out

    def parsel3Request(self, gIn, returnout):
        """Parse Layer 3 Delta Request."""
        # TODO Rewrite.
        return
        # for hostname in list(self.hosts.keys()):
        #     self.prefixes['mainrst'] = URIRef("%s:%s:service+rst" % (self.prefixes['site'], hostname))
        #     self.logger.info('Lets try to get connection ID subject for %s' % self.prefixes['mainrst'])
        #     out = self.queryGraph(gIn, self.prefixes['mainrst'],
        #                           search=URIRef('%s%s' % (self.prefixes['mrs'], 'providesRoutingTable')))
        #     if not out:
        #         msg = 'Connection ID was not received. Continue'
        #         self.logger.info(msg)
        #         continue
        #     outall = {'hosts': {}}
        #     outall['hosts'].setdefault(hostname, {})
        #     for connectionID in out:
        #         outall['connectionID'] = str(connectionID)
        #         outall['hosts'][hostname]['routes'] = []
        #         self.logger.info('This is our connection ID: %s' % connectionID)
        #         self.logger.info('Now lets get all info what it wants to do. Mainly nextHop, routeFrom, routeTo')
        #         bidPorts = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['mrs'], 'hasRoute')))
        #         for bidPort in bidPorts:
        #             route = {}
        #             for flag in ['nextHop', 'routeFrom', 'routeTo']:
        #                 route.setdefault(flag, {})
        #                 out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['mrs'], flag)))
        #                 if not out:
        #                     continue
        #                 for item in out:
        #                     outt = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'type')))
        #                     outv = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'value')))
        #                     if not outt or not outv:
        #                         continue
        #                     route[flag]['type'] = str(outt[0])
        #                     route[flag]['value'] = str(outv[0])
        #             outall['hosts'][hostname]['routes'].append(route)
        #         returnout.append(outall)
        #         self.logger.debug('L3 Parse output: %s', outall)
        # return returnout

    def _hasTags(self, gIn, bidPort, returnout):
        scanVals = returnout.setdefault('_params', {})
        for tag, pref in {'tag': 'mrs', 'belongsTo': 'nml', 'encoding': 'nml'}.items():
            out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes[pref], tag)), allowMultiple=True)
            if out:
                if str("|".join(out)) == 'urn:ogf:network:ultralight.org:2013:dellos9_s0:service+vsw:conn+5869f374-66c4-4402-b5da-2627f0c9e39e:resource+links-Connection_1:vlan+3603|urn:ogf:network:ultralight.org:2013:dellos9_s0:service+vsw':
                    import pdb; pdb.set_trace()
                    scanVals[tag] = 'urn:ogf:network:ultralight.org:2013:dellos9_s0:service+vsw'
                else:
                    scanVals[tag] = str("|".join(out))

    def _hasLabel(self, gIn, bidPort, returnout):
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['nml'], 'hasLabel')))
        if not out and str(bidPort).rsplit(':', maxsplit=1)[-1].startswith('vlanport+'):
            # This is a hack, because Orchestrator does not provide full info
            # In future - we should merge delta with model, and parse only delta info
            # from full model.
            scanVals = returnout.setdefault('hasLabel', {})
            scanVals['labeltype'] = 'ethernet#vlan'
            scanVals['value'] = int(str(bidPort).rsplit(':', maxsplit=1)[-1][9:])
        for item in out:
            scanVals = returnout.setdefault('hasLabel', {})
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['nml'], 'labeltype')))
            if out:
                scanVals['labeltype'] = out[0][len(self.prefixes['site']):]
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['nml'], 'value')))
            if out:
                scanVals['value'] = int(out[0])

    def _hasService(self, gIn, bidPort, returnout):
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['nml'], 'hasService')))
        for item in out:
            scanVals = returnout.setdefault('hasService', {})
            self.getTimeScheduling(gIn, item, returnout)
            for key in ['availableCapacity', 'granularity', 'maximumCapacity',
                        'priority', 'reservableCapacity', 'type', 'unit']:
                out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], key)))
                if out:
                    try:
                        scanVals[key] = int(out[0])
                    except ValueError:
                        scanVals[key] = str(out[0])

    def _hasNetwork(self, gIn, bidPort, returnout):
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['mrs'], 'hasNetworkAddress')))
        for item in out:
            scanVals = returnout.setdefault('hasNetworkAddress', {})
            # We only add params we care, which are: ipv4-address, ipv6-address
            name = str(item).rsplit(':', maxsplit=1)[-1].split('+')[0]
            if name in ['ipv4-address', 'ipv6-address']:
                vals = scanVals.setdefault(name, {})
                out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'type')),
                                      allowMultiple=True)
                if out:
                    vals['type'] = "|".join([str(item) for item in out])
                out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'value')))
                if out:
                    vals['value'] = str(out[0])

    def _recordSubnet(self, subnet, returnout):
        returnout = self.intOut(subnet, returnout.setdefault('SubnetMapping', {}))
        returnout.setdefault('providesSubnet', {})
        returnout['providesSubnet'][str(subnet)] = ""

    def parsePorts(self, gIn, connectionID, connOut):
        """ Get all ports for any connection and scan all of them """
        for key in ['hasBidirectionalPort', 'isAlias']:
            tmpPorts = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'], key)), allowMultiple=True)
            for port in tmpPorts:
                if port not in self.bidPorts and port not in self.scannedPorts:
                    self.bidPorts.setdefault(port, [])
                    self.bidPorts[port].append(key)
                if port in self.scannedPorts:
                    self.scannedPorts[port].append(key)
                if key == 'isAlias':
                    connOut['isAlias'] = str(port)

    def _portScanFinish(self, bidPort):
        if bidPort not in self.scannedPorts:
            self.scannedPorts[bidPort] = self.bidPorts[bidPort]
        if bidPort in self.bidPorts:
            del self.bidPorts[bidPort]


    def parsel2Request(self, gIn, returnout):
        """Parse L2 request."""
        self.logger.info('Lets try to get connection ID subject for %s' % self.prefixes['main'])
        connectionID = None
        out = self.queryGraph(gIn, URIRef(self.prefixes['main']), search=URIRef('%s%s' % (self.prefixes['mrs'],
                                                                                          'providesSubnet')))
        for connectionID in out:
            self._recordSubnet(connectionID, returnout)
            returnout.setdefault('vsw', {})
            connOut = returnout['vsw'].setdefault(str(connectionID), {})
            self._hasTags(gIn, connectionID, connOut)
            self.logger.info('This is our connection ID: %s' % connectionID)
            out = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'], 'labelSwapping')))
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

    def generateActiveConfigDict(self):
        _, currentGraph = getCurrentModel(self, True)
        currentActive = getActiveDeltas(self)
        for delta in self.dbI.get('deltas', search=[['state', 'activating'], ['modadd', 'add']]):
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
            newConfig = self.parseModel(currentGraph)
            # Now we ready to check if any of deltas overlap
            # if they do - means new delta should not be added
            # And we should get again clean model for next delta check
            if not self.conflictChecker.checkConflicts(self, newConfig, currentActive['output']):
                currentActive['output'] = newConfig
                currentActive = writeActiveDeltas(self, currentActive['output'])
                self.stateMachine._modelstatechanger(self.dbI, 'added', **delta)
            else:
                self.stateMachine._modelstatechanger(self.dbI, 'failed', **delta)

        newConfig = self.parseModel(currentGraph)
        # 3. Check if any delta expired, remove it from dictionary
        newconf, cleaned = self.conflictChecker.checkActiveConfig(currentActive['output'])

        import pprint
        pprint.pprint(newconf)
        import pdb; pdb.set_trace()
        if cleaned or not self.conflictChecker.checkConflicts(self, newconf, currentActive['output']):
            print(1)
            currentActive['output'] = newconf
            currentActive = writeActiveDeltas(self, currentActive['output'])

    def startwork(self):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        # Committed to activating...
        # committing, committed, activating, activated, remove, removing, cancel
        # 1. First getall in activating, modadd or remove and apply to model
        # generate new out
        self.generateActiveConfigDict()
        for job in [['committing', self.stateMachine.committing],
                    ['committed', self.stateMachine.committed],
                    ['activating', self.stateMachine.activating],
                    ['activated', self.stateMachine.activated]]:
            self.logger.info("Starting check on %s deltas" % job[0])
            job[1](self.dbI)

    def acceptDelta(self, deltapath):
        """Accept delta."""
        _, currentGraph = getCurrentModel(self, True)
        self.hosts = getAllHosts(self.sitename, self.logger)
        self.getSavedPrefixes(self.hosts.keys())
        deltapath = self.siteDB.moveFile(deltapath,
                                         os.path.join(self.config.get(self.sitename, 'privatedir'), "PolicyService/"))
        fileContent = self.siteDB.getFileContentAsJson(deltapath)
        self.logger.info('Called Accept Delta. Content Location: %s', deltapath)
        toDict = dict(fileContent)
        toDict["State"] = "accepting"
        try:
            for key in ['reduction', 'addition']:
                if toDict.get("Content", {}).get(key, {}):
                    self.logger.debug('Got Content %s for key %s', toDict["Content"][key], key)
                    tmpFile = ""
                    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                        tmpFile = fd.name
                        try:
                            fd.write(toDict["Content"][key])
                        except ValueError:
                            fd.write(decodebase64(toDict["Content"][key]))
                    gIn = Graph()
                    gIn.parse(tmpFile, format='turtle')
                    if key == 'reduction':
                        currentGraph -= gIn
                    elif key == 'addition':
                        currentGraph += gIn
                    os.unlink(tmpFile)
            self.parseModel(currentGraph)
        except IOError as ex:
            toDict["State"] = "failed"
            toDict["Error"] = getError(ex)
            self.stateMachine.failed(self.dbI, toDict)
        else:
            toDict["State"] = "accepted"
            toDict['modadd'] = 'idle'
            toDict['Type'] = 'submission'
            self.stateMachine.accepted(self.dbI, toDict)
            # =================================
        return toDict


def execute(config=None, logger=None, args=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if not logger:
        component = 'PolicyService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component),
                           config.get(component, 'logLevel'), True)

    if args:
        policer = PolicyService(config, logger, args[2])
        # This is only for debugging purposes.
        out = policer.acceptDelta(args[1])
        #out = policer.parseModel(args[1])
        pprint.pprint(out)
    else:
        for sitename in config.get('general', 'sites').split(','):
            policer = PolicyService(config, logger, sitename)
            policer.startwork()


if __name__ == '__main__':
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    print('If argv[1] is specified it will try to parse custom delta request. It should be a filename.')
    print('2rd argument has to be sitename which is configured in this frontend')
    print('Otherwise, it will check frontend for new deltas')
    print(sys.argv)
    if len(sys.argv) > 2:
        execute(args=sys.argv, logger=getStreamLogger())
    else:
        execute(logger=getStreamLogger())
