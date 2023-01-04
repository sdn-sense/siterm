#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Debug API Calls

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
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.MainUtilities import read_input_data


class DebugCalls():
    """Site Frontend calls."""
    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'getdebug': {'allowedMethods': ['GET']},
                     'getalldebughostname': {'allowedMethods': ['GET']},
                     'submitdebug': {'allowedMethods': ['PUT', 'POST']},
                     'updatedebug': {'allowedMethods': ['PUT', 'POST']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("getdebug", "/json/frontend/getdebug/:debugvar", action="getdebug")
        self.routeMap.connect("getalldebughostname", "/json/frontend/getalldebughostname/:debugvar", action="getalldebughostname")
        self.routeMap.connect("submitdebug", "/json/frontend/submitdebug/:debugvar", action="submitdebug")
        self.routeMap.connect("updatedebug", "/json/frontend/updatedebug/:debugvar", action="updatedebug")

    def getdebug(self, environ, **kwargs):
        """Get Debug action for specific ID."""
        search = None
        if kwargs['debugvar'] != 'ALL':
            search = [['id', kwargs['debugvar']]]
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequests', orderby=['insertdate', 'DESC'],
                              search=search, limit=1000)

    def getalldebugids(self, environ, **kwargs):
        """Get All Debug IDs."""
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequestsids', orderby=['updatedate', 'DESC'], limit=1000)

    def getalldebughostname(self, environ, **kwargs):
        """Get all Debug Requests for hostname"""
        search = [['hostname', kwargs['debugvar']], ['state', 'new']]
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequests', orderby=['updatedate', 'DESC'],
                              search=search, limit=1000)

    def submitdebug(self, environ, **kwargs):
        """Submit new debug action request."""
        inputDict = read_input_data(environ)
        jsondump = json.dumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError('Unsupported symbol in input request. Contact Support')
        out = {'hostname': inputDict['dtn'],
               'state': 'new',
               'requestdict': jsondump,
               'output': '',
               'insertdate': getUTCnow(),
               'updatedate': getUTCnow()}
        insOut = self.dbobj.insert('debugrequests', [out])
        self.responseHeaders(environ, **kwargs)
        return {'Status': insOut[0], 'ID': insOut[2]}

    def updatedebug(self, environ, **kwargs):
        """Update debug action information."""
        inputDict = read_input_data(environ)
        out = {'id': kwargs['debugvar'],
               'state': inputDict['state'],
               'output': inputDict['output'],
               'updatedate': getUTCnow()}
        updOut = self.dbobj.update('debugrequests', [out])
        self.responseHeaders(environ, **kwargs)
        return {'Status': updOut[0], 'ID': updOut[2]}
