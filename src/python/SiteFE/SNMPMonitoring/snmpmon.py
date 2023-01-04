#!/usr/bin/env python3
"""
    SNMPMonitoring gets all information from switches using SNMP and writes to DB.


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

    def startwork(self):
        """Scan all switches and get snmp data"""
        self.switch.getinfo(False)
        switches = self.switch._getAllSwitches()
        err = []
        for host in switches:
            snmpEnabled = False
            if self.config.has_option(host, 'snmp_monitoring'):
                snmpEnabled = self.config.get(host, 'snmp_monitoring')
            if not snmpEnabled:
                self.logger.info(f'SNMP config for {host}:snmp_monitoring not enabled')
                continue
            hostconf = self.switch.plugin._getHostConfig(host)
            if 'snmp_monitoring' not in hostconf:
                self.logger.info(f'Ansible host: {host} config does not have snmp_monitoring parameters')
                continue
            session = Session(**hostconf['snmp_monitoring'])
            out = {}
            for key in ['ifDescr', 'ifType', 'ifMtu', 'ifAdminStatus', 'ifOperStatus',
                        'ifHighSpeed', 'ifAlias', 'ifHCInOctets', 'ifHCOutOctets', 'ifInDiscards',
                        'ifOutDiscards', 'ifInErrors', 'ifOutErrors', 'ifHCInUcastPkts',
                        'ifHCOutUcastPkts', 'ifHCInMulticastPkts', 'ifHCOutMulticastPkts',
                        'ifHCInBroadcastPkts', 'ifHCOutBroadcastPkts']:
                try:
                    allvals = session.walk(key)
                except EasySNMPUnknownObjectIDError as ex:
                    self.logger.warning(f'Got exception for key {key}: {ex}')
                    err.append(ex)
                    continue
                except EasySNMPTimeoutError as ex:
                    self.logger.warning(f'Got SNMP Timeout Exception: {ex}')
                    err.append(ex)
                    continue
                for item in allvals:
                    indx = item.oid_index
                    out.setdefault(indx, {})
                    out[indx][key] = item.value.replace('\x00', '')
            self._writeToDB(host, out)
        if err:
            raise Exception(f'SNMP Monitoring Errors: {err}')


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
