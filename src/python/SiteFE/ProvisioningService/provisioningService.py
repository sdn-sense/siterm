#!/usr/bin/env python
"""
    Provisioning service is provision everything on the switches;

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
import importlib
import time
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getFullUrl
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import getDataFromSiteFE
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand

class ProvisioningService(object):
    """ Provisioning service communicates with Local controllers and applies network changes. """
    def __init__(self, config, logger, args):
        self.logger = logger
        self.config = config
        self.args = args
        self.siteDB = contentDB(logger=self.logger, config=self.config)
        self.sitename = None

    def pushInternalAction(self, url, state, deltaID, hostname):
        """ Push Internal action and return dict """
        newState = ""
        restOut = {}
        restOut = getDataFromSiteFE({}, url, "/sitefe/v1/deltas/%s/internalaction/%s/%s" % (deltaID, hostname, state))
        if restOut[1] >= 400:
            msg = "Failed to set new state in database for %s delta and %s hostname. Error %s " \
                  % (deltaID, hostname, restOut)
            self.logger.debug(msg)
            raise FailedInterfaceCommand(msg)
        restOutHIDs = getDataFromSiteFE({}, url, "/sitefe/v1/hostnameids/%s" % hostname)
        tmpOut = evaldict(restOutHIDs[0])
        newState = tmpOut[deltaID]
        msg = 'New State on the rest is %s and requested %s' % (newState, state)
        self.logger.debug(msg)
        if newState != state:
            time.sleep(4)
        return evaldict(restOut)

    def deltaRemoval(self, newDelta, deltaID, newvlan, switchName, switchruler, fullURL):
        """ Here goes all communication with component and also rest interface """
        self.logger.debug('I got REDUCTION!!!!!. Reduction only sets states until active.')
        if 'ReductionID' not in newDelta:
            # I dont know which one to set to removed...
            # Will apply only rules for reduction.
            self.pushInternalAction(fullURL, "remove", newDelta['ReductionID'], switchName)
        deltaState = newDelta['HOSTSTATE']
        for stateChange in [{"accepting": "accepted"}, {"accepted": "committing"},
                            {"committing": "committed"}, {"committed": "activating"},
                            {"activating": "active"}, {"active": "remove"}, {"cancel": "remove"}]:
            if deltaState == stateChange.keys()[0]:
                msg = 'Delta State %s and performing action to %s' % (deltaState, stateChange[deltaState])
                self.logger.debug(msg)
                switchruler.mainCall(deltaState, newvlan, 'remove')
                self.pushInternalAction(fullURL, stateChange[deltaState], deltaID, switchName)
                deltaState = stateChange[deltaState]
        return True

    # TODO merge these two functions
    def deltaCommit(self, newDelta, deltaID, newvlan, switchName, switchruler, fullURL):
        """ Here goes all communication with component and also rest interface """
        print 'Here goes all communication with component and also rest interface'
        deltaState = newDelta['HOSTSTATE']
        for stateChange in [{"accepting": "accepted"}, {"accepted": "committing"},
                            {"committing": "committed"}, {"committed": "activating"}, {"activating": "active"}]:
            if deltaState == stateChange.keys()[0]:
                print 'Delta State %s and performing action to %s' % (deltaState, stateChange[deltaState])
                switchruler.mainCall(deltaState, newvlan, 'add')
                self.pushInternalAction(fullURL, stateChange[deltaState], deltaID, switchName)
                deltaState = stateChange[deltaState]
        return True

    def getnewvlan(self, newDelta, deltaID, switchHostName, inKey):
        """ Check all keys in vlan requimenet and return correct out for addition or deletion """
        self.logger.debug('Delta id %s' % deltaID)
        self.logger.debug('Got Parsed Delta %s' % newDelta['ParsedDelta'])
        if inKey in newDelta['ParsedDelta'] and newDelta['ParsedDelta'][inKey]:
            return newDelta['ParsedDelta'][inKey][switchHostName]
        return {}


    def checkdeltas(self, switchHostname, inJson):
        """Check which ones are assigned to any of switch"""
        newDeltas = []
        if switchHostname in inJson['HostnameIDs'].keys():
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

    def getData(self, fullURL, URLPath):
        """ Get data from FE """
        agents = getDataFromSiteFE({}, fullURL, URLPath)
        if agents[2] != 'OK':
            msg = 'Received a failure getting information from Site Frontend %s' % str(agents)
            self.logger.debug(msg)
            return {}
        return evaldict(agents[0])

    def getAllAliases(self, switches):
        """ Get All Aliases """
        out = []
        if not switches:
            return out
        for _switchName, switchPort in switches['vlans'].items():
            for _portName, portDict in switchPort.items():
                if 'isAlias' in portDict:
                    tmp = portDict['isAlias'].split(':')[-3:]
                    out.append(tmp[0])
        return out

    def startwork(self):
        """Main start """
        for siteName in self.config.get('general', 'sites').split(','):
            workDir = self.config.get(siteName, 'privatedir') + "/ProvisioningService/"
            createDirs(workDir)
            self.sitename = siteName
            self.logger.info('Working on Site %s' % self.sitename)
            self.startworkmain()

    def startworkmain(self):
        fullURL = getFullUrl(self.config, sitename=self.sitename)
        jOut = self.getData(fullURL, "/sitefe/json/frontend/getdata")
        workDir = self.config.get('general', 'privatedir') + "/ProvisioningService/"
        createDirs(workDir)
        if not jOut:
            self.logger.info('Seems server returned empty dictionary. Exiting.')
            return
        # Get switch information...
        switchPlugin = self.config.get(self.sitename, 'plugin')
        self.logger.info('Will load %s switch plugin' % switchPlugin)
        method = importlib.import_module("SiteFE.ProvisioningService.Plugins.%s" % switchPlugin.lower())
        switchruler = method.mainCaller()
        topology = method.topology()
        switches = topology.getTopology()
        alliases = self.getAllAliases(switches)
        outputDict = {}
        allDeltas = self.getData(fullURL, "/sitefe/v1/deltas?oldview=true")
        for switchName in list(switches['switches'].keys() + alliases):
            print switchName
            newDeltas = self.checkdeltas(switchName, allDeltas)
            for newDelta in newDeltas:
                outputDict.setdefault(newDelta['ID'])
                for actionKey in ['reduction', 'addition']:
                    try:
                        newvlan = self.getnewvlan(newDelta, newDelta['ID'], switchName, actionKey)
                        if actionKey == 'reduction' and newDelta['ParsedDelta'][actionKey]:
                            self.deltaRemoval(newDelta, newDelta['ID'], newvlan, switchName, switchruler, fullURL)
                        elif actionKey == 'addition' and newDelta['ParsedDelta'][actionKey]:
                            if newDelta['State'] in ['cancel']:
                                newDelta['ReductionID'] = newDelta['ID']
                                self.deltaRemoval(newDelta, newDelta['ID'], newvlan, switchName, switchruler, fullURL)
                            else:
                                self.deltaCommit(newDelta, newDelta['ID'], newvlan, switchName, switchruler, fullURL)
                    except IOError as ex:
                        print ex
                        raise Exception('Received IOError')


def execute(config=None, logger=None, args=None):
    """Main Execute"""
    if not config:
        config = getConfig(["/etc/dtnrm-site-fe.conf"])
    if not logger:
        component = 'LookUpService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component), config.get(component, 'logLevel'))
    provisioner = ProvisioningService(config, logger, args)
    provisioner.startwork()

if __name__ == '__main__':
    execute()
