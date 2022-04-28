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
from DTNRMLibs.MainUtilities import getLoggingObject


class Switch():
    """Ansible Switch Module"""
    def __init__(self, config, sitename):
        self.parsers = parsers.ALL
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service='SwitchBackends')
        # cmd counter is used only for command with items (e.g. sonic, p4)
        # the one switches which do not have ansible modules.
        self.cmdCounter = 0

    @staticmethod
    def activate(_inputDict, _actionState):
        """Activating state actions."""
        return True

    @staticmethod
    def _executeAnsible(playbook):
        """Execute Ansible playbook"""
        # TODO control ansible runner params or use default
        return ansible_runner.run(private_data_dir='/opt/siterm/config/ansible/sense/',
                                  inventory='/opt/siterm/config/ansible/sense/inventory/inventory.yaml',
                                  playbook=playbook,
                                  rotate_artifacts=100)
                                  #debug = True,
                                  #ignore_logging = False)

    def getAnsNetworkOS(self, host):
        """Get Ansible network os from hosts file"""
        return self._getHostConfig(host).get('ansible_network_os', '')

    @staticmethod
    def _getHostConfig(host):
        """Get Ansible Host Config"""
        if not os.path.isfile('/opt/siterm/config/ansible/sense/inventory/host_vars/%s.yaml' % host):
            raise Exception('Ansible config file for %s not available.' % host)
        with open('/opt/siterm/config/ansible/sense/inventory/host_vars/%s.yaml' % host, 'r', encoding='utf-8') as fd:
            out = yaml.load(fd.read())
        return out

    @staticmethod
    def _writeHostConfig(host, out):
        """Write Ansible Host config file"""
        if not os.path.isfile('/opt/siterm/config/ansible/sense/inventory/host_vars/%s.yaml' % host):
            raise Exception('Ansible config file for %s not available.' % host)
        with open('/opt/siterm/config/ansible/sense/inventory/host_vars/%s.yaml' % host, 'w', encoding='utf-8') as fd:
            fd.write(yaml.dump(out))


    def _applyNewConfig(self):
        """Apply new config and run ansible playbook"""
        ansOut = self._executeAnsible('applyconfig.yaml')
        return ansOut

    # 0 - command show version, system. Mainly to get mac address, but might use for more info later.
    # 1 - command to get lldp neighbors details.
    # 2 - ip route information;
    # 3 - ipv6 route information
    # For Dell OS 9 - best is to use show running config;
    # For Arista EOS - show ip route vrf all | json || show ipv6 route vrf all | json
    # For Azure Sonic - we use normal ssh and command line. - There is also Dell Sonic Module
    # but that one depends on sonic-cli - which is broken in latest Azure Image (py2/py3 mainly),
    # See https://github.com/Azure/SONiC/issues/781
    def _getMacLLDPRoute(self):
        """Parser for Mac/LLDP/Route Ansible playbook"""
        def parserWrapper(num, andsiblestdout):
            """Parser wrapper to call specific parser function"""
            cmdList = {0: self.parsers[action].getinfo,
                       1: self.parsers[action].getlldpneighbors,
                       2: self.parsers[action].getIPv4Routing,
                       3: self.parsers[action].getIPv6Routing}
            tmpOut = {}
            try:
                if num not in cmdList:
                    self.logger.info('UNDEFINED FUNCTION num X. Return empty')
                else:
                    tmpOut = cmdList[num](andsiblestdout)
            except NotImplementedError as ex:
                self.logger.debug("Got Not Implemented Error. %s" % ex)
            except (AttributeError, IndexError) as ex:
                self.logger.debug('Got Exception calling switch module for %s and Num %s. Error: %s' % (action, num, ex))
            return tmpOut

        keyMapping = {0: 'info', 1: 'lldp', 2: 'ipv4', 3: 'ipv6'}
        out = {}
        ansOut = self._executeAnsible('maclldproute.yaml')
        for host, _ in ansOut.stats['ok'].items():
            hOut = out.setdefault(host, {})
            for host_events in ansOut.host_events(host):
                if host_events['event'] not in ['runner_on_ok', 'runner_item_on_ok']:
                    continue
                if 'stdout' in host_events['event_data']['res']:
                    # 0 - command to get mainly mac
                    action = host_events['event_data']['task_action']
                    # In case of command, we pass most event_data back to Backend parser
                    # because it does not group output in a single ansible even
                    # as ansible network modules.
                    if action == 'command':
                        # This means it is not using any special ansible module
                        # to communicate with switch/router. In this case, we get
                        # ansible_network_os and use that for loading module
                        action = "%s_command" % self.getAnsNetworkOS(host)
                        # And in case action is not set - means it is badly configured
                        # inside the ansible module by sys/net admin.
                        # We log this inside te log, and ignore that switch
                        if action == '_command':
                            self.logger.info('WARNING. ansible_network_os is not defined for %s host. Ignoring this host' % host)
                            continue
                        hOut.setdefault(keyMapping[self.cmdCounter], {})
                        hOut[keyMapping[self.cmdCounter]] = parserWrapper(self.cmdCounter, host_events['event_data']['res'])
                        self.cmdCounter += 1
                    else:
                        for val, key in keyMapping.items():
                            hOut.setdefault(key, {})
                            hOut[key] = parserWrapper(val, host_events['event_data']['res']['stdout'][val])
        return out

    def _getFacts(self):
        """Get All Facts for all Ansible Hosts"""
        ansOut = self._executeAnsible('getfacts.yaml')
        out = {}
        for host, _ in ansOut.stats['ok'].items():
            out.setdefault(host, {})
            for host_events in ansOut.host_events(host):
                if host_events['event'] != 'runner_on_ok':
                    continue
                action = host_events['event_data']['task_action']
                if action == 'command':
                    # This means it is not using any special ansible module
                    # to communicate with switch/router. In this case, we get
                    # ansible_network_os and use that for loading module
                    action = "%s_command" % self.getAnsNetworkOS(host)
                    # And in case action is not set - means it is badly configured
                    # inside the ansible module by sys/net admin.
                    # We log this inside te log, and ignore that switch
                    if action == '_command':
                        self.logger.info('WARNING. ansible_network_os is not defined for %s host. Ignoring this host' % host)
                        continue
                ansNetIntf = host_events.setdefault('event_data', {}).setdefault('res', {}).setdefault('ansible_facts', {}).setdefault('ansible_net_interfaces', {})
                if action in self.parsers.keys():
                    tmpOut = self.parsers[action].parser(host_events)
                    for portName, portVals in tmpOut.items():
                        ansNetIntf.setdefault(portName, {})
                        ansNetIntf[portName].update(portVals)
                        host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'].setdefault(portName, {})
                        host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'][portName].update(portVals)
                out[host] = host_events
        try:
            maclldproute = self._getMacLLDPRoute()
            for host, hitems in maclldproute.items():
                if host in out:
                    for key, vals in hitems.items():
                        out[host]['event_data']['res']['ansible_facts']['ansible_command_%s' % key] = vals
        finally:
            self.cmdCounter = 0
        return out

    @staticmethod
    def getports(inData):
        """Get ports from ansible output"""
        return inData.get('event_data', {}).get('res', {}).get('ansible_facts', {}).get('ansible_net_interfaces', {}).keys()

    @staticmethod
    def getportdata(inData, port):
        """Get port data from ansible output"""
        return inData.get('event_data', {}).get('res', {}).get('ansible_facts', {}).get('ansible_net_interfaces', {}).get(port, {})

    def getvlans(self, inData):
        """Get vlans from ansible output"""
        # Dell OS 9 has Vlan XXXX
        # Arista EOS has VlanXXXX
        ports = self.getports(inData)
        return [vlan for vlan in ports if vlan.startswith('Vlan')]

    @staticmethod
    def getVlanKey(port):
        """Normalize Vlan Key between diff switches"""
        if port.startswith('Vlan_'):
            return int(port[5:])
        if port.startswith('Vlan '):
            return int(port[5:])
        if port.startswith('Vlan'):
            return int(port[4:])
        return port

    def getvlandata(self, inData, vlan):
        """Get vlan data from ansible output"""
        return self.getportdata(inData, vlan)

    @staticmethod
    def getfactvalues(inData, key):
        """Get custom command output from ansible output, like routing, lldp, mac"""
        return inData.get('event_data', {}).get('res', {}).get('ansible_facts', {}).get(key, {})
