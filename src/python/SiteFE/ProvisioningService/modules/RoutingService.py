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

def singleDictCompare(inDict, oldDict):
    """Compare single dict and set any remaining items
       from current ansible yaml as absent in new one if
       it's status is present"""
    # If equal - return
    if inDict == oldDict:
        return
    for oldKey, oldState in oldDict.items():
        if oldState == 'present' and oldKey not in inDict.keys():
            # Means current state is present, but IP is not anymore in
            # new config
            inDict[oldKey] = 'absent'
    return

class RoutingService():
    """ Routing Service Class. Adds all activeDelta params,
    compares with running active config, make things absent if they
    are not existing anymore"""
    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    def _getDefaultBGP(self, host, *args):
        """Default yaml dict setup"""
        tmpD = self.yamlconf.setdefault(host, {})
        tmpD = tmpD.setdefault('sense_bgp', {})
        tmpD['asn'] = self.getConfigValue(host, 'private_asn', True)
        tmpD['vrf'] = self.getConfigValue(host, 'vrf')
        if not tmpD['vrf']:
            del tmpD['vrf']
        tmpD['state'] = 'present'
        return tmpD

    def _addOwnRoutes(self, host, ruid, rDict):
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
        for iptype in ['ipv4', 'ipv6']:
            val = rDict.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
            if val:
                bgpdict.setdefault('%s_network' % iptype, {})
                bgpdict['%s_network' % iptype][val] =  'present'

    def _addNeighbors(self, host, ruid, rDict):
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
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
        bgpdict = self._getDefaultBGP(host, ruid, rDict)
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
                            self._getDefaultBGP(host, ruid, rDict)
                            self._addOwnRoutes(host, ruid, rDict)
                            self._addNeighbors(host, ruid, rDict)
                            self._addPrefixList(host, ruid, rDict)

    @staticmethod
    def compareNeighbRouteMap(routeNew, routeOld):
        """Compare Neighbour Route map"""
        for rtype in ['in', 'out']:
            routeNew.setdefault(rtype, {})
            for key, val in routeOld[rtype].items():
                if key not in routeNew[rtype].keys():
                    if val == 'present':
                        routeNew[rtype]['key'] = 'absent'

    def compareNeighbors(self, neigNew, neigOld):
        """Compare neighbors"""
        if neigNew == neigOld:
            return
        for neighKey, neighDict in neigOld.items():
            if neighKey in neigNew.keys() and neighDict == neigNew[neighKey]:
                continue
            if neighKey not in neigNew.keys():
                if neighDict['state'] == 'present':
                    # Need to make it absent and add to neigNew
                    neigNew.setdefault(neighKey, neighDict)
                    neigNew[neighKey]['state'] = 'absent'
            # They are not equal and it exists in new dictionary.
            # So diff can be in route_map or remote_asn
            elif neigNew[neighKey].get('route_map', {}) != neighDict.get('route_map', {}):
                self.compareNeighbRouteMap(neigNew[neighKey].get('route_map', {}), neighDict.get('route_map', {}))

    @staticmethod
    def compareRouteMap(newMap, oldMap):
        """Compare Route maps"""
        # If equal - return
        if newMap == oldMap:
            return
        for rmapName, rmap in oldMap.items():
            for permitVal, vals in rmap.items():
                for route, state in vals.items():
                    if rmapName not in newMap.keys() and state == 'present':
                        pVal = newMap.setdefault(rmapName, {}).setdefault(permitVal, {})
                        pVal[route] = 'absent'
        return

    def compareBGP(self, switch, runningConf):
        """Compare L3 BGP"""
        if self.yamlconf[switch]['sense_bgp'] == runningConf:
            return # equal config
        for key, val in runningConf.items():
            # ipv6_network, ipv4_network, neighbor, prefix_list, route_map
            if key in ['ipv6_network', 'ipv4_network', 'prefix_list']:
                yamlOut = self.yamlconf[switch]['sense_bgp'].setdefault(key, {})
                singleDictCompare(yamlOut, val)
            elif key == 'route_map':
                yamlOut = self.yamlconf[switch]['sense_bgp'].setdefault(key, {})
                self.compareRouteMap(yamlOut, val)
            elif key == 'neighbor':
                yamlOut = self.yamlconf[switch]['sense_bgp'].setdefault(key, {})
                self.compareNeighbors(yamlOut, val)
