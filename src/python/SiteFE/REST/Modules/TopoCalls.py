#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Topology Calls

Copyright 2023 California Institute of Technology
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
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/08/03
"""
from SiteRMLibs.MainUtilities import evaldict


class TopoCalls:
    """Frontend Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'gettopology': {'allowedMethods': ['GET']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("gettopology", "/json/topo/gettopology", action="gettopology")

    @staticmethod
    def _findConnection(workdata, remMac):
        """Find connections based on MAC aaddress"""
        if not remMac:
            return None
        for switch, switchdata in workdata.items():
            if remMac in switchdata['macs']:
                return {'switch': switch, 'id': switchdata['id']}
        return None

    def _getansdata(self, indata, keys):
        if len(keys) == 1:
            return indata.get('event_data', {}).get('res', {}).get(
                              'ansible_facts', {}).get(keys[0], {})
        if len(keys) == 2:
            return indata.get('event_data', {}).get('res', {}).get(
                              'ansible_facts', {}).get(keys[0], {}).get(keys[1], {})
        return {}

    def _getWANLinks(self, incr):
        """Get WAN Links for visualization"""
        wan_links = {}
        for site in self.config['MAIN'].get('general', {}).get('sites', []):
            for sw in self.config['MAIN'].get(site, {}).get('switch', []):
                if not self.config['MAIN'].get(sw, {}):
                    continue
                if not isinstance(self.config['MAIN'].get(sw, {}).get('ports', None), dict):
                    continue
                for _, val in self.config['MAIN'].get(sw, {}).get('ports', {}).items():
                    if 'wanlink' in val and val['wanlink'] and val.get('isAlias', None):
                        wan_links.setdefault(f"wan{incr}", {"_id": incr,
                                                            "topo": {},
                                                            "DeviceInfo": {"type": "cloud",
                                                                           "name": val['isAlias']}})
                        wan_links[f"wan{incr}"]["topo"].setdefault(val['isAlias'].split(':')[-1],
                                                                   {"device": sw, "port": val})
                        incr += 1
        return wan_links

    def gettopology(self, environ, **kwargs):
        """Return all Switches information"""
        self.responseHeaders(environ, **kwargs)
        workdata = {}
        incr = 0
        # Get all Switch information
        for item in self.dbI.get('switch', orderby=['updatedate', 'DESC'], limit=1000):
            if 'output' not in item:
                continue
            tmpdict = evaldict(item['output'])
            workdata[item['device']] = {'id': incr, 'type': 'switch'}
            incr += 1
            for dkey, keys in {'macs': ['ansible_net_info', 'macs'],
                               'lldp': ['ansible_net_lldp'],
                               'intstats': ['ansible_net_interfaces']}.items():
                workdata[item['device']][dkey] = self._getansdata(tmpdict, keys)
        # Now that we have specific data; lets loop over it and get nodes/links
        out = {}
        for switch, switchdata in workdata.items():
            swout = out.setdefault(switch, {'topo': {},
                                            'DeviceInfo': {'type': 'switch', 'name': switch},
                                            '_id': switchdata['id']})
            # TODO Debug Call
            #  swout['PortInfo'] = switchdata['intstats']
            for key, vals in switchdata['lldp'].items():
                remSwitch = self._findConnection(workdata, vals.get('remote_chassis_id', ""))
                remPort = vals.get('remote_port_id', "")
                if remSwitch and remPort:
                    swout['topo'].setdefault(key, {'device': remSwitch['switch'],
                                                   'port': remPort})
        # Now lets get host information
        for host in self.dbI.get('hosts'):
            parsedInfo = getFileContentAsJson(host.get('hostinfo', ""))
            hostconfig = parsedInfo.get('Summary', {}).get('config', {})
            hostname = hostconfig.get('agent', {}).get('hostname', '')
            lldpInfo = parsedInfo.get('NetInfo', {}).get('lldp', {})
            hout = out.setdefault(hostname, {'topo': {},
                                             'DeviceInfo': {'type': 'server', 'name': hostname, },
                                             '_id': incr})
            incr += 1
            if lldpInfo:
                for intf, vals in lldpInfo.items():
                    remSwitch = self._findConnection(workdata, vals.get('remote_chassis_id', ""))
                    remPort = vals.get('remote_port_id', "")
                    if remSwitch and remPort:
                        hout['topo'].setdefault(intf, {'device': remSwitch['switch'],
                                                       'port': remPort})
            else:
                for intf in hostconfig.get('agent', {}).get('interfaces', []):
                    swintf = hostconfig.get(intf, {}).get('port', '')
                    switch = hostconfig.get(intf, {}).get('switch', '')
                    if switch and swintf:
                        hout['topo'].setdefault(intf, {'device': switch, 'port': swintf})
                # TODO: Debug call!
                #  intfStats = parsedInfo.get('NetInfo', {}).get('interfaces', {}).get(intf, {})
                #  if intfStats:
                #    hout['PortInfo'][intf] = intfStats
        out.update(self._getWANLinks(incr))
        return out
