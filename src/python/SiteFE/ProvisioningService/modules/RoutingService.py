#!/usr/bin/env python3
"""Routing Service (BGP Control) preparation/comparison

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
from DTNRMLibs.MainUtilities import generateMD5

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
            # If val has state and it is absent, delete inDictKey also
            if 'state' in val and val['state'] == 'absent':
                # Means everything already below is absent
                del inDict[key]
            continue
        if val == 'present' and key not in inDict.keys():
            # Means current state is present, but model does not know anything
            inDict[key] = 'absent'
        elif val not in ['present', 'absent']:
            # Ensure we pre-keep all other keys
            inDict[key] = val
    return

class RoutingService():
    """ Routing Service Class. Adds all activeDelta params,
    compares with running active config, make things absent if they
    are not existing anymore"""
    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()


    def _getDefaultBGP(self, host):
        """Default yaml dict setup"""
        tmpD = self.yamlconf.setdefault(host, {})
        tmpD = tmpD.setdefault('sense_bgp', {})
        tmpD['asn'] = self.getConfigValue(host, 'private_asn')
        if not tmpD['asn']:
            del tmpD['asn']
        tmpD['vrf'] = self.getConfigValue(host, 'vrf')
        if not tmpD['vrf']:
            del tmpD['vrf']
        tmpD['state'] = 'present'
        return tmpD

    def _addOwnRoutes(self, host, rDict):
        """Add Routes"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            val = rDict.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            if val:
                bgpdict.setdefault('%s_network' % iptype, {})
                bgpdict['%s_network' % iptype][val] =  'present'

    def _addNeighbors(self, host, ruid, rDict):
        """Add Neighbors"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            remasn = rDict.get('routeTo', {}).get('bgp-private-asn', {}).get('value', None)
            remip = rDict.get('nextHop', {}).get('%s-address' % iptype, {}).get('value', None)
            if remasn and remip:
                neighbor = bgpdict.setdefault('neighbor', {}).setdefault(iptype, {}).setdefault(remip, {})
                if neighbor:
                    raise Exception('Neighbor already defined. MultiPath neighbors not supported')
                neighbor.setdefault('remote_asn', remasn)
                neighbor.setdefault('state', 'present')
                neighbor.setdefault('route_map', {'in': {'sense-%s-mapin' % ruid: 'present'},
                                                  'out': {'sense-%s-mapout' % ruid: 'present'}})

    def _addPrefixList(self, host, ruid, rDict):
        """Add Prefix Lists"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            rTo = rDict.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            rFrom = rDict.get('routeTo', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            prefList = bgpdict.setdefault('prefix_list', {}).setdefault(iptype, {})
            if rTo:
                prefList[rTo] = {'sense-%s-to' % ruid: 'present'}
                self._addRouteMap(host, 'sense-%s-to' % ruid, 'sense-%s-mapout' % ruid, iptype)
            if rFrom:
                prefList[rFrom] = {'sense-%s-from' % ruid: 'present'}
                self._addRouteMap(host, 'sense-%s-from' % ruid, 'sense-%s-mapin' % ruid, iptype)

    def _addRouteMap(self, host, match, name, iptype):
        """Add Route Maps"""
        permitst = 10
        bgpdict = self._getDefaultBGP(host)
        if name and match:
            routeMap = bgpdict.setdefault('route_map', {}).setdefault(iptype, {})
            permitst += len(routeMap.get(name, {}))
            routeMap.setdefault(name, {}).setdefault(int(permitst), {match: 'present'})

    def addrst(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for rst)"""
        if 'rst' in activeConfig:
            for _, connDict in activeConfig['rst'].items():
                if not self.checkIfStarted(connDict):
                    continue
                for host, hostDict in connDict.items():
                    if host not in switches:
                        continue
                    for _, rFullDict in hostDict.items():
                        for rtag, rDict in rFullDict.get('hasRoute', {}).items():
                            ruid = generateMD5(rtag)
                            self._getDefaultBGP(host)
                            self._addOwnRoutes(host, rDict)
                            self._addNeighbors(host, ruid, rDict)
                            self._addPrefixList(host, ruid, rDict)
        for host in switches:
            self._getDefaultBGP(host)

    def compareBGP(self, switch, runningConf):
        """Compare L3 BGP"""
        if self.yamlconf[switch]['sense_bgp'] == runningConf:
            return # equal config
        for key, val in runningConf.items():
            # ipv6_network, ipv4_network, neighbor, prefix_list, route_map
            if key in ['ipv6_network', 'ipv4_network', 'prefix_list', 'route_map', 'neighbor']:
                yamlOut = self.yamlconf[switch]['sense_bgp'].setdefault(key, {})
                dictCompare(yamlOut, val)
