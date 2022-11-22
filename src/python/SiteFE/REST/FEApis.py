#!/usr/bin/env python3
"""Site FE call functions.

Copyright 2017 California Institute of Technology
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
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
"""
from __future__ import print_function
import json
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import reportServiceStatus
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.MainUtilities import getDBConn


class FrontendRM():
    """Site Frontend calls."""
    def __init__(self):
        self.initialized = False
        self.config = getConfig()
        self.logger = getLoggingObject(config=self.config,
                                       logFile='/var/log/dtnrm-site-fe/http-api/',
                                       service='http-api')
        self.siteDB = contentDB(config=self.config)
        self.dbI = getDBConn('REST-Frontend', self)

    def getHosts(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def getdata(self, **kwargs):
        """Return all available Hosts data, where key is IP address."""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def getswitchdata(self, **kwargs):
        """Return all Switches information"""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('switches', orderby=['updatedate', 'DESC'], limit=1000)

    def getactivedeltas(self, **kwargs):
        """Return all Active Deltas"""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('activeDeltas', orderby=['updatedate', 'DESC'], limit=1000)

    def addhost(self, inputDict, **kwargs):
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
        dbobj = getVal(self.dbI, **kwargs)
        host = dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            out = {'hostname': inputDict['hostname'],
                   'ip': inputDict['ip'],
                   'insertdate': inputDict['insertTime'],
                   'updatedate': inputDict['updateTime'],
                   'hostinfo': json.dumps(inputDict)}
            dbobj.insert('hosts', [out])
        else:
            print('This host is already in db. Why to add several times?')
            raise BadRequestError('This host is already in db. Why to add several times?')

    def updatehost(self, inputDict, **kwargs):
        """Update Host in DB.

        Must provide dictionary with:
            ip       -> ip of new host
        Example:
            GOOD: {"ip": "1.2.3.4", "site": "T2_US_Caltech", "status": "benchhmark",
                   "hostype": "gridftp", "port": 11234}
        """
        # Validate that these entries are known...
        dbobj = getVal(self.dbI, **kwargs)
        host = dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            raise NotFoundError(f"This IP {inputDict['ip']} is not registered at all. Call addhost")
        out = {'id': host[0]['id'],
               'hostname': inputDict['hostname'],
               'ip': inputDict['ip'],
               'updatedate': getUTCnow(),
               'hostinfo': json.dumps(inputDict)}
        dbobj.update('hosts', [out])

    def deletehost(self, inputDict, **kwargs):
        """Delete Host from DB."""
        # Validate that these entries are known...
        dbobj = getVal(self.dbI, **kwargs)
        host = dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            raise NotFoundError(f"This IP {inputDict['ip']} is not registered at all.")
        dbobj.delete('hosts', [['id', host[0]['id']]])


    def servicestate(self, inputDict, **kwargs):
        """Set Service State in DB."""
        # Only 3 Services are supported to report via URL
        # DTNRM-Agent | DTNRM-Ruler | DTNRM-Debugger
        if inputDict['servicename'] not in ['Agent', 'Ruler', 'Debugger', 'LookUpService', 'ProvisioningService', 'SNMPMonitoring']:
            raise NotFoundError(f"This Service {inputDict['servicename']} is not supported by Frontend")
        reportServiceStatus(**{'servicename': inputDict['servicename'], 'servicestate': inputDict['servicestate'],
                               'sitename': kwargs['sitename'], 'hostname': inputDict['hostname'],
                               'version': inputDict['version'], 'cls': self})

    def getdebug(self, **kwargs):
        """Get Debug action for specific ID."""
        dbobj = getVal(self.dbI, **kwargs)
        search = None
        if kwargs['mReg'][1] != 'ALL':
            search = [['id', kwargs['mReg'][1]]]
        return dbobj.get('debugrequests', orderby=['insertdate', 'DESC'], search=search, limit=1000)

    def getalldebugids(self, **kwargs):
        """Get All Debug IDs."""
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('debugrequestsids', orderby=['updatedate', 'DESC'], limit=1000)

    def getalldebughostname(self, **kwargs):
        """Get all Debug Requests for hostname"""
        dbobj = getVal(self.dbI, **kwargs)
        search = [['hostname', kwargs['mReg'][1]], ['state', 'new']]
        return dbobj.get('debugrequests', orderby=['updatedate', 'DESC'], search=search, limit=1000)

    def submitdebug(self, inputDict, **kwargs):
        """Submit new debug action request."""
        jsondump = json.dumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError('Unsupported symbol in input request. Contact Support')
        dbobj = getVal(self.dbI, **kwargs)
        out = {'hostname': inputDict['dtn'],
               'state': 'new',
               'requestdict': jsondump,
               'output': '',
               'insertdate': getUTCnow(),
               'updatedate': getUTCnow()}
        return dbobj.insert('debugrequests', [out])

    def updatedebug(self, inputDict, **kwargs):
        """Update debug action information."""
        dbobj = getVal(self.dbI, **kwargs)
        out = {'id': kwargs['mReg'][1],
               'state': inputDict['state'],
               'output': inputDict['output'],
               'updatedate': getUTCnow()}
        return dbobj.update('debugrequests', [out])
