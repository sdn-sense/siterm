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
    """ Arista EOS Ansible wrapper. """
    def __init__(self):
        self.factName = ['arista.eos.eos_facts', 'arista.eos.eos_command']
        self.logger = getLoggingObject()

    @staticmethod
    def _getSystemValidPortName(port):
        """ get Systematic port name. MRML expects it without spaces """
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Also - sometimes lldp reports multiple quotes for interface name from ansible out
        for rpl in [[" ", "_"], ["/", "-"], ['"', ''], ["'", ""]]:
            port = port.replace(rpl[0], rpl[1])
        return port

    def _getVlans(self, inLine):
        """ Get All vlans list assigned to port """
        out = []
        tmpVlans = inLine.split()[-1:][0] # Get the last item from split, e.g. 1127,1779-1799,2803
        for splPorts in tmpVlans.split(','):
            splRange = splPorts.split('-')
            if len(splRange) == 2:
                for i in range(int(splRange[0]), int(splRange[1]) + 1):
                    out.append(i)
            else:
                out.append(splRange[0])
        return out

    def parser(self, ansibleOut):
        """ Parse Ansible output and prepare it as other SENSE Services expect it """
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
                        key = "Vlan%s" % vlan
                        out.setdefault(key, {})
                        out[key].setdefault('tagged', [])
                        out[key]['tagged'].append(self._getSystemValidPortName(interfaceSt))
                else:
                    m = re.match(r'channel-group ([0-9]+) .*', line)
                    if m:
                        chnMemberId = m.group(1)
                        key = "Port-Channel%s" % chnMemberId
                        out.setdefault(key, {})
                        out[key].setdefault('channel-member', [])
                        out[key]['channel-member'].append(self._getSystemValidPortName(interfaceSt))
        return out

    def getinfo(self, ansibleOut):
        """ Get Info. So far mainly mac address is used """
        return {'mac': ansibleOut['systemMacAddress']}

    def getlldpneighbors(self, ansibleOut):
        """ Get LLDP Neighbors information """
        out = {}
        for localPort, neighbors in ansibleOut['lldpNeighbors'].items():
            if not neighbors['lldpNeighborInfo']:
                # Port does not have any neighbors
                continue
            if len(neighbors['lldpNeighborInfo']) > 1:
                #self.logger.debug('Port %s has 2 neighbors. How do we deal with it. Out: %s. Ignoring LLDP for this port' % (localPort, neighbors))
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
                tmpEntry['remote_port_id'] = lldpInfo['neighborInterfaceInfo']['interfaceDescription']
            elif lldpInfo['neighborInterfaceInfo']['interfaceIdType'] == 'interfaceName':
                # Means this port goes to another switch
                tmpEntry['remote_port_id'] = lldpInfo['neighborInterfaceInfo']['interfaceId']
            out[localPort] = tmpEntry
        return out

    def __getRouting(self, ansibleOut):
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
        """ Get IPv4 Routing information """
        #self.logger.debug('Called get getIPv4Routing AristaEOS')
        return self.__getRouting(ansibleOut)


    def getIPv6Routing(self, ansibleOut):
        """ Get IPv6 Routing information """
        #self.logger.debug('Called get getIPv6Routing AristaEOS')
        return self.__getRouting(ansibleOut)

MODULE = AristaEOS
