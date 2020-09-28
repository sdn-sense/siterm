#!/usr/bin/env python
"""
Policy Service which accepts deltas and applies them

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
"""
import os
import sys
import tempfile
import time
from rdflib import Graph
from rdflib import URIRef, Literal
from rdflib.plugins.parsers.notation3 import BadSyntax
from dateutil import parser
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.CustomExceptions import HostNotFound
from DTNRMLibs.CustomExceptions import UnrecognizedDeltaOption
from DTNRMLibs.FECalls import getAllHosts
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal
from SiteFE.PolicyService.stateMachine import StateMachine


def getError(ex):
    """ Get Error from Exception """
    errors = {IOError: -1, KeyError: -2, AttributeError: -3, IndentationError: -4,
              ValueError: -5, BadSyntax: -6, HostNotFound: -7, UnrecognizedDeltaOption: -8}
    errType = 'Unrecognized'
    errNo = '-100'
    if ex.__class__ in errors.keys():
        errType = str(ex.__class__)
        errNo = str(errors[ex.__class__])
    return {"errorType": errType,
            "errorNo": errNo,
            "errMsg": ex.message}


def getConnInfo(bidPort, prefixSite, output, nostore=False):
    """ Get Connection Info. Mainly ports. """
    nName = filter(None, bidPort[len(prefixSite):].split(':'))
    if nostore:
        return nName[2], output
    output.setdefault('hosts', {})
    output['hosts'].setdefault(nName[2], {})
    output['hosts'][nName[2]]['sourceport'] = nName[1]
    output['hosts'][nName[2]]['sourceswitch'] = nName[0]
    if len(nName) == 5:
        output['hosts'][nName[2]]['destport'] = nName[3]
    elif len(nName[-1].split('.')) == 2:
        if 'destport' not in output[nName[2]].keys():
            output['hosts'][nName[2]]['destport'] = nName[-1].split('.')[0]
    return nName[2], output


