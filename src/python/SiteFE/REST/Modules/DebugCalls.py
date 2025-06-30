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
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
import os

from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.MainUtilities import getUTCnow, jsondumps, read_input_data
from SiteRMLibs.MainUtilities import generateRandomUUID
from SiteRMLibs.Validator import Validator


class DebugCalls:
    """Site Frontend calls."""

    # pylint: disable=E1101
    # E1101 - no-member (it is not true, loaded by other class)
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()
        self.validator = Validator(self.config)

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "getdebug": {"allowedMethods": ["GET"]},
            "getalldebughostname": {"allowedMethods": ["GET"]},
            "submitdebug": {"allowedMethods": ["PUT", "POST"]},
            "updatedebug": {"allowedMethods": ["PUT", "POST"]},
            "deletedebug": {"allowedMethods": ["DELETE"]},
        }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect(
            "getdebug", "/json/frontend/getdebug/:debugvar", action="getdebug"
        )
        self.routeMap.connect(
            "getalldebughostname",
            "/json/frontend/getalldebughostname/:hostname/:state",
            action="getalldebughostname",
        )
        self.routeMap.connect(
            "submitdebug", "/json/frontend/submitdebug/:debugvar", action="submitdebug"
        )
        self.routeMap.connect(
            "updatedebug", "/json/frontend/updatedebug/:debugvar", action="updatedebug"
        )
        self.routeMap.connect(
            "deletedebug", "/json/frontend/deletedebug/:debugvar", action="deletedebug"
        )

    def _getdebuginfo(self, _environ, **kwargs):
        """Get Debug action information."""
        search = [["id", kwargs["debugvar"]]]
        out = self.dbI.get(
            "debugrequests", orderby=["insertdate", "DESC"], search=search, limit=1
        )
        if out is None:
            raise BadRequestError(
                f"Debug request with ID {kwargs['debugvar']} not found."
            )
        out = out[0]
        out["requestdict"] = self.siteDB.getFileContentAsJson(out["debuginfo"])
        out["output"] = self.siteDB.getFileContentAsJson(out["outputinfo"])
        return out

    def getdebug(self, environ, **kwargs):
        """Get Debug action for specific ID."""
        self.responseHeaders(environ, **kwargs)
        if kwargs["debugvar"] != "ALL":
            return self._getdebuginfo(environ, **kwargs)
        return self.dbI.get(
            "debugrequests", orderby=["insertdate", "DESC"], search=None, limit=50
        )

    def getalldebughostname(self, environ, **kwargs):
        """Get all Debug Requests for hostname"""
        search = [["hostname", kwargs["hostname"]], ["state", kwargs["state"]]]
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get(
            "debugrequests", orderby=["updatedate", "DESC"], search=search, limit=50
        )

    def submitdebug(self, environ, **kwargs):
        """Submit new debug action request."""
        inputDict = read_input_data(environ)
        # TODO: Move this check to backend.
        jsondump = jsondumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError(
                    "Unsupported symbol in input request. Contact Support"
                )
        inputDict = self.validator.validate(inputDict)
        debugdir = os.path.join(
            self.config.get(kwargs["sitename"], "privatedir"), "DebugRequests"
        )
        randomuuid = generateRandomUUID()
        requestfname = os.path.join(
            debugdir, inputDict["hostname"], randomuuid, "request.json"
        )
        outputfname = os.path.join(
            debugdir, inputDict["hostname"], randomuuid, "output.json"
        )
        self.siteDB.dumpFileContentAsJson(requestfname, inputDict)
        out = {
            "hostname": inputDict.get("hostname", "undefined"),
            "state": "new",
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
            "debuginfo": requestfname,
            "outputinfo": outputfname,
        }
        insOut = self.dbI.insert("debugrequests", [out])

        self.responseHeaders(environ, **kwargs)
        return {"Status": insOut[0], "ID": insOut[2]}

    def updatedebug(self, environ, **kwargs):
        """Update debug action information."""
        inputDict = read_input_data(environ)
        dbentry = self._getdebuginfo(environ, **kwargs)
        if not dbentry:
            raise BadRequestError(
                f"Debug request with ID {kwargs['debugvar']} not found."
            )
        # ==================================
        self.siteDB.dumpFileContentAsJson(
            dbentry["outputinfo"], inputDict.get("output", {})
        )

        # Update the state in database.
        out = {
            "id": kwargs["debugvar"],
            "state": inputDict["state"],
            "updatedate": getUTCnow(),
        }
        updOut = self.dbI.update("debugrequests", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}

    def deletedebug(self, environ, **kwargs):
        """Delete debug action information."""
        out = self._getdebuginfo(environ, **kwargs)
        # ==================================
        updOut = self.dbI.delete("debugrequests", [["id", kwargs["debugvar"]]])
        # Delete files if they exists
        if os.path.isfile(out["debuginfo"]):
            os.remove(out["debuginfo"])
        if os.path.isfile(out["outputinfo"]):
            os.remove(out["outputinfo"])
        # ==================================
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}
