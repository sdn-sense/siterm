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
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import isValFloat
from prometheus_client import generate_latest, CollectorRegistry
from prometheus_client import Enum, Info, CONTENT_TYPE_LATEST
from prometheus_client import Gauge

class PrometheusAPI():
    """Prometheus exporter class."""
    def __init__(self):
        self.dbI = getDBConn('Prometheus', self)

    @staticmethod
    def cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def getServiceStates(self, registry, **kwargs):
        """Get all Services states."""
        serviceState = Enum('service_state', 'Description of enum',
                            labelnames=['servicename', 'hostname'],
                            states=['OK', 'UNKNOWN', 'FAILED', 'KEYBOARDINTERRUPT', 'UNSET'],
                            registry=registry)
        infoState = Info('running_version', 'Running Code Version.',
                         labelnames=['servicename', 'hostname'],
                         registry=registry)
        services = self.dbI[kwargs['sitename']].get('servicestates')
        # {'servicestate': u'OK', 'hostname': u'4df8c7b989d1',
        #  'servicename': u'LookUpService', 'id': 1, 'updatedate': 1601047007,
        #  'version': '220727'}
        timenow = int(getUTCnow())
        for service in services:
            state = 'UNKNOWN'
            if int(timenow - service['updatedate']) < 120:
                # If we are not getting service state for 2 mins, leave state as unknown
                state = service['servicestate']
            serviceState.labels(servicename=service['servicename'], hostname=service.get('hostname', 'UNSET')).state(state)
            infoState.labels(servicename=service['servicename'], hostname=service.get('hostname', 'UNSET')).info({'version': service['version']})
        # Here get info from DB for switch snmp details
        snmpData = self.dbI[kwargs['sitename']].get('snmpmon')
        g = Gauge('interface_statistics', 'Interface Statistics', ['ifDescr', 'ifType', 'ifAlias', 'hostname', 'Key'], registry=registry)
        for item in snmpData:
            if int(timenow - service['updatedate']) < 120:
                continue
            out = json.loads(item['output'])
            for key, val in out.items():
                keys = {'ifDescr': val.get('ifDescr', ''), 'ifType': val.get('ifType', ''), 'ifAlias': val.get('ifAlias', ''), 'hostname': item['hostname']}
                for key1 in  ['ifMtu', 'ifAdminStatus', 'ifOperStatus', 'ifHighSpeed', 'ifHCInOctets', 'ifHCOutOctets', 'ifInDiscards', 'ifOutDiscards',
                              'ifInErrors', 'ifOutErrors', 'ifHCInUcastPkts', 'ifHCOutUcastPkts', 'ifHCInMulticastPkts', 'ifHCOutMulticastPkts',
                              'ifHCInBroadcastPkts', 'ifHCOutBroadcastPkts']:
                    if key1 in val and isValFloat(val[key1]):
                        keys['Key'] = key1
                        g.labels(**keys).set(val[key1])

    def metrics(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        registry = self.cleanRegistry()
        self.getServiceStates(registry, **kwargs)
        data = generate_latest(registry)
        kwargs['http_respond'].ret_200(CONTENT_TYPE_LATEST, kwargs['start_response'], None)
        return iter([data])
