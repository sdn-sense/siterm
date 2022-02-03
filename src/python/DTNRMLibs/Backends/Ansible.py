#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Ansible Backend
Calls Ansible Runnner to get Switch configs, Apply configs,
Calls Parser if available to parse additional Info from switch Out

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import os
import yaml
import ansible_runner
from DTNRMLibs.Backends import parsers

# =======================
#  Main caller - calls are done only by Provisioning Service
# =======================

class Actions():
    """ Main caller """

    def activate(self, inputDict, actionState):
        """Activating state actions."""
        return True


class Switch(Actions):
    """
    Ansible Switch Module
    """
    def __init__(self):
        self.parsers = parsers.ALL

    def _executeAnsible(self, playbook):
        # TODO control ansible runner params or use default
        ansRunner = ansible_runner.run(private_data_dir='/etc/ansible/sense/',
                                       inventory='/etc/ansible/sense/inventory/inventory.yaml',
                                       playbook=playbook)
                                       #debug = True,
                                       #ignore_logging = False)
        return ansRunner


    def _getHostConfig(self, host):
        if not os.path.isfile('/etc/ansible/sense/inventory/host_vars/%s.yaml' % host):
            raise Exception('Ansible config file for %s not available.' % host)
        with open('/etc/ansible/sense/inventory/host_vars/%s.yaml' % host, 'r', encoding='utf-8') as fd:
            out = yaml.load(fd.read())
        return out

    def _writeHostConfig(self, host, out):
        if not os.path.isfile('/etc/ansible/sense/inventory/host_vars/%s.yaml' % host):
            raise Exception('Ansible config file for %s not available.' % host)
        with open('/etc/ansible/sense/inventory/host_vars/%s.yaml' % host, 'w', encoding='utf-8') as fd:
            fd.write(yaml.dump(out))


    def _applyNewConfig(self):
        ansOut = self._executeAnsible('applyconfig.yaml')
        return ansOut

    # 0 - command show version, system. Mainly to get mac address, but might use for more info later.
    # 1 - command to get lldp neighbors details.
    # 2 - ip route information; 
    # 3 - ipv6 route information 
    # For Dell OS 9 - best is to use show running config;
    # For Arista EOS - show ip route vrf all | json || show ipv6 route vrf all | json
    def _getMacLLDPRoute(self):
        def parserWrapper(num, host_events):
            tmpOut = {}
            try:
                if num == 0:
                    tmpOut = self.parsers[action].getinfo(host_events['event_data']['res']['stdout'][0])
                elif num == 1:
                    tmpOut = self.parsers[action].getlldpneighbors(host_events['event_data']['res']['stdout'][1])
                elif num == 2:
                    tmpOut = self.parsers[action].getIPv4Routing(host_events['event_data']['res']['stdout'][2])
                elif num == 3:
                    tmpOut = self.parsers[action].getIPv6Routing(host_events['event_data']['res']['stdout'][3])
                else:
                    print('UNDEFINED FUNCTION num X. Return empty')
            except NotImplementedError as ex:
                print("Got Not Implemented Error. %s" % ex)
            except (AttributeError, IndexError) as ex:
                print('Got Exception calling switch module for %s and Num %s. Error: %s' % (action, num, ex))
            return tmpOut

        out = {}
        ansOut = self._executeAnsible('maclldproute.yaml')
        for host, _ in ansOut.stats['ok'].items():
            hOut = out.setdefault(host, {'info': {}, 'lldp': {}, 'ipv4': {}, 'ipv6': {}})
            for host_events in ansOut.host_events(host):
                if host_events['event'] != 'runner_on_ok':
                    continue
                if 'stdout' in host_events['event_data']['res']:
                    # 0 - command to get mainly mac
                    action = host_events['event_data']['task_action']
                    hOut['info'] = parserWrapper(0, host_events)
                    # 1 - command to get lldp neighbors detail
                    hOut['lldp'] = parserWrapper(1, host_events)
                    # 2 - command to get IPv4 routing info
                    hOut['ipv4'] = parserWrapper(2, host_events)
                    # 3 - command to get IPv6 routing info
                    hOut['ipv6'] = parserWrapper(3, host_events)
        return out

    def _appendCustomInfo(self, maclldproute, host, host_events):
        if host in maclldproute:
            for key, out in maclldproute[host].items():
                host_events['event_data']['res']['ansible_facts']['ansible_command_%s' % key] = out
        return host_events


    def _getFacts(self):
        maclldproute = self._getMacLLDPRoute()
        ansOut = self._executeAnsible('getfacts.yaml')
        out = {}
        for host, _ in ansOut.stats['ok'].items():
            out.setdefault(host, {})
            for host_events in ansOut.host_events(host):
                if host_events['event'] != 'runner_on_ok':
                    continue
                if 'ansible_facts' in host_events['event_data']['res'] and  \
                     'ansible_net_interfaces' in host_events['event_data']['res']['ansible_facts']:
                    action = host_events['event_data']['task_action']
                    if action in self.parsers.keys():
                        tmpOut = self.parsers[action].parser(host_events)
                        for portName, portVals in tmpOut.items():
                            host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'].setdefault(portName, {})
                            host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'][portName].update(portVals)
                host_events = self._appendCustomInfo(maclldproute, host, host_events)
                out[host] = host_events
        return out

    @staticmethod
    def getports(inData):
        """ Get ports from ansible output """
        return inData['event_data']['res']['ansible_facts']['ansible_net_interfaces'].keys()

    @staticmethod
    def getportdata(inData, port):
        """ Get port data from ansible output """
        return inData['event_data']['res']['ansible_facts']['ansible_net_interfaces'][port]

    def getvlans(self, inData):
        """ Get vlans from ansible output """
        # Dell OS 9 has Vlan XXXX
        # Arista EOS has VlanXXXX
        ports = self.getports(inData)
        return [vlan for vlan in ports if vlan.startswith('Vlan')]

    @staticmethod
    def getVlanKey(port):
        if port.startswith('Vlan_'):
            return int(port[5:])
        if port.startswith('Vlan '):
            return int(port[5:])
        if port.startswith('Vlan'):
            return int(port[4:])
        return port

    def getvlandata(self, inData, vlan):
        """ Get vlan data from ansible output """
        return self.getportdata(inData, vlan)

    @staticmethod
    def getfactvalues(inData, key):
        """ Get custom command output from ansible output, like routing, lldp, mac """
        return inData['event_data']['res']['ansible_facts'][key]
