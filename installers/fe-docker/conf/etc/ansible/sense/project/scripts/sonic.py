#!/usr/bin/env python3
"""
SENSE Azure Sonic Module, which is copied and called via Ansible from
SENSE Site-RM Resource Manager.

Main reasons for this script are the following:
    1. Azure Sonic does not have Ansible module
    2. Dell Sonic module depends on sonic-cli - and currently (140422) -
       it is broken due to python2 removal. See https://github.com/Azure/SONiC/issues/781
    3. It is very diff from normal switch cli, like:
          If vlan present on Sonic, adding it again will raise Exception (on Dell/Arista Switches, it is not)
          If vlan not cleaned (has member, ip, or any param) Sonic does not allow to remove vlan. First need to
          clean all members, params, ips and only then remove vlan.

With this script - as input, it get's information from Site-RM for which vlan and routing to configure/unconfigure
It checks with local configuration and applies the configs on Sonic with config command.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/14
"""
import os
import ast
import sys
import json
import subprocess
import shlex
import ipaddress

def normalizeIPAddress(ipInput):
    """Normalize IP Address"""
    tmpIP = ipInput.split('/')
    longIP = ipaddress.ip_address(tmpIP[0]).exploded
    if len(tmpIP) == 2:
        return "%s/%s" % (longIP, tmpIP[1])
    return longIP


def externalCommand(command):
    """Execute External Commands and return stdout and stderr."""
    command = shlex.split(command)
    proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.communicate()

def strtojson(intxt):
    """str to json function"""
    out = {}
    try:
        out = ast.literal_eval(intxt)
    except ValueError:
        out = json.loads(intxt)
    except SyntaxError as ex:
        raise Exception("SyntaxError: Failed to literal eval dict. Err:%s " % ex) from ex
    return out

def loadJson(infile):
    """Load json file and return dictionary"""
    out = {}
    if not os.path.isfile(infile):
        print('File does not exist %s. Exiting' % infile)
        sys.exit(2)
    with open(infile, 'r', encoding='utf-8') as fd:
        out = fd.read()
    return strtojson(out)

