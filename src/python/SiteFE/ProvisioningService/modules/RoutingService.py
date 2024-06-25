#!/usr/bin/env python3
# pylint: disable=line-too-long
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
from SiteRMLibs.MainUtilities import generateMD5
from SiteRMLibs.ipaddr import normalizedip

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

    def __defbgp(self, host):
        """Return def bgp dict. Skip apply if empty"""
        tmpD = {}
        tmpD['asn'] = self.getConfigValue(host, 'private_asn')
        tmpD['belongsTo'] = self.connID
        if not tmpD['asn']:
            del tmpD['asn']
        tmpD['vrf'] = self.getConfigValue(host, 'vrf')
        if not tmpD['vrf']:
            del tmpD['vrf']
        if tmpD:
            tmpD['state'] = 'present'
        return tmpD

    def _getDefaultBGP(self, host):
        """Default yaml dict setup"""
        tmpD = self.yamlconfuuid.setdefault('rst', {}).setdefault(self.connID, {})
        tmpD = tmpD.setdefault(host, {})
        tmpD = tmpD.setdefault('sense_bgp', {})
        tmpD['asn'] = self.getConfigValue(host, 'private_asn')
        tmpD['belongsTo'] = self.connID
        if not tmpD['asn']:
            del tmpD['asn']
        tmpD['vrf'] = self.getConfigValue(host, 'vrf')
        if not tmpD['vrf']:
            del tmpD['vrf']
        if tmpD:
            tmpD['state'] = 'present'
        return tmpD

    def _addOwnRoutes(self, host, rDict):
        """Add Routes"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            val = rDict.get('routeFrom', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
            if val:
                bgpdict.setdefault(f'{iptype}_network', {})
                bgpdict[f'{iptype}_network'][val] =  'present'

    def _addNeighbors(self, host, ruid, rDict):
        """Add Neighbors"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            remasn = rDict.get('routeTo', {}).get('bgp-private-asn', {}).get('value', None)
            remip = rDict.get('nextHop', {}).get(f'{iptype}-address', {}).get('value', None)
            if remasn and remip:
                remip = normalizedip(remip)
                neighbor = bgpdict.setdefault('neighbor', {}).setdefault(iptype, {}).setdefault(remip, {})
                if neighbor:
                    raise Exception('Neighbor already defined. MultiPath neighbors not supported')
                neighbor.setdefault('remote_asn', remasn)
                neighbor.setdefault('state', 'present')
                neighbor.setdefault('route_map', {'in': {f'sense-{ruid}-mapin': 'present'},
                                                  'out': {f'sense-{ruid}-mapout': 'present'}})

    def _addPrefixList(self, host, ruid, rDict):
        """Add Prefix Lists"""
        bgpdict = self._getDefaultBGP(host)
        for iptype in ['ipv4', 'ipv6']:
            rTo = rDict.get('routeFrom', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
            rFrom = rDict.get('routeTo', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
            if rTo:
                prefList = bgpdict.setdefault('prefix_list', {}).setdefault(iptype, {})
                newRoute = prefList.setdefault(rTo, {})
                newRoute[f'sense-{ruid}-to'] = 'present'
                self._addRouteMap(host, f'sense-{ruid}-to', f'sense-{ruid}-mapout', iptype)
            if rFrom:
                prefList = bgpdict.setdefault('prefix_list', {}).setdefault(iptype, {})
                newRoute = prefList.setdefault(rFrom, {})
                newRoute[f'sense-{ruid}-from'] = 'present'
                self._addRouteMap(host, f'sense-{ruid}-from', f'sense-{ruid}-mapin', iptype)

    def _addRouteMap(self, host, match, name, iptype):
        """Add Route Maps"""
        permitst = 10
        bgpdict = self._getDefaultBGP(host)
        if name and match:
            routeMap = bgpdict.setdefault('route_map', {}).setdefault(iptype, {})
            permitst += len(routeMap.get(name, {}))
            routeMap.setdefault(name, {}).setdefault(int(permitst), {match: 'present'})

    def _addparamsrst(self, connDict, switches):
        """Wrapper for add params, to put individual request info too inside dictionary"""
        for host, hostDict in connDict.items():
            if host not in switches:
                continue
            self._getDefaultBGP(host)
            for _, rFullDict in hostDict.items():
                if not self.checkIfStarted(rFullDict):
                    continue
                for rtag, rDict in rFullDict.get('hasRoute', {}).items():
                    ruid = generateMD5(rtag)
                    self._getDefaultBGP(host)
                    self._addOwnRoutes(host, rDict)
                    self._addNeighbors(host, ruid, rDict)
                    self._addPrefixList(host, ruid, rDict)

    def addrst(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for rst)"""
        if 'rst' in activeConfig:
            for connID, connDict in activeConfig['rst'].items():
                self.connID = connID
                self._addparamsrst(connDict, switches)
                if self.firstrun and connID not in self.forceapply:
                    self.forceapply.append(connID)

    def compareBGP(self, switch, runningConf, uuid):
        """Compare L3 BGP"""
        tmpD = self.yamlconfuuid.setdefault("rst", {}).setdefault(uuid, {}).setdefault(switch, {})
        tmpD = tmpD.setdefault('sense_bgp', {})
        # If equal - return no difference
        if tmpD == runningConf:
            return False
        self._getDefaultBGP(switch) # Just in case running empty, force add bgp info
        # If runningConf is empty, then it is different
        if not runningConf:
            return True
        different = False
        for key, val in runningConf.items():
            # ipv6_network, ipv4_network, neighbor, prefix_list, route_map
            if not val:
                continue
            if key in ['ipv6_network', 'ipv4_network', 'prefix_list', 'route_map', 'neighbor']:
                yamlOut = tmpD.setdefault(key, {})
                dictCompare(yamlOut, val)
                different = True
            else:
                tmpD[key] = val
        # Compare empty dict with prepared new conf:
        if self.__defbgp(switch) == tmpD:
            different = False
        return different
