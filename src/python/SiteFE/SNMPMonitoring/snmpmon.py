#!/usr/bin/env python3
"""
    SNMPMonitoring gets all information from switches using SNMP and writes to DB.

Config example:
snmp_monitoring:
  session_vars:
    community: mgmt_hep
    hostname: 172.16.1.1
    version: 2
  mac_parser:
    key_mapping:
      oid: '1.3.6.1.2.1.17.4.3.1.1'
      mib: 'mib-2.17.4.3.1.1.'
    mac_mapping:
      oid: '1.3.6.1.2.1.17.7.1.2.2'
      mib: 'mib-2.17.7.1.2.2.1.2.'

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/11/21
"""
import sys
import simplejson as json
from easysnmp import Session
from easysnmp.exceptions import EasySNMPUnknownObjectIDError
from easysnmp.exceptions import EasySNMPTimeoutError
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.Backends.main import Switch
from DTNRMLibs.MainUtilities import getGitConfig
from DTNRMLibs.MainUtilities import getLoggingObject


class SNMPMonitoring():
    """SNMP Monitoring Class"""
    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='SNMPMonitoring')
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn('SNMPMonitoring', self), **{'sitename': self.sitename})
        self.switches = {}
        self.session = None
        self.err = []
        self.hostconf = {}

    def _start(self):
        self.switch.getinfo(False)
        self.switches = self.switch._getAllSwitches()

    def _getSNMPSession(self, host):
        self.session = None
        snmpEnabled = False
        if self.config.has_option(host, 'snmp_monitoring'):
            snmpEnabled = self.config.get(host, 'snmp_monitoring')
        if not snmpEnabled:
            self.logger.info(f'SNMP config for {host}:snmp_monitoring not enabled')
            return
        self.hostconf.setdefault(host, {})
        self.hostconf[host] = self.switch.plugin._getHostConfig(host)
        if 'snmp_monitoring' not in self.hostconf[host]:
            self.logger.info(f'Ansible host: {host} config does not have snmp_monitoring parameters')
            return
        if 'session_vars' not in self.hostconf[host]['snmp_monitoring']:
            self.logger.info(f'Ansible host: {host} config does not have session_vars parameters')
            return
        self.session = Session(**self.hostconf[host]['snmp_monitoring']['session_vars'])

    def _getSNMPVals(self, key):
        try:
            allvals = self.session.walk(key)
            return allvals
        except EasySNMPUnknownObjectIDError as ex:
            self.logger.warning(f'Got exception for key {key}: {ex}')
            self.err.append(ex)
        except EasySNMPTimeoutError as ex:
            self.logger.warning(f'Got SNMP Timeout Exception: {ex}')
            self.err.append(ex)
        return []

    def _writeToDB(self, host, output):
        """Write SNMP Data to DB"""
        out = {'id': 0, 'insertdate': getUTCnow(), 'updatedate': getUTCnow(),
               'hostname': host, 'output': json.dumps(output)}
        dbOut = self.dbI.get('snmpmon', limit=1, search=[['hostname', host]])
        if dbOut:
            out['id'] = dbOut[0]['id']
            self.dbI.update('snmpmon', [out])
        else:
            self.dbI.insert('snmpmon', [out])

    def _isVlanAllowed(self, host, vlan):
        try:
            if int(vlan) in self.config.get(host, 'vlan_range_list'):
                return True
        except:
            return False
        return False

    def _getMacAddrSession(self, host, macs):
        if not self.session:
            return
        macs.setdefault(host, {'mapping': {}, 'vlans': {}})
        if 'mac_parser' in self.hostconf[host]['snmp_monitoring']:
            if 'mac_mapping' in self.hostconf[host]['snmp_monitoring']['mac_parser']:
                oid = self.hostconf[host]['snmp_monitoring']['mac_parser']['mac_mapping']['oid']
                mib = self.hostconf[host]['snmp_monitoring']['mac_parser']['mac_mapping']['mib']
                allvals = self._getSNMPVals(oid)
                for item in allvals:
                    splVal = item.oid[len(mib):].split('.', 1)
                    macs[host]['mapping'][splVal[1]] = splVal[0]
            if 'key_mapping' in self.hostconf[host]['snmp_monitoring']['mac_parser']:
                oid = self.hostconf[host]['snmp_monitoring']['mac_parser']['key_mapping']['oid']
                mib = self.hostconf[host]['snmp_monitoring']['mac_parser']['key_mapping']['mib']
                allvals = self._getSNMPVals(oid)
                for item in allvals:
                    mac = ':'.join('{:02x}'.format(ord(x)) for x in item.value)
                    mapkey = item.oid[len(mib):]
                    if mapkey in macs[host]['mapping']:
                        vlankey = macs[host]['mapping'][mapkey]
                        if self._isVlanAllowed(host, vlankey):
                            macs[host]['vlans'].setdefault(vlankey, [])
                            macs[host]['vlans'][vlankey].append(mac)

    def startwork(self):
        """Scan all switches and get snmp data"""
        self.err = []
        self._start()
        macs = {}
        for host in self.switches:
            self._getSNMPSession(host)
            if not self.session:
                continue
            out = {}
            self._getMacAddrSession(host, macs)
            for key in self.config['MAIN']['snmp']['mibs']:
                allvals = self._getSNMPVals(key)
                for item in allvals:
                    indx = item.oid_index
                    out.setdefault(indx, {})
                    out[indx][key] = item.value.replace('\x00', '')
            out['macs'] = macs[host]
            self._writeToDB(host, out)
        if self.err:
            raise Exception(f'SNMP Monitoring Errors: {self.err}')

    def startRealTime(self, host, mibs=None):
        """This is used to get a real time stats for SENSE RTMON via actions"""
        self.err = []
        self._start()
        macs = {}
        if host not in self.switches:
            return {}
        self._getSNMPSession(self.switches[host])
        if not self.session:
            return {}
        if not mibs:
            mibs = self.config['MAIN']['snmp']['mibs']
        out = {}
        self._getMacAddrSession(self.switches[host], macs)
        for key in mibs:
            allvals = self._getSNMPVals(key)
            for item in allvals:
                indx = item.oid_index
                out.setdefault(indx, {})
                out[indx][key] = item.value.replace('\x00', '')
        out['macs'] = macs[host]
        if self.err:
            self.logger.warning(f'SNMP Monitoring Errors: {self.err}')
        return out


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args:
        snmpmon = SNMPMonitoring(config, args[1])
        snmpmon.startwork()
    else:
        for sitename in config.get('general', 'sites'):
            snmpmon = SNMPMonitoring(config, sitename)
            snmpmon.startwork()


if __name__ == '__main__':
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    print('1st argument has to be sitename which is configured in this frontend')
    print(sys.argv)
    getLoggingObject(logType='StreamLogger', service='SNMPMonitoring')
    execute(args=sys.argv)
