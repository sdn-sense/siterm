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
from DTNRMLibs.MainUtilities import getConfig, getLogger, getStreamLogger
from DTNRMLibs.MainUtilities import evaldict

def getNodeDictVlans(nodesInfo, hostname, switchName):
    if not nodesInfo:
        return None, {}
    for nodeIP, nodeDict in nodesInfo['nodes'].items():
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
    # Each plugin has it's own definition how to represent and return information;
    # All of them should return all ports, switch names and also nodes to which they are connected;
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
                logger.info('Option %s is not defined for Port.' % key)
                output['vlans'][switch][port][key] = 'UNDEFINED'
            else:
                output['vlans'][switch][port][key] = config.get(site, "port%s%s" % (port, key))
        output['switches'][switch][port] = config.get(site, 'port%shostname' % port)
    for nodename, nodeDict in nodesInfo.items():
        hostinfo = evaldict(nodeDict['hostinfo'])
        for intfKey, intfDict in hostinfo['NetInfo']["interfaces"].items():
            print intfKey, intfDict
            breakLoop = False
            for key in ['switch_port', 'switch', 'vlan_range', 'available_bandwidth']:
                if key not in intfDict.keys():
                    breakLoop = True
            if breakLoop:
                continue
            if intfDict['switch'] in output['switches'].keys():
                if intfDict['switch_port'] in output['switches'][intfDict['switch']].keys():
                    logger.info('Datanode is misconfigured. It defines same interface. Will not add to ')
                    continue
                output['switches'][intfDict['switch']][intfDict['switch_port']] = nodeDict['hostname']
                output['vlans'][intfDict['switch']][intfDict['switch_port']] = {}
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['destport'] = intfKey
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['hostname'] = nodeDict['hostname']
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['desttype'] = 'server'
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['vlan_range'] = intfDict['vlan_range']
                output['vlans'][intfDict['switch']][intfDict['switch_port']]['capacity'] = intfDict['available_bandwidth']
    if config.has_option(site, "l3_routing_map"):
        routingMap = config.get(site, "l3_routing_map")
        output['l3_routing'] = evaldict(routingMap)
    print output
    return output

if __name__ == '__main__':
    print 'WARNING!!!! This should not be used through main call. Only for testing purposes!!!'
    CONFIG = getConfig(["/etc/dtnrm-site-fe.conf"])
    COMPONENT = 'LookUpService'
    LOGGER = getStreamLogger()
    for sitename in CONFIG.get('general', 'sites').split(','):
        print 'Working on %s' % sitename
        getinfo(CONFIG, LOGGER, site=sitename)
