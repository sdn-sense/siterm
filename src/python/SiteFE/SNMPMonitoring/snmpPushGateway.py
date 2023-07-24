#!/usr/bin/env python3
"""
    SNMPMonitoring gets all information from switches using SNMP and pushes to gateway.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import isValFloat
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from prometheus_client import CollectorRegistry, push_to_gateway
from prometheus_client import Info, Gauge


class PromPush():
    """SNMP PushGateway Class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        backgConfig['requestdict'] = evaldict(backgConfig['requestdict'])
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="PromPush")
        self.logger.info("====== PromPush Start Work. Config: %s", self.backgConfig)
        self.dbI = getVal(getDBConn('PrometheusPush', self), **{'sitename': self.sitename})
        self.promLabels = {'Key': '', 'ifDescr': '', 'ifType': '', 'ifAlias': '', 'hostname': ''}
        self.promLabels.update(self.__getMetadataParams())
        self.snmpLabels = {'numb': '', 'vlan': '', 'hostname': ''}
        self.snmpLabels.update(self.__getMetadataParams())

    def __getMetadataParams(self):
        """Get metadata parameters"""
        if 'metadata' in self.backgConfig['requestdict']:
            return self.backgConfig['requestdict']['metadata']
        return {}

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __pushToGateway(self, registry):
        """Push registry to remote gateway"""
        push_to_gateway(self.backgConfig['requestdict']['gateway'],
                        job=f"job-{self.backgConfig['id']}",
                        registry=registry,
                        grouping_key=self.__getMetadataParams())

    @staticmethod
    def __filterOutput(filterRules, keys):
        """
        Allows to filter output send to Prometheus based on Keys. Full input:
        {"filter": {'snmp': {'operator': "and|or", queries: {Key1: Val1, Key2: [Val2, Val3]}},
                    'mac': {'operator': "and|or", queries: {Key1: Val1, Key2: [Val2, Val3]}}
        }}
        And this function get's only:
        {'operator': "and|or", queries: {Key1: Val1, Key2: [Val2, Val3]}
        """
        if not filterRules:
            return True
        filterChecks = []
        for filterKey, filterVal in filterRules.get('queries', {}).items():
            if isinstance(filterVal, str):
                val = keys.get(filterKey, None) == filterVal
                filterChecks.append(val)
            elif isinstance(filterVal, list):
                val = keys.get(filterKey, None) in filterVal
                filterChecks.append(val)
        if filterRules['operator'] == "and" and all(filterChecks):
            return True
        if filterRules['operator'] == "or" and any(filterChecks):
            return True
        return False

    def startwork(self):
        """Start PushGateway Work"""
        hostname = self.backgConfig['requestdict']['hostname']
        mibs = self.config['MAIN']['snmp']['mibs']
        registry = self.__cleanRegistry()
        # Get info from DB
        snmpData = self.dbI.get('snmpmon', limit=1, search=[['hostname', hostname]])
        snmpGauge = Gauge('interface_statistics', 'Interface Statistics',
                          self.promLabels.keys(), registry=registry)
        macState = Info('mac_table', 'Mac Address Table',
                        labelnames=self.snmpLabels.keys(),
                        registry=registry)
        # Set Collector label for hostname
        self.snmpLabels['hostname'] = hostname
        self.promLabels['hostname'] = hostname
        for item in snmpData:
            out = evaldict(item.get('output', {}))
            for key, val in out.items():
                if key == 'macs':
                    for key1, val1, in val.get('vlans', {}).items():
                        for index, macaddr in enumerate(val1):
                            self.snmpLabels['numb'] = index
                            self.snmpLabels['vlan'] = key1
                            if self.__filterOutput(self.backgConfig['requestdict'].get('filter', {}).get('mac', {}), self.snmpLabels):
                                macState.labels(**self.snmpLabels).info({'macaddress': macaddr})
                    continue
                self.promLabels['ifDescr'] = val.get('ifDescr', '')
                self.promLabels['ifType'] = val.get('ifType', '')
                self.promLabels['ifAlias'] = val.get('ifAlias', '')
                for key1 in mibs:
                    if key1 in val and isValFloat(val[key1]):
                        self.promLabels['Key'] = key1
                        if self.__filterOutput(self.backgConfig['requestdict'].get('filter', {}).get('snmp', {}), self.promLabels):
                            snmpGauge.labels(**self.promLabels).set(val[key1])
        self.__pushToGateway(registry)
