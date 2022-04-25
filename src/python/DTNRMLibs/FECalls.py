#!/usr/bin/env python3
"""Frontend Calls to get Sitenames, databases configured in Frontend.

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
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2019 California Institute of Technology
Date                    : 2019/05/01
"""
from DTNRMLibs.MainUtilities import getDBConn

def getAllHosts(sitename, logger):
    # TODO: Remove this and have dbConn passed.
    """Get all hosts from database."""
    dbObj = getDBConn('getAllHosts')[sitename]
    jOut = {}
    for site in dbObj.get('hosts'):
        jOut[site['hostname']] = site
    return jOut
