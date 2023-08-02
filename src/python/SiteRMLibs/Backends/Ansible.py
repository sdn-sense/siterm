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
from SiteRMLibs.Backends import parsers
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.CustomExceptions import ConfigException

class Switch():
    """Ansible Switch Module"""
    def __init__(self, config, sitename):
        self.parsers = parsers.ALL
        self.defVlans = parsers.MAPPING
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service='SwitchBackends')
        self.ansibleErrs = {}

    @staticmethod
    def activate(_inputDict, _actionState):
        """Activating state actions."""
        return True

    def __getAnsErrors(self, ansOut):
        """Get Ansible errors"""
        for fkey in ['dark', 'failures']:
            for host, _ in ansOut.stats[fkey].items():
                for hostEvents in ansOut.host_events(host):
                    err = hostEvents.get('event_data', {}).get('res', {})
                    self.ansibleErrs.setdefault(host, {}).setdefault(fkey, [])
                    self.ansibleErrs[host][fkey].append(err)
                    self.logger.info('Ansible Error for %s: %s', host, err)

    def _getInventoryInfo(self, hosts=None):
        """Get Inventory Info. If hosts specified, only return for specific hosts"""
        out = {}
        with open(self.config.get('ansible', 'inventory'), 'r', encoding='utf-8') as fd:
            out = yaml.safe_load(fd.read())
        if hosts:
            tmpOut = {}
            for osName, oshosts in out.items():
                for hostname, hostdict in oshosts.get('hosts', {}).items():
                    if hostname in hosts:
                        tmpOut.setdefault(osName, {'hosts': {}})
                        tmpOut[osName]['hosts'].setdefault(hostname, hostdict)
            return tmpOut
        return out

    def _executeAnsible(self, playbook, hosts=None):
        """Execute Ansible playbook"""
        return ansible_runner.run(private_data_dir=self.config.get('ansible', 'private_data_dir'),
                                  inventory=self._getInventoryInfo(hosts),
                                  playbook=playbook,
                                  rotate_artifacts=self.config.get('ansible', 'rotate_artifacts'),
                                  debug=self.config.getboolean('ansible', 'debug'),
                                  ignore_logging=self.config.getboolean('ansible', 'ignore_logging'))

    def getAnsNetworkOS(self, host):
        """Get Ansible network os from hosts file"""
        return self.getHostConfig(host).get('ansible_network_os', '')

    def getHostConfig(self, host):
        """Get Ansible Host Config"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir')}/{host}.yaml"
        if not os.path.isfile(fname):
            raise Exception(f'Ansible config file for {host} not available.')
        with open(fname, 'r', encoding='utf-8') as fd:
            out = yaml.safe_load(fd.read())
        return out

    def _writeHostConfig(self, host, out):
        """Write Ansible Host config file"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir')}/{host}.yaml"
        if not os.path.isfile(fname):
            raise Exception(f'Ansible config file for {host} not available.')
        with open(fname, 'w', encoding='utf-8') as fd:
            fd.write(yaml.dump(out))


    def _applyNewConfig(self, hosts=None):
        """Apply new config and run ansible playbook"""
        ansOut = {}
        try:
            ansOut = self._executeAnsible('applyconfig.yaml', hosts)
        except ValueError as ex:
            raise ConfigException(f"Got Value Error. Ansible configuration exception {ex}") from ex
        self.__getAnsErrors(ansOut)
        return ansOut


    def _getFacts(self, hosts=None):
        """Get All Facts for all Ansible Hosts"""
        self.ansibleErrs = {}
        ansOut = {}
        try:
            ansOut = self._executeAnsible('getfacts.yaml', hosts)
        except ValueError as ex:
            raise ConfigException(f"Got Value Error. Ansible configuration exception {ex}") from ex
        out = {}
        for host, _ in ansOut.stats['ok'].items():
            out.setdefault(host, {})
            for host_events in ansOut.host_events(host):
                if host_events['event'] != 'runner_on_ok':
                    continue
                action = host_events['event_data']['task_action']
                if action not in self.parsers.keys():
                    self.logger.warning(f'Unsupported NOS. There might be issues. Contact dev team')
                out[host] = host_events
                ansNetIntf = host_events.setdefault('event_data', {}).setdefault('res', {}).setdefault('ansible_facts',{})
                print(ansNetIntf.keys())
                print(out[host].keys())
        self.__getAnsErrors(ansOut)
        # TODO: add lldp, routing info
        return out, self.ansibleErrs

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

    def nametomac(self, inData, key):
        """Return all mac's associated to that host. Not in use for RAW plugin"""
        macs = inData.get('event_data', {}).get('res', {}).get('ansible_facts', {}).get('ansible_net_info', {}).get('macs', [])
        if macs and isinstance(macs, str):
            return [macs]
        if macs and isinstance(macs, list):
            return macs
        self.logger.debug(f'Warning. Mac info not available for switch {key}. Path links might be broken.')
        return []
