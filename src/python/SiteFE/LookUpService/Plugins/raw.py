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
Title             : dtnrm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2016 California Institute of Technology
Date            : 2017/09/26
"""
from __future__ import print_function
from builtins import object
import copy
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger
from DTNRMLibs.MainUtilities import evaldict


def getNodeDictVlans(nodesInfo, hostname, switchName):
    """Get Node dictionary."""
    if not nodesInfo:
        return None, {}
    for _, nodeDict in list(nodesInfo['nodes'].items()):
        if nodeDict['hostname'] == hostname:
            for intf, intfDict in list(nodeDict['NetInfo'].items()):
                print(intfDict)
                if not isinstance(intfDict, dict):
                    print('Something is failing on agent. It did not sent dict!')
                    return None, {}
                if 'switch' in list(intfDict.keys()) and intfDict['switch'] == switchName:
                    return intf, intfDict
    return None, {}


class Switch(object):
    """RAW Switch plugin.

    All info comes from yaml files.
    """
    def __init__(self, config, logger, nodesInfo, site):
        self.config = config
        self.logger = logger
        self.nodesInfo = nodesInfo
        if not self.nodesInfo:
            self.nodesInfo = {}
        self.site = site
        self.output = {'switches': {}, 'vlans': {}}

    def getinfo(self):
        """Get info about RAW plugin."""
        if not self.config.has_section(self.site):
            self.logger.info('SiteName %s is not defined' % self.site)
            return self.output
        self.logger.debug('Looking for switch config for %s site' % self.site)
        # These config parameters are mandatory. In case not available, return empty list
        for key in ['plugin', 'switch']:
            if not self.config.has_option(self.site, key):
                self.logger.info('Option %s is not defined in Site Config. Return' % key)
                return {}
        switch = self.config.get(self.site, 'switch')
        for switchn in switch.split(','):
            self.switchInfo(switchn)
        self.nodeinfo()
        return self.cleanupEmpty()

    def cleanupEmpty(self):
        """Final check remove empty dicts/lists inside output."""
        tmpOut = copy.deepcopy(self.output)
        for sw, swd in list(self.output['switches'].items()):
            if not swd:
                del tmpOut['switches'][sw]
                continue
            for swp, swpVal in list(self.output['switches'][sw].items()):
                if not swpVal and not self.output.get('vlans', {}).get(sw, {}).get(swp, {}).get('isAlias'):
                    del tmpOut['switches'][sw][swp]
                    continue
        return tmpOut

    def getValFromConfig(self, switch, port, key):
        """Get val from config."""
        tmpVal = self.config.get(switch, "port%s%s" % (port, key))
        try:
            tmpVal = int(tmpVal)
        except ValueError:
            pass
        return tmpVal

    def switchInfo(self, switch):
        """Get all switch info from FE main yaml file."""
        self.output['switches'][switch] = {}
        self.output['vlans'][switch] = {}
        for port in self.config.get(switch, 'ports').split(','):
            # Each port has to have 4 things defined:
            self.output['vlans'][switch][port] = {}
            for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
                if not self.config.has_option(switch, "port%s%s" % (port, key)):
                    self.logger.debug('Option %s is not defined for Switch %s and Port %s' % (key, switch, port))
                    continue
                else:
                    tmpVal = self.getValFromConfig(switch, port, key)
                    if key == 'capacity':
                        # TODO. Allow in future to specify in terms of G,M,B. For now only G
                        # and we change it to bits
                        self.output['vlans'][switch][port][key] = tmpVal * 1000000000
                    else:
                        self.output['vlans'][switch][port][key] = tmpVal
            self.output['switches'][switch][port] = ""
            if self.config.has_option(switch, "port%shostname" % port):
                self.output['switches'][switch][port] = self.getValFromConfig(switch, port, 'hostname')
            elif self.config.has_option(switch, "port%sisAlias" % port):
                spltAlias = self.getValFromConfig(switch, port, 'isAlias').split(':')
                #self.output['switches'][switch][port] = spltAlias[-2]
                self.output['vlans'][switch][port]['desttype'] = 'switch'
                if 'destport' not in list(self.output['vlans'][switch][port].keys()):
                    self.output['vlans'][switch][port]['destport'] = spltAlias[-1]
                if 'hostname' not in list(self.output['vlans'][switch][port].keys()):
                    self.output['vlans'][switch][port]['hostname'] = spltAlias[-2]

    def nodeinfo(self):
        """put  all node information from node reported stats."""
        for _, nodeDict in list(self.nodesInfo.items()):
            hostinfo = evaldict(nodeDict['hostinfo'])
            for intfKey, intfDict in list(hostinfo['NetInfo']["interfaces"].items()):
                breakLoop = False
                for key in ['switch_port', 'switch', 'vlan_range', 'available_bandwidth']:
                    if key not in list(intfDict.keys()):
                        breakLoop = True
                if breakLoop:
                    continue
                if intfDict['switch'] in list(self.output['switches'].keys()):
                    if intfDict['switch_port'] not in list(self.output['switches'][intfDict['switch']].keys()):
                        self.logger.debug('Frontend Config is not configured to use this Port %s',
                                          intfDict['switch_port'])
                        continue
                    switch = intfDict['switch']
                    switchp = intfDict['switch_port']
                    self.output['switches'][switch][switchp] = nodeDict['hostname']
                    self.output['vlans'][switch][switchp] = {}
                    self.output['vlans'][switch][switchp]['destport'] = intfKey
                    self.output['vlans'][switch][switchp]['hostname'] = nodeDict['hostname']
                    self.output['vlans'][switch][switchp]['desttype'] = 'server'
                    self.output['vlans'][switch][switchp]['vlan_range'] = intfDict['vlan_range']
                    self.output['vlans'][switch][switchp]['capacity'] = intfDict['available_bandwidth']
                    if 'isAlias' in list(intfDict.keys()):
                        self.output['vlans'][switch][switchp]['isAlias'] = intfDict['isAlias']
        if self.config.has_option(self.site, "l3_routing_map"):
            routingMap = self.config.get(self.site, "l3_routing_map")
            self.output['l3_routing'] = evaldict(routingMap)

if __name__ == '__main__':
    print('WARNING!!!! This should not be used through main call. Only for testing purposes!!!')
    CONFIG = getConfig()
    COMPONENT = 'LookUpService'
    LOGGER = getStreamLogger()
    for sitename in CONFIG.get('general', 'sites').split(','):
        print('Working on %s' % sitename)
        method = Switch(CONFIG, LOGGER, None, sitename)
        print(method.getinfo())
