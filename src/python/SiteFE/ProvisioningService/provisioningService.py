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
UpdateDate              : 2021/11/08
"""
import sys
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import generateMD5
from DTNRMLibs.Backends.main import Switch


class ProvisioningService():
    """Provisioning service communicates with Local controllers and applies
    network changes."""
    def __init__(self, config, sitename):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='ProvisioningService')
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        workDir = self.config.get('general', 'privatedir') + "/ProvisioningService/"
        createDirs(workDir)
        self.yamlconf = {}

    def __cleanup(self):
        """Cleanup yaml conf output"""
        self.yamlconf = {}

    def __getdefaultVlan(self, host, port, portDict):
        """Default yaml dict setup"""
        tmpD = self.yamlconf.setdefault(host, {})
        tmpD = tmpD.setdefault('interface', {})
        if 'hasLabel' not in portDict or 'value' not in portDict['hasLabel']:
            raise Exception('Bad running config. Missing vlan entry: %s %s %s' % (host, port, portDict))
        vlan = portDict['hasLabel']['value']
        vlanName = self.switch._getSwitchPortName(host, 'Vlan%s' % vlan, vlan)
        vlanDict = tmpD.setdefault(vlanName, {})
        vlanDict.setdefault('name', vlanName)
        return vlanDict

    def _addTaggedInterfaces(self, host, port, portDict):
        """Add Tagged Interfaces to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        portName = self.switch._getSwitchPortName(host, port)
        vlanDict.setdefault('tagged_members', [])
        vlanDict['tagged_members'].append({'port': portName, 'state': 'present'})

    def _addIPv4Address(self, host, port, portDict):
        """Add IPv4 to expected yaml conf"""
        # For IPv4 - only single IP is supported. No secondary ones
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv4-address', {}).get('value', ""):
            vlanDict.setdefault('ip_address', {})
            vlanDict['ip_address'] = {'ip': portDict['hasNetworkAddress']['ipv4-address']['value'], 'state': 'present'}

    def _addIPv6Address(self, host, port, portDict):
        """Add IPv6 to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        if portDict.get('hasNetworkAddress', {}).get('ipv6-address', {}).get('value', ""):
            vlanDict.setdefault('ip6_address', {})
            vlanDict['ip6_address'] = {'ip': portDict['hasNetworkAddress']['ipv6-address']['value'], 'state': 'present'}

    def _presetDefaultParams(self, host, port, portDict):
        vlanDict = self.__getdefaultVlan(host,  port, portDict)
        vlanDict['description'] = portDict.get('_params', {}).get('tag', "SENSE-VLAN-Without-Tag")
        vlanDict['state'] = 'present'
        # set default name
        return vlanDict

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


    def _getDefaultBGP(self, host, *args):
        """Default yaml dict setup"""
        tmpD = self.yamlconf.setdefault(host, {})
        tmpD = tmpD.setdefault('sense_bgp', {})
        # TODO: Try except. In case not defined in config. NoOptionError will happen
        myasn = self.config.get(host, 'private_asn')
        tmpD['asn'] = myasn
        tmpD['state'] = 'present'
        return tmpD

    def _addOwnRoutes(self, host, ruid, rDict):
        #  'routeFrom': {'ipv6-prefix-list': {'type': 'ipv6-prefix-list',
        #                            'value': '2605:d9c0:2:fff1::/64'},
        #                'key': 'urn:ogf:network:ultralight.org:2013:dellos9_s0:service+rst-ipv6:table+365eeb6f-9fb8-47a9-a131-d9c14838d112:route+wan-1:from',
        #                'type': 'routeFrom'},
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
        for iptype in ['ipv4', 'ipv6']:
            val = rDict.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            if val:
                bgpdict.setdefault('%s_network' % iptype, [])
                bgpdict['%s_network' % iptype].append({'address': val, 'state': 'present'})

    def _addNeighbors(self, host, ruid, rDict):
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
        for iptype in ['ipv4', 'ipv6']:
            remasn = rDict.get('routeTo', {}).get('bgp-private-asn', {}).get('value', None)
            remip = rDict.get('nextHop', {}).get('%s-address' % iptype, {}).get('value', None)
            if remasn and remip:
                neighbor = bgpdict.setdefault('neighbor', {}).setdefault(iptype, [])
                newNeighbor = {'remote_asn': remasn, 'ip': remip, 'state': 'present',
                               'route_map': {'in': 'sense-%s-mapin' % ruid, 'out': 'sense-%s-mapout' % ruid}}
                neighbor.append(newNeighbor)

    def _addPrefixList(self, host, ruid, rDict):
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
        for iptype in ['ipv4', 'ipv6']:
            rTo = rDict.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            rFrom = rDict.get('routeTo', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            prefList = bgpdict.setdefault('prefix_list', [])
            if rTo:
                prefList.append({'name': 'sense-%s-to' % ruid, 'iprange': rTo, 'state': 'present', 'iptype': iptype})
                self._addRouteMap(host, 'sense-%s-to' % ruid, 'sense-%s-mapout' % ruid)
            if rFrom:
                prefList.append({'name': 'sense-%s-from' % ruid, 'iprange': rFrom, 'state': 'present', 'iptype': iptype})
                self._addRouteMap(host, 'sense-%s-from' % ruid, 'sense-%s-mapin' % ruid)

    def _addRouteMap(self, host, match, name):
        bgpdict = self._getDefaultBGP(host)
        if name and match:
            routeMap = bgpdict.setdefault('route_map', [])
            routeMap.append({'name': name, 'match': match, 'state': 'present'})


    def addrst(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for rst)"""
        if 'rst' in activeConfig:
            for _, connDict in activeConfig['rst'].items():
                if not self.checkIfStarted(connDict):
                    continue
                for host, hostDict in connDict.items():
                    if host not in switches:
                        continue
                    for rtype, rFullDict in hostDict.items():
                        for rtag, rDict in rFullDict.get('hasRoute', {}).items():
                            ruid = generateMD5(rtag)
                            self._getDefaultBGP(host, ruid, rDict)
                            self._addOwnRoutes(host, ruid, rDict)
                            self._addNeighbors(host, ruid, rDict)
                            self._addPrefixList(host, ruid, rDict)


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

    @staticmethod
    def compareTaggedMembers(newMembers, oldMembers):
        """Compare tagged members between expected and running conf"""
        # If equal - no point to loop. return
        if newMembers == oldMembers:
            return newMembers
        # Otherwise, loop via old members, and see which one is gone
        # It might be all remain in place and just new member was added.
        for mdict in oldMembers:
            if mdict['state'] == 'absent':
                # Ignoring absent and not adding it again.
                continue
            found = False
            for ndict in newMembers:
                if mdict == ndict:
                    # We found same dict in tagged ports. break
                    found = True
                    break
                if mdict['port'] == ndict['port']:
                    found = True
                    break
            if not found:
                # Means this port in oldMembers was removed.
                # Need to append it with state absent
                mdict['state'] = 'absent'
                newMembers.append(mdict)
        return newMembers

    def compareIpAddress(self, newIPs, oldIPs):
        """Compare ip addresses between expected and running conf"""
        # If equal - return
        if newIPs == oldIPs:
            return newIPs
        if oldIPs['state'] == 'absent':
            return newIPs
        self.logger.info('IP rewrite. %s to %s. No support for multiple IPv4 on vlan' % (oldIPs, newIPs))
        return newIPs


    def compareActiveWithRunning(self, switch, runningConf):
        """Compare expected and running conf"""
        if self.yamlconf[switch]['interface'] == runningConf:
            return # equal config
        for key, val in runningConf.items():
            if key not in self.yamlconf[switch]['interface'].keys():
                if val['state'] != 'absent':
                    # Vlan is present in switch config, but not in new config
                    # set vlan to state: 'absent'. In case it is absent already
                    # we dont need to set it again. Switch is unhappy to apply
                    # same command if service is not present.
                    self.yamlconf[switch]['interface'].setdefault(key, {'state': 'absent'})
                continue
            for key1, val1 in val.items():
                if isinstance(val1, (dict, list)) and key1 in ['tagged_members', 'ip_address', 'ip6_address']:
                    if key1 == 'tagged_members':
                        yamlOut = self.yamlconf[switch]['interface'][key].setdefault(key1, [])
                        self.compareTaggedMembers(yamlOut, val1)
                    if key1 in ['ip_address', 'ip6_address']:
                        yamlOut = self.yamlconf[switch]['interface'][key].setdefault(key1, {})
                        self.compareIpAddress(yamlOut, val1)
                elif isinstance(val1, (dict, list)):
                    raise Exception('Got unexpected dictionary in comparison %s' % val)

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
            self.yamlconf.setdefault(host, {'interface': {}})
            for key, val in curActiveConf.items():
                if key == 'interface':
                    # Pass val to new function which does comparison
                    self.compareActiveWithRunning(host, curActiveConf['interface'])
                    continue
                self.yamlconf[host][key] = val
            # Into the host itself append all except interfaces key
            if not curActiveConf == self.yamlconf[host]:
                configChanged = True
                self.switch.plugin._writeHostConfig(host, self.yamlconf[host])
        if configChanged:
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
