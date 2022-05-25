#!/usr/bin/env python3
"""Virtual Switching module to prepare/compare with ansible config.

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

def dictCompare(inDict, oldDict):
    """Compare dict and set any remaining items
       from current ansible yaml as absent in new one if
       it's status is present"""
    # If equal - return
    if inDict == oldDict:
        return
    for key, val in oldDict.items():
        if isinstance(val, dict):
            dictCompare(inDict.setdefault(key, {}), val)
            if not inDict[key]:
                # if it is empty after back from loop, delete
                del inDict[key]
            continue
        if val == 'present' and key not in inDict.keys():
            # Means current state is present, but model does not know anything
            inDict[key] = 'absent'
        elif val not in ['present', 'absent']:
            # Ensure we pre-keep all other keys
            inDict[key] = val
    return

class VirtualSwitchingService():
    """Virtual Switching - add interfaces inside ansible yaml"""
    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    def __getdefaultIntf(self, host):
        tmpD = self.yamlconf.setdefault(host, {})
        tmpD = tmpD.setdefault('interface', {})
        return tmpD

    def __getdefaultVlan(self, host, port, portDict):
        """Default yaml dict setup"""
        tmpD = self.__getdefaultIntf(host)
        if 'hasLabel' not in portDict or 'value' not in portDict['hasLabel']:
            raise Exception('Bad running config. Missing vlan entry: %s %s %s' % (host, port, portDict))
        vlan = portDict['hasLabel']['value']
        vlanName = self.switch._getSwitchPortName(host, 'Vlan%s' % vlan, vlan)
        vlanDict = tmpD.setdefault(vlanName, {})
        vlanDict.setdefault('name', vlanName)
        tmpVrf = self.getConfigValue(host, 'vrf')
        if tmpVrf:
            vlanDict.setdefault('vrf', tmpVrf)
        return vlanDict

    def _addTaggedInterfaces(self, host, port, portDict):
        """Add Tagged Interfaces to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        portName = self.switch._getSwitchPortName(host, port)
        vlanDict.setdefault('tagged_members', {})
        vlanDict['tagged_members'][portName] = 'present'

    def _addIPv4Address(self, host, port, portDict):
        """Add IPv4 to expected yaml conf"""
        # For IPv4 - only single IP is supported. No secondary ones
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv4-address', {}).get('value', ""):
            vlanDict.setdefault('ipv4_address', {})
            vlanDict['ipv4_address'][portDict['hasNetworkAddress']['ipv4-address']['value']] = 'present'

    def _addIPv6Address(self, host, port, portDict):
        """Add IPv6 to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv6-address', {}).get('value', ""):
            vlanDict.setdefault('ipv6_address', {})
            vlanDict['ipv6_address'][portDict['hasNetworkAddress']['ipv6-address']['value']] = 'present'

    def _presetDefaultParams(self, host, port, portDict):
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        vlanDict['description'] = portDict.get('_params', {}).get('tag', "SENSE-VLAN-Without-Tag")
        vlanDict['state'] = 'present'

    def addvsw(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for vsw)"""
        if 'vsw' in activeConfig:
            for _, connDict in activeConfig['vsw'].items():
                if not self.checkIfStarted(connDict):
                    continue
                # Get _params and existsDuring - if start < currentTime and currentTime < end
                # Otherwise log details of the start/stop/currentTime.
                for host, hostDict in connDict.items():
                    if host in switches:
                        for port, portDict in hostDict.items():
                            self._presetDefaultParams(host, port, portDict)
                            self._addTaggedInterfaces(host, port, portDict)
                            self._addIPv4Address(host, port, portDict)
                            self._addIPv6Address(host, port, portDict)
        else:
            for host in switches:
                self.__getdefaultIntf(host)

    def compareVsw(self, switch, runningConf):
        """Compare expected and running conf"""
        if self.yamlconf[switch]['interface'] == runningConf:
            return # equal config
        for key, val in runningConf.items():
            if key not in self.yamlconf[switch]['interface'].keys() and val['state'] != 'absent':
                # Vlan is present in ansible config, but not in new config
                # set vlan to state: 'absent'. In case it is absent already
                # we dont need to set it again. Switch is unhappy to apply
                # same command if service is not present.
                self.yamlconf[switch]['interface'].setdefault(key, {'state': 'absent'})
                continue
            for key1, val1 in val.items():
                if isinstance(val1, (dict, list)) and key1 in ['tagged_members', 'ipv4_address', 'ipv6_address']:
                    yamlOut = self.yamlconf[switch]['interface'].setdefault(key, {}).setdefault(key1, {})
                    dictCompare(yamlOut, val1)
                elif isinstance(val1, (dict, list)):
                    raise Exception('Got unexpected dictionary in comparison %s' % val)
