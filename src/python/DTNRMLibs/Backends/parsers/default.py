#!/usr/bin/env python3
"""
Default example of ansible parser module;
This should not be used in production, and it is only
for developing new modules for other switch vendors.

All these functions are mandatory in any of switch module.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/27
"""
from DTNRMLibs.MainUtilities import getLoggingObject

# Class Name, this is also used below MODULE= <ClassName>
# Ansible module will preload all parsers by MODULE variable
class Default():
    """ Default class example for building new parsers """
    def __init__(self):
        # Facts names is used to match with ansible command.
        # See ansible project template and it depends on which
        # ansible module you use for acessing network device.
        # .e.g. for dell os 9 - dellos9_facts, dellos9_command
        #       for arista eos- arista.eos.eos_facts, arista.eos.eos_command
        # You can find more details here of other possible switches.
        # https://docs.w3cub.com/ansible/
        self.factName = ['default_facts', 'default_command']
        self.logger = getLoggingObject()

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
        raise NotImplementedError('Default getinfo call not implemented')

    def getlldpneighbors(self, ansibleOut):
        """
        This call is used to get all lldp neighbors, which are used
        for generating topology.
        INPUT:
          Ansible file: /etc/ansible/sense/project/maclldproute.yaml
          2nd command (Dell `show lldp neighbors detail` | Arista `show lldp neighbors detail | json`)
        OUTPUT:
        {<local_port_id>: {'local_port_id': <local_port_id>,
                           'remote_port_id': <remote_port_id>,
                           'remote_chassis_id': <remote_mac_address>}
        }
        EXAMPLE:
        {'hundredGigE 1/1':
              {'local_port_id': 'hundredGigE 1/1',
               'remote_port_id': 'hundredGigE 1/32',
               'remote_chassis_id': '34:17:eb:4c:1e:80'},
         'hundredGigE 1/2':
              {'local_port_id': 'hundredGigE 1/2',
               'remote_port_id': 'hundredGigE 1/31',
               'remote_chassis_id': '34:17:eb:4c:1e:80'},
        }
        """
        raise NotImplementedError('Default getinfo call not implemented')

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
        raise NotImplementedError('Default getIPv4Routing call not implemented')


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
        raise NotImplementedError('Default getIPv4Routing call not implemented')

    def parser(self, ansibleOut):
        """ Parse Ansible output and prepare it as other SENSE Services expect it """
        # Out must be {'<interface_name>': {'key': 'value'}} OR
        #             {'<interface_name>': {'key': ['value1', 'value2']}
        # dict as value are not supported (not found use case yet for this)
        raise NotImplementedError('Default parser call not implemented')

MODULE = Default
