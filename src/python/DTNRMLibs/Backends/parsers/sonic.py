#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Azure Sonic Additional Parser.
Ansible module issues simple commands and we need
to parse all to our way to represent inside the model
Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/13
"""
import json
import re
from DTNRMLibs.ipaddr import ipVersion, getsubnet
from DTNRMLibs.MainUtilities import getLoggingObject

class Sonic():
    """Default class example for building new parsers"""
    def __init__(self, **kwargs):
        # Facts names is used to match with ansible command.
        # See ansible project template and it depends on which
        # ansible module you use for acessing network device.
        # .e.g. for dell os 9 - dellos9_facts, dellos9_command
        #       for arista eos- arista.eos.eos_facts, arista.eos.eos_command
        #       for sonic - we use normal bash commands and it is mapped
        #                   together with ansible_network_os parameter.
        #                   The issue for sonic is - no real module which works fine...
        # You can find more details here of other possible switches.
        # https://docs.w3cub.com/ansible/
        self.factName = ['sonic_command']
        self.logger = getLoggingObject(config=kwargs['config'], service='SwitchBackends')
        self.runnincConf = {}

    def __getMac(self):
        """Get Mac from runningconfig"""
        mac = "00:00:00:00:00:00"
        if len(self.runnincConf['DEVICE_METADATA']) > 1:
            self.logger.info('WARNING. MAC ADDRESS MIGHT BE INCORRECT! Multiple Devices on SONIC')
        for _host, hostmetadata in self.runnincConf['DEVICE_METADATA'].items():
            mac = hostmetadata['mac']
        return mac

    def getinfo(self, ansibleOut):
        """
        This call is used to get system MAC, which will be used
        for generating topology together with lldp information.
        INPUT:
          Ansible file: /etc/ansible/sense/project/maclldproute.yaml
          1st command (Dell `show system` | Arista `show version | json`)
        OUTPUT:
        {'mac': <MAC_ADDRESS>}
        EXAMPLE:
        {'mac': '4c:76:25:e8:44:c0'}
        """
        del ansibleOut
        mac = self.__getMac()
        return {'mac': mac}

    @staticmethod
    def getlldpneighbors(ansibleOut):
        """
        This call is used to get all lldp neighbors, which are used
        for generating topology.
        INPUT:
          Ansible file: /etc/ansible/sense/project/maclldproute.yaml
          2nd command (Dell `show lldp neighbors detail` | Arista `show lldp neighbors detail | json`)
        SONIC Command Output (Only relevant parts taken):
            Interface:    eth0, via: LLDP, RID: 1, Time: 13 days, 16:10:22
            ChassisID:    mac b0:33:a6:fc:ce:40
            SysName:      Z36-sw.sdsc.edu
            PortID:       local 523
            PortDescr:    AA36/hutton/NRP/MellanoxSN3700

            Interface:    Ethernet16, via: LLDP, RID: 6, Time: 13 days, 16:10:14
            ChassisID:    mac 00:1c:73:03:10:26
            SysName:      oasis1-sw.sdsc.edu
            PortID:       ifname Ethernet7/24/1
            PortDescr:    AA36-400G-sw NRP Demo Sw

            Interface:    Ethernet20, via: LLDP, RID: 5, Time: 13 days, 16:10:16
            ChassisID:    mac 00:1c:73:03:11:12
            SysName:      oasis2-sw.sdsc.edu
            PortID:       ifname Ethernet7/24/1
            PortDescr:    AA36-400G-sw NRP Demo Sw

            Interface:    Ethernet24, via: LLDP, RID: 20, Time: 1 day, 13:46:08
            ChassisID:    mac b4:2e:99:ba:77:c5
            SysName:      k8s-gen4-01.sdsc.optiputer.net
            PortID:       mac 0c:42:a1:80:0e:f8
            PortDescr:    enp65s0
        OUTPUT:
        {<local_port_id>: {'local_port_id': <local_port_id>,
                           'remote_port_id': <remote_port_id>,
                           'remote_chassis_id': <remote_mac_address>}
        }
        EXAMPLE:
        {'hundredGigE 1/1':
              {'local_port_id': 'hundredGigE 1/1',
               'remote_port_id': 'hundredGigE 1/32',
               'remote_system_name': mysuperhost.net,
               'remote_chassis_id': '34:17:eb:4c:1e:80'},
         'hundredGigE 1/2':
              {'local_port_id': 'hundredGigE 1/2',
               'remote_port_id': 'hundredGigE 1/31',
               'remote_system_name': mysuperhost1.net,
               'remote_chassis_id': '34:17:eb:4c:1e:80'},
        }
        """
        # local_port_id -> Interface: <IntfName>,.*
        # remote_system_name -> SysName:      oasis2-sw.sdsc.edu
        # remote_port_id -> PortID:       ifname Ethernet7/24/1
        #      if not matched -> PortDescr:    enp65s0
        # remote_chassis_id -> ChassisID:    mac 00:1c:73:03:10:26
        #    also if PortID:       mac 0c:42:a1:80:0e:f8 - overwrite remote_chassis_id
        regexs = {'local_port_id': {'rules': [r'Interface:\s*([a-zA-Z0-9]*),.*']},
                  'remote_system_name': {'rules': [r'SysName:\s*(.+)']},
                  'remote_port_id': {'action': 'ifnotmatched', 'rules': [r'PortID:\s*ifname\s*(.+)', r'PortDescr:\s*(.+)']},
                  'remote_chassis_id': {'action': 'overwrite', 'rules': [r'ChassisID:\s*mac\s*(.+)', r'PortID:\s*mac\s*(.+)']}}
        out = {}
        for entry in ansibleOut['stdout'].split('-------------------------------------------------------------------------------'):
            entryOut = {}
            for regName, regex in regexs.items():
                match = re.search(regex['rules'][0], entry, re.M)
                if match:
                    entryOut[regName] = match.group(1)
                elif regex.get('action', '') == 'ifnotmatched':
                    match = re.search(regex['rules'][1], entry, re.M)
                    if match:
                        entryOut[regName] = match.group(1)
                if regex.get('action', '') == 'overwrite':
                    match = re.search(regex['rules'][1], entry, re.M)
                    if match:
                        entryOut[regName] = match.group(1)
            if 'local_port_id' in entryOut:
                out[entryOut['local_port_id']] = entryOut
        return out

    def __getRoutes(self, routeType):
        """General Get Routes. INPUT: routeType = (int) 4,6"""
        out = []
        if routeType not in [4, 6]:
            return out
        for route, rDict in self.runnincConf.get('STATIC_ROUTE', {}).items():
            if ipVersion(route) == routeType:
                tmpRoute = {'from': route,
                            'to': rDict.get('nexthop', ''),
                            'vrf': rDict.get('nexthop-vrf', ''),
                            'intf': rDict.get('ifname', ''),
                            }
                out.append({k: v for k, v in tmpRoute.items() if v})
        return out

    def getIPv4Routing(self, ansibleOut):
        """
        This call is used to get all IPv4 routing information
        INPUT:
          Ansible file: /etc/ansible/sense/project/maclldproute.yaml
          3rd command (Dell `show running-config` | Arista `show ip route vrf all | json`)
        OUTPUT:
        [{'to': <TO_RANGE>, 'from': 'FROM_GTW', 'vrf': <VRF_NAME|Optional>, 'intf': <INTF_NAME|Optional>}]
        EXAMPLE:
        [{'to': '0.0.0.0/0', 'from': '192.168.255.254'},
         {'vrf': 'lhcone', 'to': '0.0.0.0/0', 'from': '192.84.86.238'}]
        """
        del ansibleOut
        return self.__getRoutes(routeType=4)


    def getIPv6Routing(self, ansibleOut):
        """
        This call is used to get all IPv6 routing information
        INPUT:
          Ansible file: /etc/ansible/sense/project/maclldproute.yaml
          4th command (Dell `show running-config` | Arista `show ipv6 route vrf all | json`)
        OUTPUT:
        [{'to': <TO_RANGE>, 'from': 'FROM_GTW', 'vrf': <VRF_NAME|Optional>, 'intf': <INTF_NAME|Optional>}]
        EXAMPLE:
        [{'vrf': 'lhcone', 'to': '::/0', 'from': '2605:d9c0:0:ff02::'},
         {'vrf': 'lhcone', 'to': '2605:d9c0:2::/48', 'intf': 'NULL 0'}]
        """
        del ansibleOut
        return self.__getRoutes(routeType=6)

    def parser(self, ansibleOut):
        """General Parser to parse ansible config"""
        out = {}
        # Out must be {'<interface_name>': {'key': 'value'}} OR
        #             {'<interface_name>': {'key': ['value1', 'value2']}
        # dict as value are not supported (not found use case yet for this)
        tmpJson = json.loads(ansibleOut['event_data']['res']['stdout'])
        self.runnincConf = tmpJson
        mac = self.__getMac()
        # Add All Ports
        for portType in ['PORT', 'PORTCHANNEL', 'VLAN']:
            for port, portDict in tmpJson.get(portType, {}).items():
                out[port] = portDict
                out[port]['mac'] = mac
        # Add All PorChannel members
        for port, _portDict in tmpJson.get('PORTCHANNEL_MEMBER', {}).items():
            tmpPort = port.split('|')
            if len(tmpPort) != 2:
                self.logger.info('Warning. PORTCHANNEL_MEMBER member key issue. Key: %s' % port)
                continue
            out.setdefault(tmpPort[0], {})
            out[tmpPort[0]].setdefault('channel-member', [])
            out[tmpPort[0]]['channel-member'].append(tmpPort[1])
        # Add Vlan Interface info, like IPs.
        for port, _portDict in tmpJson.get('VLAN_INTERFACE', {}).items():
            tmpPort = port.split('|')
            if len(tmpPort) != 2:
                self.logger.info('Warning. VLAN_INTERFACE member key issue. Key: %s' % port)
                continue
            out.setdefault(tmpPort[0], {})
            iptype = ipVersion(tmpPort[1])
            tmpIP = tmpPort[1].split('/')
            if iptype == 4:
                out[tmpPort[0]].setdefault('ipv4', [])
                out[tmpPort[0]]['ipv4'].append({'address': tmpIP[0], 'masklen': tmpIP[1]})
            elif iptype == 6:
                out[tmpPort[0]].setdefault('ipv6', [])
                out[tmpPort[0]]['ipv6'].append({'address': tmpIP[0], 'subnet': getsubnet(tmpPort[1])})
        # Get all vlan members, tagged, untagged
        for port, portDict in tmpJson.get('VLAN_MEMBER', {}).items():
            tmpPort = port.split('|')
            if len(tmpPort) != 2:
                self.logger.info('Warning. VLAN_MEMBER member key issue. Key: %s' % port)
                continue
            pOutDict = out.setdefault(tmpPort[0], {})
            tagDict = pOutDict.setdefault(portDict.get('tagging_mode', 'undefinedtagmode'), [])
            tagDict.append(tmpPort[1])
        return out

MODULE = Sonic