class PolicyService(object):
    """ Policy Service to accept deltas """
    def __init__(self, config, logger, sitename):
        self.sitename = sitename
        self.logger = logger
        self.config = config
        self.siteDB = contentDB(logger=self.logger, config=self.config)
        self.dbI = getDBConn()
        self.stateMachine = StateMachine(self.logger)

    def queryGraph(self, graphIn, sub=None, pre=None, obj=None, search=None):
        """ Does search inside the graph based on provided parameters """
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
        return foundItems

    def getTimeScheduling(self, out, gIn, prefixes):
        """ This is for identifying LIFETIME! In case it fails to get correct timestamp,
            resources will be provisioned right away
        """
        for timeline in out:
            times = {}
            for timev in ['end', 'start']:
                tout = self.queryGraph(gIn, timeline, search=URIRef('%s%s' % (prefixes['nml'], timev)))
                temptime = None
                try:
                    temptime = int(time.mktime(parser.parse(str(tout[0])).timetuple()))
                    if time.daylight:
                        temptime -= 3600
                except Exception:
                    continue
                times[timev] = temptime
            if len(times.keys()) == 2:
                return times
        return {}

    def parseDeltaRequest(self, inFileName, allKnownHosts):
        """Parse delta request to json"""
        self.logger.info("Parsing delta request %s ", inFileName)
        prefixes = {}
        prefixes['site'] = "%s:%s:%s" % (self.config.get('prefixes', 'site'),
                                         self.config.get(self.sitename, 'domain'),
                                         self.config.get(self.sitename, 'year'))
        prefixes['main'] = URIRef("%s:service+vsw" % prefixes['site'])
        prefixes['nml'] = self.config.get('prefixes', 'nml')
        prefixes['mrs'] = self.config.get('prefixes', 'mrs')
        gIn = Graph()
        gIn.parse(inFileName, format='turtle')
        out = []
        self.logger.info('Trying to parse L2 info from delta')
        out = self.parsel2Request(allKnownHosts, prefixes, gIn, out)
        self.logger.info('Trying to parse L3 info from delta')
        out = self.parsel3Request(allKnownHosts, prefixes, gIn, out)
        return out

    def parsel3Request(self, allKnownHosts, prefixes, gIn, returnout):
        """ Parse Layer 3 Delta Request """
        for hostname in allKnownHosts.keys():
            prefixes['mainrst'] = URIRef("%s:%s:service+rst" % (prefixes['site'], hostname))
            self.logger.info('Lets try to get connection ID subject for %s' % prefixes['mainrst'])
            out = self.queryGraph(gIn, prefixes['mainrst'],
                                  search=URIRef('%s%s' % (prefixes['mrs'], 'providesRoutingTable')))
            if not out:
                msg = 'Connection ID was not received. Continue'
                self.logger.info(msg)
                continue
            outall = {}
            outall.setdefault('hosts', {})
            outall['hosts'].setdefault(hostname, {})
            for connectionID in out:
                outall['connectionID'] = str(connectionID)
                outall['hosts'][hostname]['routes'] = []
                self.logger.info('This is our connection ID: %s' % connectionID)
                self.logger.info('Now lets get all info what it wants to do. Mainly nextHop, routeFrom, routeTo')
                bidPorts = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (prefixes['mrs'], 'hasRoute')))
                for bidPort in bidPorts:
                    route = {}
                    for flag in ['nextHop', 'routeFrom', 'routeTo']:
                        route.setdefault(flag, {})
                        out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (prefixes['mrs'], flag)))
                        if not out:
                            continue
                        for item in out:
                            outt = self.queryGraph(gIn, item, search=URIRef('%s%s' % (prefixes['mrs'], 'type')))
                            outv = self.queryGraph(gIn, item, search=URIRef('%s%s' % (prefixes['mrs'], 'value')))
                            if not outt or not outv:
                                continue
                            route[flag]['type'] = str(outt[0])
                            route[flag]['value'] = str(outv[0])
                    outall['hosts'][hostname]['routes'].append(route)
                returnout.append(outall)
                self.logger.debug('L3 Parse output: %s', outall)
        return returnout

    def parsel2Request(self, allKnownHosts, prefixes, gIn, returnout):
        """ Parse L2 request """
        self.logger.info('Lets try to get connection ID subject for %s' % prefixes['main'])
        connectionID = None
        out = self.queryGraph(gIn, prefixes['main'], search=URIRef('%s%s' % (prefixes['mrs'], 'providesSubnet')))
        if not out:
            msg = 'Connection ID was not received. Something is wrong...'
            self.logger.info(msg)
            return []
        for connectionID in out:
            output = {}
            output['connectionID'] = str(connectionID)
            self.logger.info('This is our connection ID: %s' % connectionID)
            self.logger.info('Now lets get all info what it wants to do. Mainly bidPorts and labelSwapping flag')
            bidPorts = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (prefixes['nml'],
                                                                                  'hasBidirectionalPort')))
            out = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (prefixes['nml'], 'labelSwapping')))
            output['labelSwapping'] = str(out[0])
            out = self.queryGraph(gIn, connectionID, search=URIRef('%s%s' % (prefixes['nml'], 'existsDuring')))
            out = self.getTimeScheduling(out, gIn, prefixes)
            if len(out.keys()) == 2:
                output['timestart'] = out['start']
                output['timeend'] = out['end']
            # =======================================================
            self.logger.info('Now lets get all info for each bidirectionalPort, like vlan, ip, serviceInfo ')
            # We need mainly hasLabel, hasNetworkAddress
            for bidPort in bidPorts:
                # Get first which labels it has. # This provides us info about vlan tag
                connInfo, output = getConnInfo(bidPort, prefixes['site'], output, nostore=True)
                if connInfo not in allKnownHosts:
                    print 'Ignore %s' % connInfo
                    continue
                connInfo, output = getConnInfo(bidPort, prefixes['site'], output)
                alias = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (prefixes['nml'], 'isAlias')))
                if alias and alias[0] not in bidPorts:
                    self.logger.info('Received alias for %s to %s' % (bidPort, alias))
                    bidPorts.append(alias[0])
                # Now let's get vlan ID
                out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (prefixes['nml'], 'hasLabel')))
                if not out:
                    continue
                out = self.queryGraph(gIn, out[0], search=URIRef('%s%s' % (prefixes['nml'], 'value')))
                output['hosts'][connInfo]['vlan'] = str(out[0])
                # Now Let's get IP
                out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (prefixes['mrs'], 'hasNetworkAddress')))
                for item in out:
                    outtype = self.queryGraph(gIn, item, search=URIRef('%s%s' % (prefixes['mrs'], 'type')))
                    outval = self.queryGraph(gIn, item, search=URIRef('%s%s' % (prefixes['mrs'], 'value')))
                    if Literal('ipv4-address') in outtype:
                        if len(outval[0].split('/')) == 2:
                            output['hosts'][connInfo]['ip'] = str(outval[0])
                # Now lets get service Info and what was requested.
                out = self.queryGraph(gIn, bidPort, search=URIRef('%s%s' % (prefixes['nml'], 'hasService')))
                output['hosts'][connInfo].setdefault('params', [])
                serviceparams = {}
                if out:
                    for key in ['availableCapacity', 'granularity', 'maximumCapacity',
                                'priority', 'reservableCapacity', 'type', 'unit']:
                        tmpout = self.queryGraph(gIn, out[0], search=URIRef('%s%s' % (prefixes['mrs'], key)))
                        if len(tmpout) >= 1:
                            serviceparams[key] = str(tmpout[0])
                output['hosts'][connInfo]['params'].append(serviceparams)
            returnout.append(output)
        return returnout

    def startwork(self):
        """ Start Policy Service """
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        for siteName in self.config.get('general', 'sites').split(','):
            workDir = self.config.get(siteName, 'privatedir') + "/PolicyService/"
            createDirs(workDir)
            self.logger.info('Working on Site %s' % siteName)
            self.startworkmain(siteName)
        # Committed to activating...
        # committing, committed, activating, activated, remove, removing, cancel
        dbobj = getVal(self.dbI, sitename=self.sitename)
        for job in [['committing', self.stateMachine.committing],
                    ['committed', self.stateMachine.committed],
                    ['activating', self.stateMachine.activating],
                    ['activated', self.stateMachine.activated],
                    ['remove', self.stateMachine.remove],
                    ['removing', self.stateMachine.removing],
                    ['cancel', self.stateMachine.cancel],
                    ['cancelConn', self.stateMachine.cancelledConnections]]:
            self.logger.info("Starting check on %s deltas" % job[0])
            job[1](dbobj)

    def acceptDelta(self, deltapath):
        """ Accept delta """
        jOut = getAllHosts(self.sitename, self.logger)
        fileContent = self.siteDB.getFileContentAsJson(deltapath)
        os.unlink(deltapath)  # File is not needed anymore.
        toDict = dict(fileContent)
        toDict["State"] = "accepting"
        outputDict = {'addition': '', 'reduction': ''}
        try:
            self.logger.info(toDict["Content"])
            self.logger.info(type(toDict["Content"]))
            for key in ['reduction', 'addition']:
                if key in toDict["Content"] and toDict["Content"][key]:
                    self.logger.info('Got Content %s for key %s', toDict["Content"][key], key)
                    tmpFile = tempfile.NamedTemporaryFile(delete=False)
                    try:
                        tmpFile.write(toDict["Content"][key])
                    except ValueError as ex:
                        self.logger.info('Received ValueError. More details %s. Try to write normally with decode', ex)
                        tmpFile.write(decodebase64(toDict["Content"][key]))
                    tmpFile.close()
                    outputDict[key] = self.parseDeltaRequest(tmpFile.name, jOut, self.sitename)
                    os.unlink(tmpFile.name)
        except (IOError, KeyError, AttributeError, IndentationError, ValueError,
                BadSyntax, HostNotFound, UnrecognizedDeltaOption) as ex:
            outputDict = getError(ex)
        dbobj = getVal(self.dbI, sitename=self.sitename)
        if 'errorType' in outputDict.keys():
            toDict["State"] = "failed"
            toDict["Error"] = outputDict
            toDict['ParsedDelta'] = {'addition': '', 'reduction': ''}
            self.stateMachine.failed(dbobj, toDict)
        else:
            toDict["State"] = "accepted"
            connID = None
            for key in outputDict:
                toDict["State"] = "accepted"
                if not outputDict[key]:
                    continue
                toDict['dtype'] = key
                toDict['Type'] = key
                self.logger.info('%s' % str(outputDict[key]))
                toDict["ParsedDelta"] = outputDict
                connID = []
                for item in outputDict[key]:
                    connID.append(item['connectionID'])
                toDict['ConnID'] = connID
                toDict['modadd'] = 'idle'
                self.stateMachine.accepted(dbobj, toDict)
            # =================================
        return toDict


def execute(config=None, logger=None, args=None):
    """Main Execute"""
    if not config:
        config = getConfig()
    if not logger:
        component = 'PolicyService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component),
                           config.get(component, 'logLevel'), True)

    policer = PolicyService(config, logger, args[3])
    if args:
        # This is only for debugging purposes.
        print policer.parseDeltaRequest(args[1], {args[2]: []}, args[3])
    else:
        policer.startwork()


if __name__ == '__main__':
    print 'WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.'
    print 'If argv[1] is specified it will try to parse custom delta request. It should be a filename.'
    print '2nd argument is hostname. You can find hostname inside the delta'
    print '3rd argument has to be sitename which is configured in this frontend'
    print 'Otherwise, it will check frontend for new deltas'
    print sys.argv
    if len(sys.argv) == 4:
        execute(args=sys.argv, logger=getStreamLogger())
    else:
        execute(logger=getStreamLogger())
