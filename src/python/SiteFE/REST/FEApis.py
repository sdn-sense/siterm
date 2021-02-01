#!/usr/bin/env python3
"""
Site FE call functions

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
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
from __future__ import print_function
from builtins import str
from builtins import object
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.FECalls import reportServiceStatus


class FrontendRM(object):
    """ Site Frontend calls"""
    def __init__(self):
        self.dbI = getDBConn('REST-Frontend')
        self.initialized = False
        self.config = getConfig()
        self.siteDB = contentDB()

    def getHosts(self, **kwargs):
        """ Return all available Hosts, where key is IP address """
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def getdata(self, **kwargs):
        """ Return all available Hosts data, where key is IP address """
        dbobj = getVal(self.dbI, **kwargs)
        return dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def addhost(self, inputDict, **kwargs):
        """Adding new host to DB.
           Must provide dictionary with:
                hostname -> hostname of new host
                ip       -> ip of new host
                lat      -> latitude, enought to provide approximately site location
                lon      -> longitude, enought to provide approximately site location
          Examples:
          GOOD: {"hostname": "dtn-rm.ultralight.org",
                 "ip": "1.2.3.4"} """
        dbobj = getVal(self.dbI, **kwargs)
        host = dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            out = {'hostname': inputDict['hostname'],
                   'ip': inputDict['ip'],
                   'insertdate': inputDict['insertTime'],
                   'updatedate': inputDict['updateTime'],
                   'hostinfo': str(inputDict)}
            dbobj.insert('hosts', [out])
        else:
            print('This host is already in db. Why to add several times?')
            raise BadRequestError('This host is already in db. Why to add several times?')
        return

    def updatehost(self, inputDict, **kwargs):
        """ Update Host in DB.
            Must provide dictionary with:
                ip       -> ip of new host
            Example:
                GOOD: {"ip": "1.2.3.4", "site": "T2_US_Caltech", "status": "benchhmark",
                       "hostype": "gridftp", "port": 11234}"""
        # Validate that these entries are known...
        dbobj = getVal(self.dbI, **kwargs)
        host = dbobj.get('hosts', limit=1, search=[['ip', inputDict['ip']]])
        if not host:
            raise NotFoundError('This IP %s is not registered at all. Call addhost' % inputDict['ip'])
        out = {'id': host[0]['id'],
               'hostname': inputDict['hostname'],
               'ip': inputDict['ip'],
               'updatedate': getUTCnow(),
               'hostinfo': str(inputDict)}
        dbobj.update('hosts', [out])
        return

    @staticmethod
    def servicestate(inputDict, **kwargs):
        """ Set Service State in DB """
        # Only 2 Services are supported to report via URL
        # DTNRM-Agent and DTNRM-Ruler
        if inputDict['servicename'] not in ['Agent', 'Ruler']:
            raise NotFoundError('This Service %s is not supported by Frontend' % inputDict['servicename'])
        reportServiceStatus(inputDict['servicename'], inputDict['servicestate'],
                            kwargs['sitename'], None, inputDict['hostname'])
