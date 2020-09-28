#!/usr/bin/env python
"""
Frontend Calls to get Sitenames, databases configured in Frontend.

Copyright 2019 California Institute of Technology
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
@Copyright		: Copyright (C) 2019 California Institute of Technology
Date			: 2019/05/01
"""
import sys
import socket
import importlib
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.DBBackend import dbinterface


def getDBConn():
    """ Get datanase connection """
    dbConn = {}
    config = getConfig()
    for sitename in config.get('general', 'sites').split(','):
        if config.has_option(sitename, "database"):
            dbConn[sitename] = dbinterface(config.get(sitename, "database"))
    return dbConn


def getAllHosts(sitename, logger):
    """ Get all hosts from database """
    logger.info('Get all hosts for %s', sitename)
    dbObj = getDBConn()[sitename]
    jOut = {}
    for site in dbObj.get('hosts'):
        jOut[site['hostname']] = site
    return jOut


def getSwitches(config, sitename, nodes, logger):
    """ Get Switches plugin """
    switchPlugin = config.get(sitename, 'plugin')
    logger.info('Will load %s switch plugin' % switchPlugin)
    method = importlib.import_module("SiteFE.LookUpService.Plugins.%s" % switchPlugin.lower())
    switchInfo = method.getinfo(config, logger, nodes, sitename)
    return switchInfo


def reportServiceStatus(servicename, status, sitename, logger, hostname=""):
    """ Report service state to DB """
    try:
        if not hostname:
            hostname = socket.gethostname()
        dbOut = {'hostname': hostname,
                 'servicestate': status,
                 'servicename': servicename,
                 'updatedate': getUTCnow()}
        dbI = getDBConn()
        dbobj = getVal(dbI, **{'sitename': sitename})
        services = dbobj.get('servicestates', search=[['hostname', hostname], ['servicename', servicename]])
        if not services:
            dbobj.insert('servicestates', [dbOut])
        else:
            dbobj.update('servicestates', [dbOut])
    except Exception:
        excType, excValue = sys.exc_info()[:2]
        logger.critical("Error details in reportServiceStatus. ErrorType: %s, ErrMsg: %s",
                        str(excType.__name__), excValue)
