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
from SiteRMLibs.ipaddr import normalizedip


def dictCompare(inDict, oldDict, key1):
    """Compare dict and set any remaining items
       from current ansible yaml as absent in new one if
       it's status is present"""
    # If equal - return
    if inDict == oldDict:
        return
    for key, val in oldDict.items():
        if isinstance(val, dict):
            dictCompare(inDict.setdefault(key, {}), val, key1)
            if not inDict[key]:
                # if it is empty after back from loop, delete
                del inDict[key]
            continue
        tmpKey = key
        if key1 in ['ipv4_address', 'ipv6_address']:
            tmpKey = normalizedip(key)
        if val == 'present' and tmpKey not in inDict.keys():
            # Means current state is present, but model does not know anything
            inDict[tmpKey] = 'absent'
        elif val not in ['present', 'absent']:
            # Ensure we pre-keep all other keys
            inDict[tmpKey] = val
    return

class VirtualSwitchingService():
    """Virtual Switching - add interfaces inside ansible yaml"""
    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    def __getdefaultIntf(self, host):
        if self.reqid == 0:
            tmpD = self.yamlconf.setdefault(host, {})
        elif self.reqid == 1:
            tmpD = self.yamlconfuuid.setdefault('vsw', {}).setdefault(self.connID, {})
            tmpD = tmpD.setdefault(host, {})
        else:
            raise Exception('Wrong code. Should not reach this part. VirtualSwitchingService')
        tmpD = tmpD.setdefault('interface', {})
        return tmpD

    def __getdefaultVlan(self, host, port, portDict):
        """Default yaml dict setup"""
        tmpD = self.__getdefaultIntf(host)
        if 'hasLabel' not in portDict or 'value' not in portDict['hasLabel']:
            raise Exception(f'Bad running config. Missing vlan entry: {host} {port} {portDict}')
        vlan = portDict['hasLabel']['value']
        vlanName = f'Vlan{vlan}'
        vlanDict = tmpD.setdefault(vlanName, {})
        vlanDict.setdefault('name', vlanName)
        vlanDict.setdefault('vlanid', vlan)
        tmpVrf = self.getConfigValue(host, 'vrf')
        if tmpVrf:
            vlanDict.setdefault('vrf', tmpVrf)
        tmpVlanMTU = self.getConfigValue(host, 'vlan_mtu')
        if tmpVlanMTU:
            vlanDict.setdefault('mtu', tmpVlanMTU)
        return vlanDict

    def _addTaggedInterfaces(self, host, port, portDict):
        """Add Tagged Interfaces to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        portName = self.switch.getSwitchPortName(host, port)
        # Replace virtual port name to real portname if defined
        if self.config.has_option(host, f'port_{portName}_realport'):
            portName = self.config.config['MAIN'][host][f'port_{portName}_realport']
        vlanDict.setdefault('tagged_members', {})
        vlanDict['tagged_members'][portName] = 'present'

    def _addIPv4Address(self, host, port, portDict):
        """Add IPv4 to expected yaml conf"""
        # For IPv4 - only single IP is supported. No secondary ones
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv4-address', {}).get('value', ""):
            vlanDict.setdefault('ipv4_address', {})
            ip = normalizedip(portDict['hasNetworkAddress']['ipv4-address']['value'])
            vlanDict['ipv4_address'][ip] = 'present'

    def _addIPv6Address(self, host, port, portDict):
        """Add IPv6 to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv6-address', {}).get('value', ""):
            vlanDict.setdefault('ipv6_address', {})
            ip = normalizedip(portDict['hasNetworkAddress']['ipv6-address']['value'])
            vlanDict['ipv6_address'][ip] = 'present'

    def _presetDefaultParams(self, host, port, portDict):
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        vlanDict['description'] = portDict.get('_params', {}).get('tag', "SENSE-VLAN-Without-Tag")
        vlanDict['belongsTo'] = portDict.get('_params', {}).get('belongsTo', "SENSE-VLAN-Without-belongsTo")
        vlanDict['state'] = 'present'

    def _addparamsVsw(self, connDict, switches):
        """Wrapper for add params, to put individual request info too inside dictionary"""
        # 0 - Main which adds all requests into a single yaml file for ansible
        # 1 - Adds Vlan request into a unique uuid request dictionary and used by ansible
        for reqid in [0, 1]:
            self.reqid = reqid
            for host, hostDict in connDict.items():
                if host in switches:
                    for port, portDict in hostDict.items():
                        if port == '_params':
                            continue
                        self._presetDefaultParams(host, port, portDict)
                        self._addTaggedInterfaces(host, port, portDict)
                        self._addIPv4Address(host, port, portDict)
                        self._addIPv6Address(host, port, portDict)

    def addvsw(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for vsw)"""
        if 'vsw' in activeConfig:
            for connID, connDict in activeConfig['vsw'].items():
                self.connID = connID
                if not self.checkIfStarted(connDict):
                    continue
                self._addparamsVsw(connDict, switches)
        for reqid in [0, 1]:
            self.reqid = reqid
            for host in switches:
                self.__getdefaultIntf(host)

    def compareVsw(self, switch, runningConf, uuid=''):
        """Compare expected and running conf"""
        if uuid:
            tmpD = self.yamlconfuuid.setdefault('vsw', {}).setdefault(uuid, {}).setdefault(switch, {})
        else:
            tmpD = self.yamlconf.setdefault(switch)
        tmpD = tmpD.setdefault('interface', {})
        if tmpD == runningConf:
            return False  # equal config
        for key, val in runningConf.items():
            if key not in tmpD.keys() and val['state'] != 'absent':
                # Vlan is present in ansible config, but not in new config
                # set vlan to state: 'absent'. In case it is absent already
                # we dont need to set it again. Switch is unhappy to apply
                # same command if service is not present.
                tmpD.setdefault(key, {'state': 'absent', 'vlanid': val['vlanid']})
            if val['state'] != 'absent':
                for key1, val1 in val.items():
                    if isinstance(val1, (dict, list)) and key1 in ['tagged_members', 'ipv4_address', 'ipv6_address']:
                        yamlOut = tmpD.setdefault(key, {}).setdefault(key1, {})
                        dictCompare(yamlOut, val1, key1)
                    if isinstance(val1, str) and key1 == 'vlanid':
                        tmpD.setdefault(key, {}).setdefault(key1, val1)
        return True
