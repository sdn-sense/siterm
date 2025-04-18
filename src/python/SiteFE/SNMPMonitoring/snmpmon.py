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
    mib: "mib-2.17.7.1.2.2.1.3."
    oid: "1.3.6.1.2.1.17.7.1.2.2.1.3"

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/11/21
"""
import sys
from easysnmp import Session
from easysnmp.exceptions import EasySNMPUnknownObjectIDError
from easysnmp.exceptions import EasySNMPTimeoutError
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import jsondumps
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.GitConfig import getGitConfig


class SNMPMonitoring():
    """SNMP Monitoring Class"""
    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='SNMPMonitoring')
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn('SNMPMonitoring', self), **{'sitename': self.sitename})
        self.diragent = contentDB()
        self.switches = {}
        self.session = None
        self.err = []
        self.hostconf = {}

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def _start(self):
        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()

    def _getSNMPSession(self, host):
        self.session = None
        self.hostconf.setdefault(host, {})
        self.hostconf[host] = self.switch.plugin.getHostConfig(host)
        if self.config.config['MAIN'].get(host, {}).get('external_snmp', ''):
            snmphost = self.config.config['MAIN'][host]['external_snmp']
            self.logger.info(f'SNMP Scan skipped for {host}. Remote endpoint defined: {snmphost}')
            return
        if 'snmp_monitoring' not in self.hostconf[host]:
            self.logger.info(f'Ansible host: {host} config does not have snmp_monitoring parameters')
            return
        if 'session_vars' not in self.hostconf[host]['snmp_monitoring']:
            self.logger.info(f'Ansible host: {host} config does not have session_vars parameters')
            return
        # easysnmp does not support ipv6 and will fail with ValueError (unable to unpack)
        # To avoid this, we will bypass ipv6 check if error is raised.
        try:
            self.session = Session(**self.hostconf[host]['snmp_monitoring']['session_vars'])
        except ValueError:
            conf = self.hostconf[host]['snmp_monitoring']['session_vars']
            hostname = conf.pop('hostname')
            self.session = Session(**conf)
            self.session.update_session(hostname=hostname)


    def _getSNMPVals(self, key, host=None):
        try:
            allvals = self.session.walk(key)
            return allvals
        except EasySNMPUnknownObjectIDError as ex:
            ex = f'[{host}]: Got SNMP UnknownObjectID Exception for key {key}: {ex}'
            self.logger.warning(ex)
            self.err.append(ex)
        except EasySNMPTimeoutError as ex:
            ex = f'[{host}]: Got SNMP Timeout Exception: {ex}'
            self.logger.warning(ex)
            self.err.append(ex)
        return []

    def _junosmac(self, host, macs):
        """Junos Mac Parser (custom as it requires to get multiple values)"""
        # Junos uses ansible to get mac addresses
        # mainly because SNMP not always returns vlan id associated with mac address
        # There might be some MIBs/oids which can be used to get this information
        # for now, we will use ansible to get mac addresses (as enabling more features
        # at sites - might be more complex)
        updatedate = self.switch.switches.get('output', {}).get(host, {}).get('dbinfo', {}).get('updatedate', 0)
        if (getUTCnow() - updatedate) > 600:
            self.logger.info(f'[{host}]: Forcing ansible to update device information')
            self.switch.deviceUpdate(self.sitename, host)
        self.switch.getinfo()
        mactable = self.switch.output.get('mactable', {}).get(host, {})
        macs.setdefault(host, {'vlans': {}})
        for vlanid, allmacs in mactable.items():
            if not self._isVlanAllowed(host, vlanid):
                continue
            macs[host]['vlans'].setdefault(vlanid, [])
            for mac in allmacs:
                macs[host]['vlans'][vlanid].append(mac)


    def _writeToDB(self, host, output):
        """Write SNMP Data to DB"""
        out = {'id': 0, 'insertdate': getUTCnow(), 'updatedate': getUTCnow(),
               'hostname': host, 'output': jsondumps(output)}
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
        if self.hostconf[host].get('ansible_network_os', 'undefined') == 'sense.junos.junos':
            self._junosmac(host, macs)
            return
        macs.setdefault(host, {'vlans': {}})
        if 'mac_parser' in self.hostconf[host]['snmp_monitoring']:
            oid = self.hostconf[host]['snmp_monitoring']['mac_parser']['oid']
            mib = self.hostconf[host]['snmp_monitoring']['mac_parser']['mib']
            allvals = self._getSNMPVals(oid, host)
            for item in allvals:
                splt = item.oid[(len(mib)):].split('.')
                vlan = splt.pop(0)
                mac = [format(int(x), '02x') for x in splt]
                if self._isVlanAllowed(host, vlan):
                    macs[host]['vlans'].setdefault(vlan, [])
                    macs[host]['vlans'][vlan].append(":".join(mac))

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
                allvals = self._getSNMPVals(key, host)
                for item in allvals:
                    indx = item.oid_index
                    out.setdefault(indx, {})
                    out[indx][key] = item.value.replace('\x00', '')
            out['macs'] = macs[host]
            self._writeToDB(host, out)
        if self.err:
            raise Exception(f'SNMP Monitoring Errors: {self.err}')


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args and len(args) > 1:
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
