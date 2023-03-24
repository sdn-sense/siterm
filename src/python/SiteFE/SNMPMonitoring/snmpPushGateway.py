#!/usr/bin/env python3
"""
    SNMPMonitoring gets all information from switches using SNMP and pushes to gateway.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import isValFloat
from SiteFE.SNMPMonitoring.snmpmon import SNMPMonitoring
from prometheus_client import CollectorRegistry, push_to_gateway
from prometheus_client import Info, Gauge


class PromPush():
    """SNMP PushGateway Class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="PromPush")
        self.logger.info("====== PromPush Start Work. Config: %s", self.backgConfig)
        self.SNMPMonClass = SNMPMonitoring(config, sitename)

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __pushToGateway(self, registry):
        """Push registry to remote gateway"""
        push_to_gateway(self.backgConfig['requestdict']['gateway'],
                        job=f"job-{self.backgConfig['id']}",
                        registry=registry)

    def startwork(self):
        """Start PushGateway Work"""
        hostname = self.backgConfig['requestdict']['hostname']
        mibs = ["ifDescr", "ifType", "ifAlias"]
        if 'mibs' in self.backgConfig['requestdict']:
            mibs += self.backgConfig['requestdict']['mibs']
            mibs = list(set(mibs))
        else:
            # If mibs not specified in config, we use defaults from config
            mibs = self.config['MAIN']['snmp']['mibs']
        registry = self.__cleanRegistry()
        snmpData = self.SNMPMonClass.startRealTime(hostname, mibs)
        snmpGauge = Gauge('interface_statistics', 'Interface Statistics',
                          ['ifDescr', 'ifType', 'ifAlias', 'hostname', 'Key'], registry=registry)
        macState = Info('mac_table', 'Mac Address Table',
                        labelnames=['numb', 'vlan', 'hostname'],
                        registry=registry)
        for key, val in snmpData:
            if key == 'macs':
                if 'vlans' in val:
                    for key1, val1, in val['vlans'].items():
                        for index, macaddr in enumerate(val1):
                            labels = {'numb': index, 'vlan': key1,
                                      'hostname': hostname}
                            macState.labels(**labels).info({'macaddress': macaddr})
                continue
            keys = {'ifDescr': val.get('ifDescr', ''),
                    'ifType': val.get('ifType', ''),
                    'ifAlias': val.get('ifAlias', ''),
                    'hostname': hostname}
            for key1 in mibs:
                if key1 in val and isValFloat(val[key1]):
                    keys['Key'] = key1
                    snmpGauge.labels(**keys).set(val[key1])
        self.__pushToGateway(registry)
