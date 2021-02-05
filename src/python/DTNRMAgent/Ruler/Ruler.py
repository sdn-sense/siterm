#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

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
Title             : dtnrm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2016 California Institute of Technology
Date            : 2017/09/26
"""
from __future__ import absolute_import
import os
import glob
import pprint
from DTNRMAgent.Ruler.QOS import QOS
from DTNRMAgent.Ruler.Components.VInterfaces import VInterfaces
from DTNRMLibs.MainUtilities import getDataFromSiteFE, evaldict, getStreamLogger
from DTNRMLibs.MainUtilities import createDirs, getFullUrl, contentDB, getFileContentAsJson
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand


COMPONENT = 'Ruler'


class Ruler():
    """Ruler class to create interfaces on the system."""
    def __init__(self, config, logger):
        self.config = config if config else getConfig()
        self.logger = logger if logger else getLogger("%s/%s/" % (self.config.get('general', 'logDir'), COMPONENT),
                                                      self.config.get('general', 'logLevel'))
        self.workDir = self.config.get('general', 'private_dir') + "/DTNRM/RulerAgent/"
        createDirs(self.workDir)
        self.fullURL = getFullUrl(self.config, self.config.get('general', 'siteName'))
        self.noRules = self.config.getboolean('agent', 'norules')
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Ruler Start Work. Hostname: %s", self.hostname)
        self.vInterface = VInterfaces(self.config, self.logger)

    def getData(self, url):
        """Get data from FE."""
        self.logger.info('Query: %s%s' % (self.fullURL, url))
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = 'Received a failure getting information from Site Frontend %s' % str(out)
            self.logger.critical(msg)
            return {}
        if self.config.getboolean('general', "debug"):
            pretty = pprint.PrettyPrinter(indent=4)
            pretty.pprint(evaldict(out[0]))
        self.logger.info('End function checkdeltas')
        return evaldict(out[0])

    def vlansProvisioned(self):
        """Get all VLANs provisioned and already in place."""
        out = []
        for fileName in glob.glob("%s/*.json" % self.workDir):
            inputDict = getFileContentAsJson(fileName)
            out.append(inputDict)
        return out

    def getHostStates(self, state):
        """Get All HostStates from Frontend."""
        return self.getData("/sitefe/v1/hostnameids/%s/%s" % (self.hostname, state))

    def getDeltaInfo(self, deltaid):
        """Get Delta information."""
        return self.getData("/sitefe/v1/deltas/%s?oldview=true" % deltaid)

    def setHostState(self, state, deltaid):
        """Push Internal action and return dict."""
        restOut = getDataFromSiteFE({}, self.fullURL, "/sitefe/v1/deltas/%s/internalaction/%s/%s" %
                                    (deltaid, self.hostname, state))
        if restOut[1] >= 400:
            self.logger.info("Failed to set new state in database for %s delta \
                             and %s hostname. Error %s " % (deltaid, self.hostname, restOut))
            raise FailedInterfaceCommand("Failed to set new state in database for %s delta \
                                         and %s hostname. Error %s " % (deltaid, self.hostname, restOut))
        return restOut

    def vlanCheck(self, addition):
        """Vlan parameters check and append."""
        if 'MTU' not in list(addition['hosts'][self.hostname].keys()):
            addition['hosts'][self.hostname]['MTU'] = 9000
        if 'txqueuelen' not in addition['hosts'][self.hostname]:
            addition['hosts'][self.hostname]['txqueuelen'] = 10000
        # We might want to do more checks here later.
        return addition

    def checkResources(self, addition, deltaID):
        """Check if IP, interfaces, routes are in place.

        if not, add's it.
        """
        if not self.noRules:
            self.logger.info('Addition info %s' % addition)
            try:
                self.vInterface.status(addition['hosts'][self.hostname], True)
                self.logger.debug('Resources are up and ok.')
            except FailedInterfaceCommand:
                self.logger.debug('State is active, but resources are not. Re-starting')
                addition['uid'] = deltaID
                addition = self.vlanCheck(addition)
                self.logger.info("Applying virtual interface rules. STATUS Failed")
                self.vInterface.add(addition['hosts'][self.hostname])
                self.vInterface.setup(addition['hosts'][self.hostname])
                self.vInterface.start(addition['hosts'][self.hostname])

    def activateResources(self, addition, deltaID):
        """Resources activation."""
        # Check if file present. If So, set failed and remove file!
        newvlanFile = self.workDir + "/%s.json" % deltaID
        addition['uid'] = deltaID
        if os.path.isfile(newvlanFile):
            if not self.noRules:
                self.logger.info("Removing virtual interface rules file. Add it again by call from FE")
                self.vInterface.stop(addition['hosts'][self.hostname])
                self.vInterface.remove(addition['hosts'][self.hostname])
            os.unlink(newvlanFile)
            # return True, "This delta was already on the system. Cancel it."
        if self.hostname not in list(addition['hosts'].keys()):
            return False, "Failed to find own hostname in dictionary"
        addition = self.vlanCheck(addition)
        self.logger.info("Saving file %s", deltaID)
        agentdb = contentDB(logger=self.logger, config=self.config)
        agentdb.dumpFileContentAsJson(newvlanFile, addition)
        if not self.noRules:
            self.logger.info("Applying virtual interface rules")
            self.vInterface.add(addition['hosts'][self.hostname])
            self.vInterface.setup(addition['hosts'][self.hostname])
            self.vInterface.start(addition['hosts'][self.hostname])
        else:
            self.logger.info("Agent is not configured to create interfaces. Continue")
        return True, ""

    def cancelResources(self, addition, deltaID):
        """Remove resources (Remove interfaces, remove ips, L3 routes)."""
        self.logger.info('Cancelling resources for %s delta' % deltaID)
        if not self.noRules:
            self.logger.info("Removing virtual interface rules")
            self.vInterface.stop(addition['hosts'][self.hostname])
            self.vInterface.remove(addition['hosts'][self.hostname])
        return True, ""

    def start(self):
        """Start execution and get new requests from FE."""
        # a) First check all the deltas on the system based on UID;
        #     1. If State is still activated; leave as it is;
        #     2. If State in remove, removing, cancel, failed do the following:
        #          a) check host state if not removed, do delta Removal;
        #          b) update state and delete file;
        #          c) if state in failed - remove resources and set state removed; remove file;
        self.checkAllFiles()
        self.checkHostStates()
        self.checkActivatingDeltas()
        # QoS Rules:
        # ===========================================================================================
        if not self.noRules:
            qosruler = QOS(self.config, self.logger)
            self.logger.info('Agent is configured to apply QoS rules')
            qosruler.start()
        else:
            self.logger.info('Agent is not configured to apply QoS rules')
        self.logger.info('Ended function start')

    def checkAllFiles(self):
        """Check All deltas active on the host."""
        self.logger.info('Started function checkAllFiles start')
        for fileName in glob.glob("%s/*.json" % self.workDir):
            inputDict = getFileContentAsJson(fileName)
            if 'uid' not in inputDict.keys():
                self.logger.info('Seems this dictionary is custom delta. Ignoring it.')
                continue
            deltaInfo = self.getDeltaInfo(inputDict['uid'])
            if not deltaInfo:
                self.logger.debug('FE did not return anything for %s' % inputDict['uid'])
                continue
            if deltaInfo[0]['state'] in ['remove', 'removing', 'removed', 'cancel', 'failed']:
                if os.path.isfile(fileName):
                    os.remove(fileName)
            elif deltaInfo[0]['state'] in ['activating', 'activated']:
                if deltaInfo[0]['deltat'] == 'addition':
                    deltaInfo[0]['addition'] = evaldict(deltaInfo[0]['addition'])
                    self.checkResources(deltaInfo[0]['addition'][0], inputDict['uid'])

    def checkHostStates(self):
        """Check Host State deltas."""
        # Checking all active host states and set to cancel only ones which deltas are in:
        # for addition deltas - only removed state
        # for reduction deltas - remove and removed
        # ===========================================================================================
        states = self.getHostStates('active')
        for state in states:
            if state['state'] != 'active':
                continue
            deltaInfo = self.getDeltaInfo(state['deltaid'])
            if not deltaInfo:
                self.logger.debug('FE did not return anything for %s' % state['deltaid'])
                continue
            if deltaInfo[0]['state'] in ['remove', 'removed'] and deltaInfo[0]['deltat'] == 'addition':
                self.cancelResources(evaldict(deltaInfo[0]['addition'])[0], state['deltaid'])
                self.setHostState('cancel', state['deltaid'])
            elif deltaInfo[0]['state'] in ['remove', 'removed'] and deltaInfo[0]['deltat'] == 'reduction':
                self.cancelResources(evaldict(deltaInfo[0]['reduction'])[0], state['deltaid'])
                self.setHostState('cancel', state['deltaid'])
            elif deltaInfo[0]['state'] in ['activated'] and deltaInfo[0]['deltat'] == 'reduction':
                self.setHostState('activated', state['deltaid'])

    def checkActivatingDeltas(self):
        """Check all deltas in activating states."""
        states = self.getHostStates('activating')
        for state in states:
            # Check delta State;
            deltaInfo = self.getDeltaInfo(state['deltaid'])
            if not deltaInfo:
                self.logger.debug('FE did not return anything for %s' % state['deltaid'])
                continue
            if deltaInfo[0]['deltat'] == 'reduction':
                deltaInfo[0]['reduction'] = evaldict(deltaInfo[0]['reduction'])
                for connDelta in deltaInfo[0]['reduction']:
                    self.cancelResources(connDelta, state['deltaid'])
                    self.setHostState('active', state['deltaid'])
            elif deltaInfo[0]['deltat'] == 'addition':
                deltaInfo[0]['addition'] = evaldict(deltaInfo[0]['addition'])
                if deltaInfo[0]['state'] in ['activating', 'activated']:
                    self.logger.info('Activating delta %s' % state['deltaid'])
                    if not deltaInfo[0]['addition']:
                        self.logger.info('Failing delta %s. No addition parsed' % state['deltaid'])
                        self.logger.info(deltaInfo[0])
                        # self.setHostState('failed', state['deltaid'])
                        continue
                    outExit = False
                    for connDelta in deltaInfo[0]['addition']:
                        outExit, message = self.activateResources(connDelta, state['deltaid'])
                        self.logger.info("Exit: %s, Message: %s" % (outExit, message))
                    if outExit:
                        self.setHostState('active', state['deltaid'])
                    else:
                        # TODO. Have ability to save message in Frontend.
                        self.setHostState('failed', state['deltaid'])


def execute(config=None, logger=None):
    """Execute main script for DTN-RM Agent output preparation."""
    ruler = Ruler(config, logger)
    ruler.start()

if __name__ == '__main__':
    execute(logger=getStreamLogger())