class SonicCmd():
    """Sonic CMD Executor API"""
    def __init__(self):
        self.config = {}
        self.needRefresh = True

    def generateSonicDict(self):
        """Generate all Vlan Info for comparison with SENSE FE Entries"""
        cmdout = externalCommand('show runningconfiguration all')
        out = strtojson(cmdout[0])
        for key, _ in out.get('VLAN', {}).items():
            self.config.setdefault(key, {})
        for key, _ in out.get('VLAN_INTERFACE', {}).items():
            # Key can be
            # Vlan4070|2001:48d0:3001:11f::1/64
            # Vlan50
            # Vlan50|132.249.2.46/29
            tmpKey = key.split('|')
            intD = self.config.setdefault(tmpKey[0], {})
            if len(tmpKey) == 2:
                intD.setdefault('ips', [])
                intD['ips'].append(normalizeIPAddress(tmpKey[1]))
        for key, vals in out.get('VLAN_MEMBER', {}).items():
            #'Vlan3841|PortChannel501': {'tagging_mode': 'tagged'}
            #'Vlan3842|Ethernet100': {'tagging_mode': 'untagged'},
            # SENSE Works only with tagged mode.
            if vals['tagging_mode'] == 'tagged':
                tmpKey = key.split('|')
                intD = self.config.setdefault(tmpKey[0], {})
                intD.setdefault('tagged_members', [])
                intD['tagged_members'].append(tmpKey[1])

    def __executeCommand(self, cmd):
        """Execute command and set needRefresh to True"""
        print(cmd)
        externalCommand(cmd)
        self.needRefresh = True

    def __refreshConfig(self):
        """Refresh config from Switch"""
        if self.needRefresh:
            self.config = {}
            self.generateSonicDict()
            self.needRefresh = False

    def _addVlan(self, **kwargs):
        """Add Vlan if not present"""
        self.__refreshConfig()
        if kwargs['vlan'] not in self.config:
            cmd = "sudo config vlan add %(vlanid)s" % kwargs
            self.__executeCommand(cmd)

    def _delVlan(self, **kwargs):
        """Del Vlan if present. Del All Members, IPs too (required)"""
        # First we need to clean all IPs and tagged members from VLAN
        self._delMember(**kwargs)
        self._delIP(**kwargs)
        self.__refreshConfig()
        if kwargs['vlan'] in self.config:
            cmd = "sudo config vlan del %(vlanid)s" % kwargs
            self.__executeCommand(cmd)

    def _addMember(self, **kwargs):
        """Add Member if not present"""
        self._addVlan(**kwargs)
        self.__refreshConfig()
        if kwargs['member'] not in self.config.get(kwargs['vlan'], {}).get('tagged_members', []):
            cmd = "sudo config vlan member add %(vlanid)s %(member)s" % kwargs
            self.__executeCommand(cmd)

    def _delMember(self, **kwargs):
        """Del Member if not present"""
        self.__refreshConfig()
        if 'member' in kwargs:
            cmd = "sudo config vlan member del %(vlanid)s %(member)s" % kwargs
            self.__executeCommand(cmd)
        else:
            for member in self.config.get(kwargs['vlan'], {}).get('tagged_members', []):
                kwargs['member'] = member
                self._delMember(**kwargs)

    def _addIP(self, **kwargs):
        """Add IP if not present"""
        self._addVlan(**kwargs)
        self.__refreshConfig()
        if kwargs['ip'] not in self.config.get(kwargs['vlan'], {}).get('ips', []):
            cmd = "sudo config interface ip add %(vlan)s %(ip)s" % kwargs
            self.__executeCommand(cmd)

    def _delIP(self, **kwargs):
        """Del IP if not present"""
        self.__refreshConfig()
        if 'ip' in kwargs:
            cmd = "sudo config interface ip remove %(vlan)s %(ip)s" % kwargs
            self.__executeCommand(cmd)
        else:
            for ip in self.config.get(kwargs['vlan'], {}).get('ips', []):
                kwargs['ip'] = ip
                self._delIP(**kwargs)

def applyConfig(sensevlans):
    """Loop via sense vlans and check with sonic vlans config"""
    #{'description': 'urn:ogf:network:service+63b10f36-2f66-4db2-9273-493c79b5da35:vt+l2-policy::Connection_1',
    # 'ip6_address': {'ip': 'fc00:0:0:0:0:0:0:38/64', 'state': 'present'}, 'name': 'Vlan 3333', 'state': 'present',
    # 'tagged_members': [{'port': 'Ethernet24', 'state': 'present'}]}
    sonicAPI = SonicCmd()
    for key, val in sensevlans.items():
        # Sonic key is without space
        tmpKey = key.split(' ')
        tmpD = {'vlan': "".join(tmpKey), 'vlanid': tmpKey[1]}
        # Vlan ADD/Remove
        if val['state'] == 'present':
            sonicAPI._addVlan(**tmpD)
        if val['state'] == 'absent':
            sonicAPI._delVlan(**tmpD)
            continue
        # IP ADD/Remove
        for ipkey in ['ip6_address', 'ip_address']:
            ipDict = val.get(ipkey, {})
            if not ipDict:
                continue
            tmpD['ip'] = normalizeIPAddress(ipDict['ip'])
            if ipDict['state'] == 'present':
                sonicAPI._addIP(**tmpD)
            if ipDict['state'] == 'absent':
                sonicAPI._delIP(**tmpD)
        # Tagged Members Add/Remove
        for tagged in val.get('tagged_members', []):
            tmpD['member'] = tagged['port']
            if tagged['state'] == 'present':
                sonicAPI._addMember(**tmpD)
            if tagged['state'] == 'absent':
                sonicAPI._delMember(**tmpD)

def execute(args):
    """Main execute"""
    if len(args) == 1 or len(args) > 2:
        print('Too many or not enough args provided. Args: %s' % args)
        print('Please run ./sonic.py <json_file_config_location>')
        sys.exit(1)
    sensevlans = loadJson(args[1])
    applyConfig(sensevlans)

if __name__ == "__main__":
    execute(args=sys.argv)
