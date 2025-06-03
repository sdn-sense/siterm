#!/usr/bin/env python3
"""
Topology Calls

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
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/08/03
"""
import os
from SiteRMLibs.MainUtilities import getFileContentAsJson


class TopoCalls:
    """Frontend Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {"gettopology": {"allowedMethods": ["GET"]}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect(
            "gettopology", "/json/topo/gettopology", action="gettopology"
        )

    def gettopology(self, environ, **kwargs):
        """Return all Switches information"""
        self.responseHeaders(environ, **kwargs)
        topodir = os.path.join(
            self.config.get(kwargs["sitename"], "privatedir"), "Topology"
        )
        topofname = os.path.join(topodir, "topology.json")
        return getFileContentAsJson(topofname)
