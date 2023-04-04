#!/usr/bin/env python3
# pylint: disable=W0613
"""
Cisco NX Additional Parser.
Ansible module issues simple commands and we need
to parse all to our way to represent inside the model
Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/31
"""
from DTNRMLibs.MainUtilities import getLoggingObject

class CiscoNX():
    """Default class example for building new parsers"""
    def __init__(self, **kwargs):
        self.factName = ['cisco.nxos.nxos_facts', 'cisco.nxos.nxos_command']
        self.defVlanNaming = '%(vlanname)%(vlanid)s'
        self.logger = getLoggingObject(config=kwargs['config'], service='SwitchBackends')
        self.runnincConf = {}

    def __getMac(self):
        """Get Macs from all interfaces"""
        mac = []
        for _, intfDict in self.runnincConf.get('ansible_net_interfaces', {}).items():
            if 'macaddress' in intfDict and intfDict['macaddress']:
                mac.append(intfDict['macaddress'])
        return mac

    def getinfo(self, ansibleOut):
        """Get Info about CiscoNX. Mainly all Macs"""
        mac = self.__getMac()
        return {'mac': mac}

    def getlldpneighbors(self, ansibleOut):
        """Get lldp neighbors from runningconf"""
        return self.runnincConf.get('ansible_net_neighbors', {})
        # return out

    def __getRoutes(self, routeType):
        """General Get Routes. INPUT: routeType = (str) ipv4,ipv6"""
        return self.runnincConf.get('ansible_net_routing', {}).get(routeType, [])

    def getIPv4Routing(self, ansibleOut):
        """Get IPv4 Routing info"""
        return self.__getRoutes(routeType='ipv4')


    def getIPv6Routing(self, ansibleOut):
        """Get IPv6 Routing info"""
        return self.__getRoutes(routeType='ipv6')

    def parser(self, ansibleOut):
        """General Parser to parse ansible config"""
        self.runnincConf = ansibleOut.get('event_data', {}).get('res', {}).get('ansible_facts', {})
        return self.runnincConf.get('ansible_net_interfaces', {})

MODULE = CiscoNX
