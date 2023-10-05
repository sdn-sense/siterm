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


class Switch:
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
            for host, _ in ansOut.stats.get(fkey, {}).items():
                for hostEvents in ansOut.host_events(host):
                    err = hostEvents.get('event_data', {}).get('res', {})
                    self.ansibleErrs.setdefault(host, {}).setdefault(fkey, [])
                    self.ansibleErrs[host][fkey].append(err)
                    self.logger.info('Ansible Error for %s: %s', host, err)

    def _writeInventoryInfo(self, out, subitem=''):
        """Write Ansible Inventory file (used only in a single apply)"""
        fname = f"{self.config.get('ansible', 'inventory' + subitem)}"
        with open(fname, 'w', encoding='utf-8') as fd:
            fd.write(yaml.dump(out))

    def _getInventoryInfo(self, hosts=None, subitem=''):
        """Get Inventory Info. If hosts specified, only return for specific hosts"""
        with open(self.config.get('ansible', 'inventory' + subitem), 'r', encoding='utf-8') as fd:
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

    def _executeAnsible(self, playbook, hosts=None, subitem=''):
        """Execute Ansible playbook"""
        return ansible_runner.run(private_data_dir=self.config.get('ansible', 'private_data_dir' + subitem),
                                  inventory=self._getInventoryInfo(hosts, subitem),
                                  playbook=playbook,
                                  rotate_artifacts=self.config.get('ansible', 'rotate_artifacts' + subitem),
                                  debug=self.config.getboolean('ansible', 'debug' + subitem),
                                  ignore_logging=self.config.getboolean('ansible', 'ignore_logging' + subitem))

    def getAnsNetworkOS(self, host, subitem=''):
        """Get Ansible network os from hosts file"""
        return self.getHostConfig(host, subitem).get('ansible_network_os', '')

    def getHostConfig(self, host, subitem=''):
        """Get Ansible Host Config"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir'+ subitem)}/{host}.yaml"
        if not os.path.isfile(fname):
            raise Exception(f'Ansible config file for {host} not available.')
        with open(fname, 'r', encoding='utf-8') as fd:
            out = yaml.safe_load(fd.read())
        return out

    def _writeHostConfig(self, host, out, subitem=''):
        """Write Ansible Host config file"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir' + subitem)}/{host}.yaml"
        if not subitem and not os.path.isfile(fname):
            raise Exception(f'Ansible config file for {host} not available.')
        with open(fname, 'w', encoding='utf-8') as fd:
            fd.write(yaml.dump(out))

    def _applyNewConfig(self, hosts=None, subitem=''):
        """Apply new config and run ansible playbook"""
        try:
            ansOut = self._executeAnsible('applyconfig.yaml', hosts, subitem)
        except ValueError as ex:
            raise ConfigException(f"Got Value Error. Ansible configuration exception {ex}") from ex
        self.__getAnsErrors(ansOut)
        return ansOut

    def _getFacts(self, hosts=None, subitem=''):
        """Get All Facts for all Ansible Hosts"""
        self.ansibleErrs = {}
        try:
            ansOut = self._executeAnsible('getfacts.yaml', hosts, subitem)
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
                ansNetIntf = host_events.setdefault('event_data', {}).setdefault('res', {}).setdefault('ansible_facts', {})
                print(ansNetIntf.keys())
                print(out[host].keys())
        self.__getAnsErrors(ansOut)
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
        swname = inData.get('event_data', {}).get('host', '')
        ports = self.getports(inData)
        tmpout = [vlan for vlan in ports if vlan.startswith('Vlan')]
        if self.config.has_option(swname, 'allvlans') and self.config.get(swname, 'allvlans'):
            return tmpout
        # If we reach here, means allvlans flag is false. It should include into model only SENSE Vlans.
        out = []
        if self.config.has_option(swname, 'all_vlan_range_list') and self.config.get(swname, 'all_vlan_range_list'):
            for item in tmpout:
                vlanid = self.getVlanKey(item)
                if isinstance(vlanid, int):
                    if vlanid in self.config.get(swname, 'all_vlan_range_list'):
                        out.append(item)
                else:
                    self.logger.warning(f'Issue with vlan name {item}. Not able to make integer')
                    out.append(item)
        else:
            # This point to an issue in SiteRM configuration. In this case we return all vlans
            self.logger.warning('There is an issue with all vlans range configuration. Contact DEV Team')
            return tmpout
        return out

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
