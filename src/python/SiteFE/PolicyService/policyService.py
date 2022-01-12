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
import time
from rdflib import Graph
from rdflib import URIRef
from rdflib.plugins.parsers.notation3 import BadSyntax
from dateutil import parser
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.CustomExceptions import HostNotFound
from DTNRMLibs.CustomExceptions import UnrecognizedDeltaOption
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper  # TODO: Move to general

def getError(ex):
    """Get Error from Exception."""
    errors = {IOError: -1, KeyError: -2, AttributeError: -3, IndentationError: -4,
              ValueError: -5, BadSyntax: -6, HostNotFound: -7, UnrecognizedDeltaOption: -8}
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
        self.dbI = getDBConn('PolicyService', self)
        self.stateMachine = StateMachine(self.logger, self.config)
        self.hosts = getAllHosts(self.sitename, self.logger)
        for siteName in self.config.get('general', 'sites').split(','):
            workDir = os.path.join(self.config.get(siteName, 'privatedir'), "PolicyService/")
            createDirs(workDir)

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


    def queryGraph(self, graphIn, sub=None, pre=None, obj=None, search=None, allowMultiple=False):
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
                raise Exception('Search returned multiple entries. Not Supported. Out: %s' % foundItems)
        return foundItems

    def getTimeScheduling(self, gIn, connectionID, connOut):
        """Identifying lifetime of the service.
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'], 'existsDuring')))
        for timeline in out:
            times = connOut.setdefault('_params', {}).setdefault('existsDuring', {})
            for timev in ['end', 'start']:
                tout = self.queryGraph(gIn, timeline, search=URIRef('%s%s' % (self.prefixes['nml'], timev)))
                temptime = None
                try:
                    temptime = int(time.mktime(parser.parse(str(tout[0])).timetuple()))
                    if time.daylight:
                        temptime -= 3600
                except Exception:
                    continue
                times[timev] = temptime

    def parseDeltaRequest(self, inFileName):
        """Parse delta request to json."""
        self.logger.info("Parsing delta request %s ", inFileName)
        out = {}
        gIn = Graph()
        gIn.parse(inFileName, format='turtle')
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
        import pprint
        pprint.pprint(out)
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
        for tag, pref in {'tag': 'mrs', 'belongsTo': 'nml'}.items():
            out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes[pref], tag)))
            if out:
                scanVals[tag] = str(out[0])


    def _hasLabel(self, gIn, bidPort, returnout):
        returnout = self.intOut(bidPort, returnout)
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['nml'], 'hasLabel')))
        for item in out:
            scanVals = returnout.setdefault('hasLabel', {})
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['nml'], 'labeltype')))
            if out:
                scanVals['labeltype'] = out[0][len(self.prefixes['site']):]
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['nml'], 'value')))
            if out:
                scanVals['value'] = int(out[0])

    def _hasService(self, gIn, bidPort, returnout):
        returnout = self.intOut(bidPort, returnout)
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['nml'], 'hasService')))
        for item in out:
            scanVals = returnout.setdefault('hasService', {})
            for key in ['availableCapacity', 'granularity', 'maximumCapacity',
                        'priority', 'reservableCapacity', 'type', 'unit']:
                out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], key)))
                if out:
                    try:
                        scanVals[key] = int(out[0])
                    except ValueError:
                        scanVals[key] = str(out[0])


    def _hasNetwork(self, gIn, bidPort, returnout):
        returnout = self.intOut(bidPort, returnout)
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (self.prefixes['mrs'], 'hasNetworkAddress')))
        for item in out:
            scanVals = returnout.setdefault('hasNetworkAddress', {})
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'type')), allowMultiple=True)
            if out:
                scanVals['type'] = "|".join([str(item) for item in out])
            out = self.queryGraph(gIn, item, search=URIRef('%s%s' % (self.prefixes['mrs'], 'value')))
            if out:
                scanVals['value'] = str(out[0])


    def _recordSubnet(self, subnet, returnout):
        returnout = self.intOut(subnet, returnout.setdefault('SubnetMapping', {}))
        returnout.setdefault('providesSubnet', {})
        returnout['providesSubnet'][str(subnet)] = ""

    def parsePorts(self, bidPorts, gIn, connectionID):
        """ Get all ports for any connection and scan all of them """
        tmpPorts = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'],
                                                                              'hasBidirectionalPort')), allowMultiple=True)
        tmpPorts += self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (self.prefixes['nml'],
                                                                               'isAlias')), allowMultiple=True)
        for port in bidPorts:
            if port in tmpPorts:
                tmpPorts.remove(port)
        return tmpPorts


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
            bidPorts = []
            bidPorts += self.parsePorts(bidPorts, gIn, connectionID)
            # Get time scheduling details for connection.
            self.getTimeScheduling(gIn, connectionID, connOut)
            # =======================================================
            for bidPort in bidPorts:
                self.intOut(bidPort, connOut)
                self._hasTags(gIn, bidPort, connOut)
                bidPorts += self.parsePorts(bidPorts, gIn, bidPort)
                self._hasLabel(gIn, bidPort, connOut)
                self._hasService(gIn, bidPort, connOut)
                self._hasNetwork(gIn, bidPort, connOut)
        return returnout

    def startwork(self):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        # Committed to activating...
        # committing, committed, activating, activated, remove, removing, cancel
        dbobj = getVal(self.dbI, sitename=self.sitename)
        for job in [['committing', self.stateMachine.committing],
                    ['committed', self.stateMachine.committed],
                    ['activating', self.stateMachine.activating],
                    ['activated', self.stateMachine.activated],
                    ['removal', self.stateMachine.removing]]:
            self.logger.info("Starting check on %s deltas" % job[0])
            job[1](dbobj)

    def acceptDelta(self, deltapath):
        """Accept delta."""
        self.hosts = getAllHosts(self.sitename, self.logger)
        self.getSavedPrefixes(self.hosts.keys())
        deltapath = self.siteDB.moveFile(deltapath,
                                         os.path.join(self.config.get(self.sitename, 'privatedir'), "PolicyService/"))
        fileContent = self.siteDB.getFileContentAsJson(deltapath)
        self.logger.info('Called Accept Delta. Content Location: %s', deltapath)
        toDict = dict(fileContent)
        toDict["State"] = "accepting"
        outputDict = {'addition': '', 'reduction': ''}
        try:
            for key in ['reduction', 'addition']:
                if key in toDict["Content"] and toDict["Content"][key]:
                    self.logger.debug('Got Content %s for key %s', toDict["Content"][key], key)
                    tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
                    try:
                        tmpFile.write(toDict["Content"][key])
                    except ValueError as ex:
                        self.logger.info('Received ValueError. More details %s. Try to write normally with decode', ex)
                        tmpFile.write(decodebase64(toDict["Content"][key]))
                    tmpFile.close()
                    outputDict[key] = self.parseDeltaRequest(tmpFile.name)
                    os.unlink(tmpFile.name)
        #except (IOError, KeyError, AttributeError, IndentationError, ValueError,
        #        BadSyntax, HostNotFound, UnrecognizedDeltaOption) as ex:
        except IOError as ex:
            outputDict = getError(ex)
        dbobj = getVal(self.dbI, sitename=self.sitename)
        if 'errorType' in outputDict or \
        ('ParsedDelta' in outputDict and 'errorType' in outputDict['ParsedDelta']):
            toDict["State"] = "failed"
            toDict["Error"] = outputDict
            toDict['ParsedDelta'] = {'addition': '', 'reduction': ''}
            self.stateMachine.failed(dbobj, toDict)
        else:
            toDict["State"] = "accepted"
            connID = []
            toDict["ParsedDelta"] = outputDict
            toDict['modadd'] = 'idle'
            for key in outputDict:
                if not outputDict[key]:
                    continue
                toDict['Type'] = 'modify' if 'Type' in toDict.keys() else key
                # In case of modify, only addition connection IDs are stored;
                # otherwise, corresponding type connectionIDs
                if toDict['Type'] == 'modify':
                    raise Exception('Modify stopped support. Need review.')
                    # TODO: Modify not supported now as we change model generation.
                    # TODO: Review how modify is handled
                    #connID = []
                    #for item in outputDict['addition']:
                    #   connID.append(item['connectionID'])
                else:
                    for svc in ['vsw', 'rst']:
                        if svc not in outputDict[key]:
                            continue
                        for item in outputDict[key][svc]:
                            connID.append(item)
            toDict['ConnID'] = connID
            self.stateMachine.accepted(dbobj, toDict)
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
        policer.acceptDelta(args[1])
        #print(policer.parseDeltaRequest(args[1], {args[2]: []}))
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
