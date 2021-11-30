#!/usr/bin/env python3
"""Provisioning service is provision everything on the switches;

Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
UpdateDate              : 2021/11/08
"""
import sys
import pprint
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import getDataFromSiteFE
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.Backends.main import Switch
from SiteFE.REST.Models.DeltaModels import frontendDeltaModels


class ProvisioningService():
    """Provisioning service communicates with Local controllers and applies
    network changes."""
    def __init__(self, config, logger, sitename):
        self.logger = logger
        self.config = config
        self.siteDB = contentDB(logger=self.logger, config=self.config)
        self.sitename = sitename
        self.switch = Switch(config, logger, sitename)
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        workDir = self.config.get('general', 'privatedir') + "/ProvisioningService/"
        createDirs(workDir)
        self.feCalls = frontendDeltaModels(self.logger, self.config. self.dbI)

    def pushInternalAction(self, state, deltaID, hostname):
        """Push Internal action and return dict."""
        # TODO: Catch exceptions, like WrongDeltaStatusTransition
        self.feCalls.commitdelta(deltaID, state, internal=True, hostname=hostname, **{'sitename': self.sitename})


    def deltaRemoval(self, newDelta, deltaID, newvlan, switchName):
        """Here goes all communication with component and also rest
        interface."""
        self.logger.debug('I got REDUCTION!!!!!. Reduction only sets states until active.')
        if 'ReductionID' not in newDelta:
            # I dont know which one to set to removed...
            # Will apply only rules for reduction.
            self.pushInternalAction("remove", newDelta['ReductionID'], switchName)
        deltaState = newDelta['HOSTSTATE']
        for stateChange in [{"accepting": "accepted"}, {"accepted": "committing"},
                            {"committing": "committed"}, {"committed": "activating"},
                            {"activating": "active"}, {"active": "remove"}, {"cancel": "remove"}]:
            if deltaState == list(stateChange.keys())[0]:
                msg = 'Delta State %s and performing action to %s' % (deltaState, stateChange[deltaState])
                self.logger.debug(msg)
                self.switch.mainCall(deltaState, newvlan, 'remove')
                self.pushInternalAction(stateChange[deltaState], deltaID, switchName)
                deltaState = stateChange[deltaState]
        return True

    def deltaCommit(self, newDelta, deltaID, newvlan, switchName):
        """Here goes all communication with component and also rest
        interface."""
        deltaState = newDelta['HOSTSTATE']
        for stateChange in [{"accepting": "accepted"}, {"accepted": "committing"},
                            {"committing": "committed"}, {"committed": "activating"}, {"activating": "active"}]:
            if deltaState == list(stateChange.keys())[0]:
                self.logger.info('Delta State %s and performing action to %s' % (deltaState, stateChange[deltaState]))
                self.switch.mainCall(deltaState, newvlan, 'add')
                self.pushInternalAction(stateChange[deltaState], deltaID, switchName)
                deltaState = stateChange[deltaState]
        return True

    def getnewvlan(self, newDelta, deltaID, switchHostName, inKey):
        """Check all keys in vlan requimenet and return correct out for
        addition or deletion."""
        self.logger.debug('Delta id %s' % deltaID)
        self.logger.debug('Got Parsed Delta %s' % newDelta['ParsedDelta'])
        if inKey in newDelta['ParsedDelta'] and newDelta['ParsedDelta'][inKey]:
            return newDelta['ParsedDelta'][inKey][switchHostName]
        return {}

    def checkdeltas(self, switchHostname, inJson):
        """Check which ones are assigned to any of switch."""
        newDeltas = []
        if switchHostname in list(inJson['HostnameIDs'].keys()):
            for delta in inJson['HostnameIDs'][switchHostname]:
                # print delta, self.hostname, inJson['ID'][delta]['State']
                # 1) Filter out all which are not relevant.
                self.logger.debug('Switch %s delta state %s' % (delta, inJson['ID'][delta]['State']))
                if inJson['ID'][delta]['State'] in ['activating', 'removing']:
                    if inJson['HostnameIDs'][switchHostname][delta] not in ['failed', 'active', 'remove']:
                        tmpDict = inJson['ID'][delta]
                        tmpDict['HOSTSTATE'] = inJson['HostnameIDs'][switchHostname][delta]
                        newDeltas.append(tmpDict)
                elif inJson['ID'][delta]['State'] in ['cancel']:
                    tmpDict = inJson['ID'][delta]
                    tmpDict['HOSTSTATE'] = inJson['HostnameIDs'][switchHostname][delta]
                    newDeltas.append(tmpDict)
        return newDeltas

    def getData(self, fullURL, urlPath):
        """Get data from FE."""
        agents = getDataFromSiteFE({}, fullURL, urlPath)
        if agents[2] != 'OK':
            msg = 'Received a failure getting information from Site Frontend %s' % str(agents)
            self.logger.debug(msg)
            return {}
        return evaldict(agents[0])

    def getAllAliases(self):
        """Get All Aliases."""
        out = self.switch.output['switches'].keys()
        for _, switchPort in list(self.switch.output['ports'].items()):
            for _, portDict in list(switchPort.items()):
                if 'isAlias' in portDict:
                    tmp = portDict['isAlias'].split(':')[-3:]
                    out.append(tmp[0])
        return out

    def _vlanAction(self, newDelta, switchName, actionKey):
        """ Vlan action redurce/add based on delta state """
        newvlan = self.getnewvlan(newDelta, newDelta['ID'], switchName, actionKey)
        if actionKey == 'reduction' and newDelta['ParsedDelta'][actionKey]:
            self.deltaRemoval(newDelta, newDelta['ID'], newvlan, switchName)
        elif actionKey == 'addition' and newDelta['ParsedDelta'][actionKey]:
            if newDelta['State'] in ['cancel']:
                newDelta['ReductionID'] = newDelta['ID']
                self.deltaRemoval(newDelta, newDelta['ID'], newvlan, switchName)
            else:
                self.deltaCommit(newDelta, newDelta['ID'], newvlan, switchName)
        else:
            self.logger.warning('Unknown delta state')
            pretty = pprint.PrettyPrinter(indent=4)
            pretty.pprint(evaldict(newDelta))

    def startwork(self):
        """Start Provisioning Service main worker."""
        jOut = self.dbI.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)
        if not jOut:
            self.logger.info('No Hosts in database. Finish loop.')
            return
        # Get switch information...
        self.switch.getinfo(jOut, False)
        alliases = self.getAllAliases()
        outputDict = {}
        allDeltas = self.dbI.get('deltas')
        for switchName in alliases:
            newDeltas = self.checkdeltas(switchName, allDeltas)
            for newDelta in newDeltas:
                outputDict.setdefault(newDelta['ID'])
                for actionKey in ['reduction', 'addition']:
                    try:
                        self._vlanAction(newDelta, switchName, actionKey)
                    except IOError as ex:
                        self.logger.warning('IOError: %s', ex)
                        raise Exception from IOError


def execute(config=None, logger=None, args=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if not logger:
        component = 'ProvisioningService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component), config.get(component, 'logLevel'))
    if args:
        provisioner = ProvisioningService(config, logger, args[1])
        provisioner.startwork()
    else:
        for sitename in config.get('general', 'sites').split(','):
            provisioner = ProvisioningService(config, logger, sitename)
            provisioner.startwork()

if __name__ == '__main__':
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    print('1st argument has to be sitename which is configured in this frontend')
    print(sys.argv)
    if len(sys.argv) == 2:
        execute(args=sys.argv, logger=getStreamLogger())
    else:
        execute(logger=getStreamLogger())
