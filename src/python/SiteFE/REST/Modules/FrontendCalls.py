#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Frontend API Calls (config, db interface)

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
class FrontendCalls():
    """Frontend Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'feconfig': {'allowedMethods': ['GET']},
                     'getdata': {'allowedMethods': ['GET']},
                     'gethosts': {'allowedMethods': ['GET']},
                     'getswitchdata': {'allowedMethods': ['GET']},
                     'getactivedeltas': {'allowedMethods': ['GET']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("feconfig", "/json/frontend/configuration", action="feconfig")
        self.routeMap.connect("getdata", "/json/frontend/getdata", action="getdata")
        self.routeMap.connect("gethosts", "/json/frontend/gethosts", action="gethosts")
        self.routeMap.connect("getswitchdata", "/json/frontend/getswitchdata", action="getswitchdata")
        self.routeMap.connect("getactivedeltas", "/json/frontend/getactivedeltas", action="getactivedeltas")

    def __responseHeaders(self, environ, **kwargs):
        self.httpresp.ret_200('application/json', kwargs["start_response"], None)

    def feconfig(self, environ, **kwargs):
        """Returns Frontend configuration"""
        self.__responseHeaders(environ, **kwargs)
        return self.config['MAIN']

    def gethosts(self, environ, **kwargs):
        """Return all available Hosts, where key is IP address."""
        self.__responseHeaders(environ, **kwargs)
        return self.dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def getdata(self, environ, **kwargs):
        """Return all available Hosts data, where key is IP address."""
        self.__responseHeaders(environ, **kwargs)
        return self.dbobj.get('hosts', orderby=['updatedate', 'DESC'], limit=1000)

    def getswitchdata(self, environ, **kwargs):
        """Return all Switches information"""
        self.__responseHeaders(environ, **kwargs)
        return self.dbobj.get('switches', orderby=['updatedate', 'DESC'], limit=1000)

    def getactivedeltas(self, environ, **kwargs):
        """Return all Active Deltas"""
        self.__responseHeaders(environ, **kwargs)
        return self.dbobj.get('activeDeltas', orderby=['updatedate', 'DESC'], limit=1000)
