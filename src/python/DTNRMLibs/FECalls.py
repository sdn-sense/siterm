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

import importlib
from DTNRMLibs.CustomExceptions import FailedToParseError
from DTNRMLibs.MainUtilities import getDataFromSiteFE
from DTNRMLibs.MainUtilities import evaldict, getConfig
from DTNRMLibs.DBBackend import dbinterface


def getDBConn():
    dbConn = {}
    config = getConfig(["/etc/dtnrm-site-fe.conf"])
    for sitename in config.get('general', 'sites').split(','):
        if config.has_option(sitename, "database"):
            dbConn[sitename] = dbinterface(config.get(sitename, "database"))
    return dbConn


def getAllHosts(sitename, logger):
    dbObj = getDBConn()[sitename]
    jOut = {}
    for site in dbObj.get('hosts'):
        jOut[site['hostname']] = site
    return jOut

def getSwitches(config, sitename, nodes, logger):
    switchPlugin = config.get(sitename, 'plugin')
    logger.info('Will load %s switch plugin' % switchPlugin)
    method = importlib.import_module("SiteFE.LookUpService.Plugins.%s" % switchPlugin.lower())
    switchInfo = method.getinfo(config, logger, nodes, sitename)
    return switchInfo
