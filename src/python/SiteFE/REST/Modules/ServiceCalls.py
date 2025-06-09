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
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
import os
from SiteRMLibs.CustomExceptions import NotFoundError
from SiteRMLibs.MainUtilities import getUTCnow, read_input_data, contentDB


class ServiceCalls(contentDB):
    """Host Info/Add/Update Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()
        self.servicedirs = {}
        for sitename in self.sites:
            if sitename != "MAIN":
                self.servicedirs.setdefault(sitename, "")
                self.servicedirs[sitename] = os.path.join(self.config.get(sitename, "privatedir"), "ServiceData")

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "addservice": {"allowedMethods": ["PUT"]},
            "updateservice": {"allowedMethods": ["PUT"]},
            "deleteservice": {"allowedMethods": ["POST"]},
            "getservice": {
                "allowedMethods": ["GET"],
                "urlParams": [
                    {"key": "hostname", "default": "", "type": str},
                    {"key": "servicename", "default": "", "type": str},
                ],
            },
        }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("addservice", "/json/frontend/addservice", action="addservice")
        self.routeMap.connect("updateservice", "/json/frontend/updateservice", action="addservice")
        self.routeMap.connect("deleteservice", "/json/frontend/deleteservice", action="deleteservice")
        self.routeMap.connect("getservice", "/json/frontend/getservice", action="getservice")

    def __generateSearch(self, inputDict):
        """Generate search query for service."""
        search = []
        if inputDict.get("hostname", None):
            search.append(["hostname", inputDict["hostname"]])
        if inputDict.get("servicename", None):
            search.append(["servicename", inputDict["servicename"]])
        return search

    def addservice(self, environ, **kwargs):
        """Adding new service to DB."""
        status = "Undefined"
        inputDict = read_input_data(environ)
        fname = os.path.join(self.servicedirs[kwargs["sitename"]], inputDict["hostname"], "serviceinfo.json")
        out = {
            "hostname": inputDict["hostname"],
            "servicename": inputDict["servicename"],
            "insertdate": inputDict.get("insertTime", getUTCnow()),
            "updatedate": inputDict.get("updateTime", getUTCnow()),
            "serviceinfo": fname,
        }
        host = self.dbI.get("services", limit=1, search=self.__generateSearch(inputDict))
        if not host:
            self.dumpFileContentAsJson(fname, inputDict)
            self.dbI.insert("services", [out])
            status = "ADDED"
        else:
            out["id"] = host[0]["id"]
            del out["insertdate"]
            out["updatedate"] = getUTCnow()
            self.dumpFileContentAsJson(fname, inputDict)
            self.dbI.update("services", [out])
            status = "UPDATED"
        self.responseHeaders(environ, **kwargs)
        return {"Status": status}

    def deleteservice(self, environ, **kwargs):
        """Delete Service from DB."""
        inputDict = read_input_data(environ)
        # Validate that these entries are known...
        host = self.dbI.get("services", limit=1, search=self.__generateSearch(inputDict))
        if not host:
            raise NotFoundError(f"This Input {inputDict} is not registered at all.")
        # Delete from services
        self.dbI.delete("services", [["id", host[0]["id"]]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": f"DELETED {host[0]['hostname']}"}

    def getservice(self, environ, **kwargs):
        """Get Service Action in DB for GET method."""
        search = []
        if kwargs["urlParams"].get("hostname", None):
            search.append(["hostname", kwargs["urlParams"]["hostname"]])
        if kwargs["urlParams"].get("servicename", None):
            search.append(["servicename", kwargs["urlParams"]["servicename"]])
        services = self.dbI.get("services", search=search)
        self.responseHeaders(environ, **kwargs)
        return services
