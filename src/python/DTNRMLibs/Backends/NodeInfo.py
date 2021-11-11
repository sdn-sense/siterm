#!/usr/bin/env python3
"""
    Node information which was received from the agent.

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
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2021 California Institute of Technology
Date            : 2021/11/08
"""
from DTNRMLibs.MainUtilities import evaldict

class Node():
    """ Parse node info sent by agent """
    def __init__(self, config, logger, site):
        self.config = config
        self.site = site
        self.logger = logger

    def nodeinfo(self, nodesInfo, output):
        """put  all node information from node reported stats."""
        for _, nodeDict in list(nodesInfo.items()):
            hostinfo = evaldict(nodeDict['hostinfo'])
            for intfKey, intfDict in list(hostinfo['NetInfo']["interfaces"].items()):
                breakLoop = False
                for key in ['switch_port', 'switch', 'vlan_range', 'available_bandwidth']:
                    if key not in list(intfDict.keys()):
                        breakLoop = True
                if breakLoop:
                    continue
                if intfDict['switch'] in list(output['ports'].keys()):
                    if intfDict['switch_port'] not in list(output['ports'][intfDict['switch']].keys()):
                        self.logger.debug('Frontend Config is not configured to use this Port %s',
                                          intfDict['switch_port'])
                        continue
                    switch = intfDict['switch']
                    switchp = intfDict['switch_port']
                    output['ports'][switch][switchp] = {}
                    output['ports'][switch][switchp]['destport'] = intfKey
                    output['ports'][switch][switchp]['hostname'] = nodeDict['hostname']
                    output['ports'][switch][switchp]['desttype'] = 'server'
                    output['ports'][switch][switchp]['vlan_range'] = intfDict['vlan_range']
                    output['ports'][switch][switchp]['capacity'] = intfDict['available_bandwidth']
                    if 'isAlias' in list(intfDict.keys()):
                        output['ports'][switch][switchp]['isAlias'] = intfDict['isAlias']
        if self.config.has_option(self.site, "l3_routing_map"):
            routingMap = self.config.get(self.site, "l3_routing_map")
            output['l3_routing'] = evaldict(routingMap)
        return output
