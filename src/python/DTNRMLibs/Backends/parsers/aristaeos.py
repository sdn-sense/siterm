#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Arista EOS Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import re
from DTNRMLibs.MainUtilities import getLoggingObject

class AristaEOS():
    """Arista EOS Ansible wrapper."""
    def __init__(self, **kwargs):
        self.factName = ['arista.eos.eos_facts', 'arista.eos.facts', 'arista.eos.eos_command']
        self.defVlanNaming = 'Vlan%(vlanid)s'
        self.logger = getLoggingObject(config=kwargs['config'], service='SwitchBackends')

    @staticmethod
    def getSystemValidPortName(port):
        """Get Systematic port name. MRML expects it without spaces"""
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Also - sometimes lldp reports multiple quotes for interface name from ansible out
        for rpl in [[" ", "_"], ["/", "-"], ['"', ''], ["'", ""]]:
            port = port.replace(rpl[0], rpl[1])
        return port

    @staticmethod
    def _getVlans(inLine):
        """Get All vlans list assigned to port"""
        out = []
        tmpVlans = inLine.split()[-1:][0] # Get the last item from split, e.g. 1127,1779-1799,2803
        if tmpVlans == 'none':
            # Arista needs to define none vlans (if none are configured on the link)
            return out
        for splPorts in tmpVlans.split(','):
            splRange = splPorts.split('-')
            if len(splRange) == 2:
                for i in range(int(splRange[0]), int(splRange[1]) + 1):
                    out.append(i)
            else:
                out.append(splRange[0])
        return out

    def parser(self, ansibleOut):
        """Parse Ansible output and prepare it as other SENSE Services expect it"""
        # Out must be {'<interface_name>': {'key': 'value'}} OR
        #             {'<interface_name>': {'key': ['value1', 'value2']}
        # dict as value are not supported (not found use case yet for this)
        out = {}
        interfaceSt = ""
        for line in ansibleOut['event_data']['res']['ansible_facts']['ansible_net_config'].split('\n'):
            line = line.strip() # Remove all white spaces
            if line == "!" and interfaceSt:
                interfaceSt = "" # This means interface ended!
            elif line.startswith('interface'):
                interfaceSt = line[10:]
            elif interfaceSt:
                if line.startswith('switchport trunk allowed vlan') or line.startswith('switchport access vlan'):
                    for vlan in self._getVlans(line):
                        key = f"Vlan{vlan}"
                        out.setdefault(key, {})
                        out[key].setdefault('tagged', [])
                        out[key]['tagged'].append(self.getSystemValidPortName(interfaceSt))
                else:
                    m = re.match(r'channel-group ([0-9]+) .*', line)
                    if m:
                        chnMemberId = m.group(1)
                        key = f"Port-Channel{chnMemberId}"
                        out.setdefault(key, {})
                        out[key].setdefault('channel-member', [])
                        out[key]['channel-member'].append(self.getSystemValidPortName(interfaceSt))
        return out

    @staticmethod
    def getinfo(ansibleOut):
        """Get Info. So far mainly mac address is used"""
        return {'mac': ansibleOut['systemMacAddress']}

    def getlldpneighbors(self, ansibleOut):
        """Get LLDP Neighbors information"""
        out = {}
        for localPort, neighbors in ansibleOut['lldpNeighbors'].items():
            if not neighbors['lldpNeighborInfo']:
                # Port does not have any neighbors
                continue
            if len(neighbors['lldpNeighborInfo']) > 1:
                continue
            lldpInfo = neighbors['lldpNeighborInfo'][0]
            tmpEntry = {'local_port_id': localPort}
            # Mac comes like: 4c76.25e8.44c0
            # We need to have: 4c:76:25:e8:44:c0
            mac = lldpInfo['chassisId'].replace('.', '')
            split_mac = [mac[index : index + 2] for index in range(0, len(mac), 2)]
            mac = ":".join(split_mac)
            tmpEntry['remote_chassis_id'] = mac
            if 'systemName' in lldpInfo:
                tmpEntry['remote_system_name'] = lldpInfo['systemName']
            if lldpInfo['neighborInterfaceInfo']['interfaceIdType'] == 'macAddress':
                # Means this port goes to server itself
                tmpEntry['remote_port_id'] = self.getSystemValidPortName(lldpInfo['neighborInterfaceInfo']['interfaceDescription'])
            elif lldpInfo['neighborInterfaceInfo']['interfaceIdType'] == 'interfaceName':
                # Means this port goes to another switch
                tmpEntry['remote_port_id'] = self.getSystemValidPortName(lldpInfo['neighborInterfaceInfo']['interfaceId'])
            elif lldpInfo['neighborInterfaceInfo']['interfaceIdType'] == 'local':
                tmpEntry['remote_port_id'] = self.getSystemValidPortName(lldpInfo['neighborInterfaceInfo']['interfaceDescription'])
            out[localPort] = tmpEntry
        return out

    @staticmethod
    def __getRouting(ansibleOut):
        """Get Routing Info from Arista EOS Devices"""
        out = []
        for vrf, routes in ansibleOut.get('vrfs', {}).items():
            for route, routed in routes.get('routes', {}).items():
                for routestats in routed.get('vias', []):
                    nRoute = {}
                    if vrf != 'default':
                        nRoute['vrf'] = vrf
                    nRoute['to'] = route
                    if 'nexthopAddr' in routestats:
                        nRoute['from'] = routestats['nexthopAddr']
                    if 'interface' in routestats:
                        nRoute['intf'] = routestats['interface']
                    out.append(nRoute)
        return out

    def getIPv4Routing(self, ansibleOut):
        """Get IPv4 Routing information"""
        return self.__getRouting(ansibleOut)


    def getIPv6Routing(self, ansibleOut):
        """Get IPv6 Routing information"""
        return self.__getRouting(ansibleOut)

MODULE = AristaEOS
