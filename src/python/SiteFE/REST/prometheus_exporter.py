#! /usr/bin/env python
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
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getUTCnow
from prometheus_client import generate_latest, CollectorRegistry
from prometheus_client import Enum, CONTENT_TYPE_LATEST


class PrometheusAPI(object):
    """ Prometheus exporter class"""
    def __init__(self):
        self.dbI = getDBConn('Prometheus')

    @staticmethod
    def cleanRegistry():
        """ Get new/clean prometheus registry """
        registry = CollectorRegistry()
        return registry

    def getServiceStates(self, registry, **kwargs):
        """ Get all Services states """
        serviceState = Enum('service_state', 'Description of enum',
                            labelnames=['servicename'],
                            states=['OK', 'UNKNOWN', 'FAILED', 'KEYBOARDINTERRUPT'],
                            registry=registry)
        services = self.dbI[kwargs['sitename']].get('servicestates')
        # {'servicestate': u'OK', 'hostname': u'4df8c7b989d1',
        #  'servicename': u'LookUpService', 'id': 1, 'updatedate': 1601047007}
        timenow = int(getUTCnow())
        for service in services:
            state = 'UNKNOWN'
            if int(timenow - service['updatedate']) < 120:
                # If we are not getting service state for 2 mins, leave state as unknown
                state = service['servicestate']
            serviceState.labels(servicename=service['servicename']).state(state)

    def metrics(self, **kwargs):
        """ Return all available Hosts, where key is IP address """
        registry = self.cleanRegistry()
        self.getServiceStates(registry, **kwargs)
        data = generate_latest(registry)
        kwargs['http_respond'].ret_200(CONTENT_TYPE_LATEST, kwargs['start_response'], None)
        return iter([data])
