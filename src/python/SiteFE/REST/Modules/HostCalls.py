#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Host API Calls

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
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import reportServiceStatus
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.MainUtilities import read_input_data


class HostCalls():
    """Host Info/Add/Update Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'addhosts': {'allowedMethods': ['PUT']},
                     'updatehost': {'allowedMethods': ['PUT']},
                     'deletehost': {'allowedMethods': ['PUT']},
                     'servicestate': {'allowedMethods': ['PUT']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("addhost", "/json/frontend/addhost", action="addhost")
        self.routeMap.connect("updatehost", "/json/frontend/updatehost", action="updatehost")
        self.routeMap.connect("deletehost", "/json/frontend/deletehost", action="deletehost")
        self.routeMap.connect("servicestate", "/json/frontend/servicestate", action="servicestate")

    def addhost(self, environ, **kwargs):
        """Adding new host to DB.

        Must provide dictionary with:
              hostname -> hostname of new host
              ip       -> ip of new host
              lat      -> latitude, enought to provide approximately site location
              lon      -> longitude, enought to provide approximately site location
        Examples:
        GOOD: {"hostname": "dtn-rm.ultralight.org",
               "ip": "1.2.3.4"}
        """
        inputDict = read_input_data(environ)
        host = self.dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            out = {'hostname': inputDict['hostname'],
                   'ip': inputDict['ip'],
                   'insertdate': inputDict['insertTime'],
                   'updatedate': inputDict['updateTime'],
                   'hostinfo': json.dumps(inputDict)}
            self.dbobj.insert('hosts', [out])
        else:
            print('This host is already in db. Why to add several times?')
            raise BadRequestError('This host is already in db. Why to add several times?')
        self.responseHeaders(environ, **kwargs)
        return {"Status": 'ADDED'}

    def updatehost(self, environ, **kwargs):
        """Update Host in DB.

        Must provide dictionary with:
            ip       -> ip of new host
        Example:
            GOOD: {"ip": "1.2.3.4", "site": "T2_US_Caltech", "status": "benchhmark",
                   "hostype": "gridftp", "port": 11234}
        """
        inputDict = read_input_data(environ)
        # Validate that these entries are known...
        host = self.dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            raise NotFoundError(f"This IP {inputDict['ip']} is not registered at all. Call addhost")
        out = {'id': host[0]['id'],
               'hostname': inputDict['hostname'],
               'ip': inputDict['ip'],
               'updatedate': getUTCnow(),
               'hostinfo': json.dumps(inputDict)}
        self.dbobj.update('hosts', [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": 'UPDATED'}

    def deletehost(self, environ, **kwargs):
        """Delete Host from DB."""
        inputDict = read_input_data(environ)
        # Validate that these entries are known...
        host = self.dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            raise NotFoundError(f"This IP {inputDict['ip']} is not registered at all.")
        self.dbobj.delete('hosts', [['id', host[0]['id']]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": 'DELETED'}

    def servicestate(self, environ, **kwargs):
        """Set Service State in DB."""
        inputDict = read_input_data(environ)
        # Only 3 Services are supported to report via URL
        # DTNRM-Agent | DTNRM-Ruler | DTNRM-Debugger
        if inputDict['servicename'] not in ['Agent', 'Ruler', 'Debugger',
                                            'LookUpService', 'ProvisioningService',
                                            'SNMPMonitoring']:
            raise NotFoundError(f"This Service {inputDict['servicename']} is not supported by Frontend")
        reportServiceStatus(**{'servicename': inputDict['servicename'],
                               'servicestate': inputDict['servicestate'],
                               'sitename': kwargs['sitename'], 'hostname': inputDict['hostname'],
                               'version': inputDict['version'], 'runtime': inputDict['runtime'],
                               'cls': self})
        self.responseHeaders(environ, **kwargs)
        return {"Status": 'REPORTED'}
