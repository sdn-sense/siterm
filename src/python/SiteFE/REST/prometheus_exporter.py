#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Copyright 2020 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2020 California Institute of Technology
Date                    : 2020/09/25
"""
import json
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import isValFloat
from DTNRMLibs.MainUtilities import getAllHosts
from prometheus_client import generate_latest, CollectorRegistry
from prometheus_client import Enum, Info, CONTENT_TYPE_LATEST
from prometheus_client import Gauge


class PrometheusAPI():
    """Prometheus exporter class."""
    def __init__(self):
        self.dbI = getDBConn('Prometheus', self)
        self.timenow = int(getUTCnow())

    def _refreshTimeNow(self):
        """Refresh timenow"""
        self.timenow = int(getUTCnow())

    @staticmethod
    def cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def getAgentData(self, registry, **kwargs):
        """Add Agent Data (Cert validity) to prometheus output"""
        agentCertValid = Gauge('agent_cert', 'Agent Certificate Validity', ['hostname', 'Key'], registry=registry)
        for host, hostDict in getAllHosts(self.dbI[kwargs['sitename']]).items():
            hostDict['hostinfo'] = evaldict(hostDict['hostinfo'])
            if int(self.timenow - hostDict['updatedate']) > 300:
                continue
            if 'CertInfo' in hostDict.get('hostinfo', {}).keys():
                for key in ['notAfter', 'notBefore']:
                    keys = {'hostname': host, 'Key': key}
                    agentCertValid.labels(**keys).set(hostDict['hostinfo']['CertInfo'].get(key, 0))

    def getSNMPData(self, registry, **kwargs):
        """Add SNMP Data to prometheus output"""
        # Here get info from DB for switch snmp details
        snmpData = self.dbI[kwargs['sitename']].get('snmpmon')
        snmpGauge = Gauge('interface_statistics', 'Interface Statistics', ['ifDescr', 'ifType', 'ifAlias', 'hostname', 'Key'], registry=registry)
        for item in snmpData:
            if int(self.timenow - item['updatedate']) > 300:
                continue
            out = json.loads(item['output'])
            for _key, val in out.items():
                keys = {'ifDescr': val.get('ifDescr', ''), 'ifType': val.get('ifType', ''), 'ifAlias': val.get('ifAlias', ''), 'hostname': item['hostname']}
                for key1 in ['ifMtu', 'ifAdminStatus', 'ifOperStatus', 'ifHighSpeed', 'ifHCInOctets', 'ifHCOutOctets', 'ifInDiscards', 'ifOutDiscards',
                             'ifInErrors', 'ifOutErrors', 'ifHCInUcastPkts', 'ifHCOutUcastPkts', 'ifHCInMulticastPkts', 'ifHCOutMulticastPkts',
                             'ifHCInBroadcastPkts', 'ifHCOutBroadcastPkts']:
                    if key1 in val and isValFloat(val[key1]):
                        keys['Key'] = key1
                        snmpGauge.labels(**keys).set(val[key1])

    def getServiceStates(self, registry, **kwargs):
        """Get all Services states."""
        serviceState = Enum('service_state', 'Description of enum',
                            labelnames=['servicename', 'hostname'],
                            states=['OK', 'UNKNOWN', 'FAILED', 'KEYBOARDINTERRUPT', 'UNSET'],
                            registry=registry)
        runtimeInfo = Gauge('service_runtime', 'Service Runtime', ['servicename', 'hostname'], registry=registry)
        infoState = Info('running_version', 'Running Code Version.',
                         labelnames=['servicename', 'hostname'],
                         registry=registry)
        services = self.dbI[kwargs['sitename']].get('servicestates')
        # {'servicestate': u'OK', 'hostname': u'4df8c7b989d1',
        #  'servicename': u'LookUpService', 'id': 1, 'updatedate': 1601047007,
        #  'version': '220727'}
        for service in services:
            state = 'UNKNOWN'
            runtime = -1
            if int(self.timenow - service['updatedate']) < 300:
                # If we are not getting service state for 2 mins, leave state as unknown
                state = service['servicestate']
                runtime = service['runtime']
            labels = {'servicename': service['servicename'], 'hostname': service.get('hostname', 'UNSET')}
            serviceState.labels(**labels).state(state)
            infoState.labels(**labels).info({'version': service['version']})
            runtimeInfo.labels(**labels).set(runtime)
        self.getSNMPData(registry, **kwargs)
        self.getAgentData(registry, **kwargs)

    def metrics(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        self._refreshTimeNow()
        registry = self.cleanRegistry()
        self.getServiceStates(registry, **kwargs)
        data = generate_latest(registry)
        kwargs['http_respond'].ret_200(CONTENT_TYPE_LATEST, kwargs['start_response'], None)
        return iter([data])
