#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Prometheus API Output Calls.

Copyright 2023 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
import simplejson as json
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import isValFloat
from DTNRMLibs.MainUtilities import getAllHosts
from prometheus_client import generate_latest, CollectorRegistry
from prometheus_client import Enum, Info, CONTENT_TYPE_LATEST
from prometheus_client import Gauge


class PrometheusCalls():
    """Prometheus Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.timenow = int(getUTCnow())
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'prometheus': {'allowedMethods': ['GET']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("prometheus", "/json/frontend/metrics", action="prometheus")

    def __refreshTimeNow(self):
        """Refresh timenow"""
        self.timenow = int(getUTCnow())

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __getAgentData(self, registry, **kwargs):
        """Add Agent Data (Cert validity) to prometheus output"""
        agentCertValid = Gauge('agent_cert', 'Agent Certificate Validity', ['hostname', 'Key'], registry=registry)
        for host, hostDict in getAllHosts(self.dbobj).items():
            hostDict['hostinfo'] = evaldict(hostDict['hostinfo'])
            if int(self.timenow - hostDict['updatedate']) > 300:
                continue
            if 'CertInfo' in hostDict.get('hostinfo', {}).keys():
                for key in ['notAfter', 'notBefore']:
                    keys = {'hostname': host, 'Key': key}
                    agentCertValid.labels(**keys).set(hostDict['hostinfo']['CertInfo'].get(key, 0))

    def __getSNMPData(self, registry, **kwargs):
        """Add SNMP Data to prometheus output"""
        # Here get info from DB for switch snmp details
        snmpData = self.dbobj.get('snmpmon')
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

    def __getServiceStates(self, registry, **kwargs):
        """Get all Services states."""
        serviceState = Enum('service_state', 'Description of enum',
                            labelnames=['servicename', 'hostname'],
                            states=['OK', 'UNKNOWN', 'FAILED', 'KEYBOARDINTERRUPT', 'UNSET'],
                            registry=registry)
        runtimeInfo = Gauge('service_runtime', 'Service Runtime', ['servicename', 'hostname'], registry=registry)
        infoState = Info('running_version', 'Running Code Version.',
                         labelnames=['servicename', 'hostname'],
                         registry=registry)
        services = self.dbobj.get('servicestates')
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
        self.__getSNMPData(registry, **kwargs)
        self.__getAgentData(registry, **kwargs)

    def __metrics(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        self.__refreshTimeNow()
        registry = self.__cleanRegistry()
        self.__getServiceStates(registry, **kwargs)
        data = generate_latest(registry)
        self.httpresp.ret_200(CONTENT_TYPE_LATEST, kwargs['start_response'], None)
        return iter([data])

    def prometheus(self, environ, **kwargs):
        """Return prometheus stats."""
        return self.__metrics(**kwargs)
