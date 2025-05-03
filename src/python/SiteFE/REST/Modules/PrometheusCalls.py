#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Prometheus API Output Calls.

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
import os
from prometheus_client import CONTENT_TYPE_LATEST

class PrometheusCalls:
    """Prometheus Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {"prometheus": {"allowedMethods": ["GET"]}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect(
            "prometheus", "/json/frontend/metrics", action="prometheus"
        )

    def prometheus(self, environ, **kwargs):
        """Return prometheus stats."""
        snmpdir = os.path.join(self.config.get(environ['APP_SITENAME'], "privatedir"), "HostData")
        fname = os.path.join(snmpdir, 'snmpinfo.txt')
        if not os.path.exists(fname):
            self.httpresp.ret_404("text/plain", kwargs["start_response"], None)
            return iter([b"# Metrics are not available\n"])
        try:
            with open(fname, "rb") as fd:
                data = fd.read()
            self.httpresp.ret_200(CONTENT_TYPE_LATEST, kwargs["start_response"], None)
            return iter([data])
        except FileNotFoundError:
            self.httpresp.ret_404("text/plain", kwargs["start_response"], None)
            return iter([b"# Metrics are not available\n"])
