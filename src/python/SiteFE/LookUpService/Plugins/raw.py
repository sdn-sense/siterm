#!/usr/bin/env python
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
"""
import copy
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger
from DTNRMLibs.MainUtilities import evaldict


def getNodeDictVlans(nodesInfo, hostname, switchName):
    """ Get Node dictionary """
    if not nodesInfo:
        return None, {}
    for _, nodeDict in nodesInfo['nodes'].items():
        if nodeDict['hostname'] == hostname:
            for intf, intfDict in nodeDict['NetInfo'].items():
                print intfDict
                if not isinstance(intfDict, dict):
                    print 'Something is failing on agent. It did not sent dict!'
                    return None, {}
                if 'switch' in intfDict.keys() and intfDict['switch'] == switchName:
                    return intf, intfDict
    return None, {}


def getinfo(config, logger, nodesInfo=None, site=None):
    """ Get info about RAW plugin """
    output = {'switches': {}, 'vlans': {}}
    if not nodesInfo:
        logger.warning('This FE does not have any nodes defined.')
        nodesInfo = {}
    if not config.has_section(site):
        logger.info('SiteName %s is not defined' % site)
        return output
    logger.info('Looking for switch config for %s site' % site)
    # These config parameters are mandatory. In case not available, return empty list
    for key in ['plugin', 'ports', 'switch']:
        if not config.has_option(site, key):
            logger.info('Option %s is not defined in Site Config. Return' % key)
            return {}
    switch = config.get(site, 'switch')
    output['switches'][switch] = {}
    output['vlans'][switch] = {}
    for port in config.get(site, 'ports').split(','):
        # Each port has to have 4 things defined:
        output['vlans'][switch][port] = {}
        for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
            if not config.has_option(site, "port%s%s" % (port, key)):
                logger.info('Option %s is not defined for Port %s' % (key, port))
            else:
                if key == 'capacity':
                    # TODO. Allow in future to specify in terms of G,M,B. For now only G
                    # and we change it to bits
                    tmpVal = int(config.get(site, "port%s%s" % (port, key)))
                    output['vlans'][switch][port][key] = tmpVal * 1000000000
                else:
                    output['vlans'][switch][port][key] = config.get(site, "port%s%s" % (port, key))
        output['switches'][switch][port] = ""
        if config.has_option(site, "port%shostname" % port):
            output['switches'][switch][port] = config.get(site, 'port%shostname' % port)
        else:
            if config.has_option(site, "port%sisAlias" % port):
                # Means this is the definition of isAlias to another network:
                # And we only do this for keys in UNDEFINED
                spltAlias = config.get(site, 'port%sisAlias' % port).split(':')
                output['switches'][switch][port] = spltAlias[-2]
                output['vlans'][switch][port]['desttype'] = 'switch'
                if 'destport' not in output['vlans'][switch][port].keys():
                    output['vlans'][switch][port]['destport'] = spltAlias[-1]
                if 'hostname' not in output['vlans'][switch][port].keys():
                    output['vlans'][switch][port]['hostname'] = spltAlias[-2]
    for _, nodeDict in nodesInfo.items():
        hostinfo = evaldict(nodeDict['hostinfo'])
        for intfKey, intfDict in hostinfo['NetInfo']["interfaces"].items():
            print intfKey, intfDict
            breakLoop = False
            for key in ['switch_port', 'switch', 'vlan_range', 'available_bandwidth']:
                if key not in intfDict.keys():
                    logger.debug('key %s is not available in intf dict git config', key)
                    breakLoop = True
            if breakLoop:
                continue
            if intfDict['switch'] in output['switches'].keys():
                if intfDict['switch_port'] not in output['switches'][intfDict['switch']].keys():
                    logger.debug('Frontend Config is not configured to use this Port %s', intfDict['switch_port'])
                    continue
                output['switches'][intfDict['switch']][intfDict['switch_port']] = nodeDict['hostname']
                output['vlans'][intfDict['switch']][intfDict['switch_port']] = {}
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['destport'] = intfKey
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['hostname'] = nodeDict['hostname']
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['desttype'] = 'server'
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['vlan_range'] = intfDict['vlan_range']
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['capacity'] = intfDict['available_bandwidth']
                if 'isAlias' in intfDict.keys():
                    output['vlans'][intfDict['switch']][intfDict['switch_port']]['isAlias'] = intfDict['isAlias']
    if config.has_option(site, "l3_routing_map"):
        routingMap = config.get(site, "l3_routing_map")
        output['l3_routing'] = evaldict(routingMap)
    print output
    # Final check to remove empty listings.
    # e.g. Frontend defined port - but no hosts registered to this port;
    tmpOut = copy.deepcopy(output)
    for sw, swd in output['switches'].items():
        if not swd:
            del tmpOut['switches'][sw]
            continue
        for swp, swpVal in output['switches'][sw].items():
            if not swpVal:
                del tmpOut['switches'][sw][swp]
                continue
    print tmpOut
    return tmpOut

if __name__ == '__main__':
    print 'WARNING!!!! This should not be used through main call. Only for testing purposes!!!'
    CONFIG = getConfig()
    COMPONENT = 'LookUpService'
    LOGGER = getStreamLogger()
    for sitename in CONFIG.get('general', 'sites').split(','):
        print 'Working on %s' % sitename
        getinfo(CONFIG, LOGGER, site=sitename)
