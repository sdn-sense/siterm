#!/usr/bin/env python3
# pylint: disable=W0212
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
UpdateDate              : 2022/05/09
"""
import sys
import configparser
import datetime
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.Backends.main import Switch
from SiteFE.ProvisioningService.modules.RoutingService import RoutingService
from SiteFE.ProvisioningService.modules.VirtualSwitchingService import VirtualSwitchingService


class ProvisioningService(RoutingService, VirtualSwitchingService):
    """Provisioning service communicates with Local controllers and applies
    network changes."""
    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='ProvisioningService')
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        workDir = self.config.get('general', 'privatedir') + "/ProvisioningService/"
        createDirs(workDir)
        self.yamlconf = {}
        self.lastApplied = None

    def _forceApply(self):
        curDate = datetime.datetime.now().strftime('%Y-%m-%d-%H')
        if self.lastApplied != curDate:
            self.lastApplied = curDate
            return True
        return False

    def __cleanup(self):
        """Cleanup yaml conf output"""
        self.yamlconf = {}

    def getConfigValue(self, section, option, raiseError=False):
        """Get Config Val"""
        try:
            return self.config.get(section, option)
        except (configparser.NoOptionError, configparser.NoSectionError) as ex:
            if raiseError:
                raise ex
        return ''

    def checkIfStarted(self, connDict):
        """Check if service started."""
        serviceStart = True
        stTime = connDict.get('_params', {}).get('existsDuring', {}).get('start', 0)
        enTime = connDict.get('_params', {}).get('existsDuring', {}).get('end', 0)
        tag = connDict.get('_params', {}).get('tag', 'Unknown-tag')
        if stTime == 0 and enTime == 0:
            return serviceStart
        if stTime > getUTCnow():
            self.logger.debug('Start Time in future. Not starting %s' % tag)
            serviceStart = False
        if enTime < getUTCnow():
            self.logger.debug('End Time passed. Not adding to config %s' % tag)
            serviceStart = False
        return serviceStart

    def prepareYamlConf(self, activeConfig, switches):
        """Prepare yaml config"""
        self.addvsw(activeConfig, switches)
        self.addrst(activeConfig, switches)

    def applyConfig(self):
        """Apply yaml config on Switch"""
        ansOut = self.switch.plugin._applyNewConfig()
        if not ansOut:
            return
        for host, _ in ansOut.stats.get('failures', {}).items():
            for host_events in ansOut.host_events(host):
                if host_events['event'] != 'runner_on_failed':
                    continue
                self.logger.info("Failed to apply Configuration. Failure details below:")
                self.logger.info(host_events)
        if ansOut.stats.get('failures', {}):
            # TODO: Would be nice to save in DB and see errors from WEB UI
            raise Exception("There was configuration apply issue. Please contact support and provide this log file.")


    def startwork(self):
        """Start Provisioning Service main worker."""
        # Workflow is as follow
        # Get current active config;
        self.__cleanup()
        activeDeltas = self.dbI.get('activeDeltas')
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            activeDeltas['output'] = evaldict(activeDeltas['output'])
        if not activeDeltas:
            activeDeltas = {'output': {}}

        self.switch.getinfo(False)
        switches = self.switch._getAllSwitches()
        self.prepareYamlConf(activeDeltas['output'], switches)

        configChanged = False
        for host in switches:
            curActiveConf = self.switch.plugin._getHostConfig(host)
            # Add all keys  from curActiveConf, except interface key
            if host not in self.yamlconf:
                continue
            for key, val in curActiveConf.items():
                if key == 'interface':
                    # Pass val to new function which does comparison
                    self.compareVsw(host, curActiveConf['interface'])
                elif key == 'sense_bgp':
                    self.compareBGP(host, curActiveConf['sense_bgp'])
                else:
                    self.yamlconf[host][key] = val
            # Into the host itself append all except interfaces key
            if curActiveConf != self.yamlconf[host]:
                configChanged = True
                self.switch.plugin._writeHostConfig(host, self.yamlconf[host])
        if configChanged or self._forceApply():
            self.applyConfig()

def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if args:
        provisioner = ProvisioningService(config, args[1])
        provisioner.startwork()
    else:
        for sitename in config.get('general', 'sites').split(','):
            provisioner = ProvisioningService(config, sitename)
            provisioner.startwork()

if __name__ == '__main__':
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    print('1st argument has to be sitename which is configured in this frontend')
    print(sys.argv)
    getLoggingObject(logType='StreamLogger', service='ProvisioningService')
    execute(args=sys.argv)
