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
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
from SiteRMLibs.CustomExceptions import (BadRequestError, NotFoundError,
                                         OverlapException)
from SiteRMLibs.MainUtilities import (getUTCnow, jsondumps, read_input_data)
from SiteFE.REST.Modules.Functions.Host import HostSubCalls


class HostCalls(HostSubCalls):
    """Host Info/Add/Update Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "addhosts": {"allowedMethods": ["PUT"]},
            "updatehost": {"allowedMethods": ["PUT"]},
            "deletehost": {"allowedMethods": ["POST"]},
            "servicestate": {"allowedMethods": ["PUT"]},
            "serviceaction": {"allowedMethods": ["GET", "POST", "DELETE"],
                              'urlParams': [{"key": "hostname", "default": "", "type": str},
                                            {"key": "servicename", "default": "", "type": str}]
                            }
            }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("addhost", "/json/frontend/addhost", action="addhost")
        self.routeMap.connect(
            "updatehost", "/json/frontend/updatehost", action="updatehost"
        )
        self.routeMap.connect(
            "deletehost", "/json/frontend/deletehost", action="deletehost"
        )
        self.routeMap.connect(
            "servicestate", "/json/frontend/servicestate", action="servicestate"
        )
        self.routeMap.connect(
            "serviceaction", "/json/frontend/serviceaction", action="serviceaction"
        )

    def addhost(self, environ, **kwargs):
        """Adding new host to DB.

        Must provide dictionary with:
              hostname -> hostname of new host
              ip       -> ip of new host
              lat      -> latitude, enought to provide approximately site location
              lon      -> longitude, enought to provide approximately site location
        Examples:
        GOOD: {"hostname": "siterm.ultralight.org",
               "ip": "1.2.3.4"}
        """
        inputDict = read_input_data(environ)
        host = self.dbI.get("hosts", limit=1, search=[["ip", inputDict["ip"]]])
        if not host:
            out = {
                "hostname": inputDict["hostname"],
                "ip": inputDict["ip"],
                "insertdate": inputDict["insertTime"],
                "updatedate": inputDict["updateTime"],
                "hostinfo": jsondumps(inputDict),
            }
            self.dbI.insert("hosts", [out])
        else:
            raise BadRequestError(
                "This host is already in db. Why to add several times?"
            )
        self.responseHeaders(environ, **kwargs)
        return {"Status": "ADDED"}

    def updatehost(self, environ, **kwargs):
        """Update Host in DB.

        Must provide dictionary with:
            ip       -> ip of new host
        Example:
            GOOD: {"ip": "1.2.3.4", "site": "T2_US_Caltech", "status": "benchhmark",
                   "hostype": "gridftp", "port": 11234}
        """
        inputDict = read_input_data(environ)
        # Validate that these entries are known...
        host = self.dbI.get("hosts", limit=1, search=[["ip", inputDict["ip"]]])
        if not host:
            raise NotFoundError(
                f"This IP {inputDict['ip']} is not registered at all. Call addhost"
            )
        out = {
            "id": host[0]["id"],
            "hostname": inputDict["hostname"],
            "ip": inputDict["ip"],
            "updatedate": getUTCnow(),
            "hostinfo": jsondumps(inputDict),
        }
        self.dbI.update("hosts", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": "UPDATED"}

    def deletehost(self, environ, **kwargs):
        """Delete Host from DB."""
        inputDict = read_input_data(environ)
        # Validate that these entries are known...
        host = self.dbI.get("hosts", limit=1, search=[["ip", inputDict["ip"]]])
        if not host:
            raise NotFoundError(f"This IP {inputDict['ip']} is not registered at all.")
        # If it is in activeDeltas (means something is provisioned) - we should not delete until
        # resources are freed up.
        active = self.getActiveDeltas(environ, **kwargs)
        stillactive = []
        for key, vals in active.get("output", {}).get("vsw", {}).items():
            if inputDict["hostname"] in vals:
                stillactive.append(key)
        if stillactive:
            raise OverlapException(
                f"Unable to delete host. The following resources are active: {stillactive}"
            )
        # Delete from hosts
        self.dbI.delete("hosts", [["id", host[0]["id"]]])
        # Delete from service states
        self.dbI.delete("servicestates", [["hostname", host[0]["hostname"]]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": "DELETED"}

    def servicestate(self, environ, **kwargs):
        """Set Service State in DB."""
        inputDict = read_input_data(environ)
        if not self._host_supportedService(inputDict.get("servicename", "")):
            raise NotFoundError(
                f"This Service {inputDict['servicename']} is not supported by Frontend"
            )
        self._host_reportServiceStatus(
            **{
                "servicename": inputDict["servicename"],
                "servicestate": inputDict["servicestate"],
                "sitename": kwargs["sitename"],
                "hostname": inputDict["hostname"],
                "version": inputDict["version"],
                "runtime": inputDict["runtime"],
            }
        )
        self.responseHeaders(environ, **kwargs)
        return {"Status": "REPORTED"}

    def serviceaction(self, environ, **kwargs):
        """Set Service Action in DB."""
        # ======================================================
        # GET
        if environ["REQUEST_METHOD"].upper() == "GET":
            return self.__serviceaction_get(environ, **kwargs)
        # ======================================================
        # POST
        if environ["REQUEST_METHOD"].upper() == "POST":
            return self.__serviceaction_post(environ, **kwargs)
        # ======================================================
        # DELETE
        if environ['REQUEST_METHOD'].upper() == 'DELETE':
            return self.__serviceaction_delete(environ, **kwargs)
        raise BadRequestError("Request not in GET/POST/DELETE METHOD.")

    def __serviceaction_post(self, environ, **kwargs):
        """Set Service Action in DB for POST method."""
        inputDict = read_input_data(environ)
        if not self._host_supportedService(inputDict.get("servicename", "")):
            raise NotFoundError(
                f"This Service {inputDict['servicename']} is not supported by Frontend"
            )
        self._host_recordServiceAction(**inputDict)
        self.responseHeaders(environ, **kwargs)
        return {"Status": "Recorded"}

    def __serviceaction_get(self, environ, **kwargs):
        """Get Service Action in DB for GET method."""
        search = []
        if kwargs['urlParams']['hostname']:
            search.append(['hostname', kwargs['urlParams']['hostname']])
        if kwargs['urlParams']['servicename']:
            search.append(['servicename', kwargs['urlParams']['servicename']])

        actions = self.dbI.get('serviceaction', search=[['uid', modelID]])
        self.responseHeaders(environ, **kwargs)
        return actions

    def __serviceaction_delete(self, environ, **kwargs):
        """Delete Service Action in DB for DELETE method."""
        inputDict = read_input_data(environ)
        if not self._host_supportedService(inputDict.get("servicename", "")):
            raise NotFoundError(
                f"This Service {inputDict['servicename']} is not supported by Frontend"
            )
        self._host_deleteServiceAction(**inputDict)
        self.responseHeaders(environ, **kwargs)
        return {"Status": "Deleted"}
