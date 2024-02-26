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
import re

from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.MainUtilities import getUTCnow, jsondumps, read_input_data


class CallValidator:
    """Validator class for Debug Actions"""

    def __init__(self, config):
        self.functions = {
            "prometheus-push": self.__validatePrompush,
            "arp-push": self.__validateArppush,
            "iperf-server": self.__validateIperfserver,
            "iperf-client": self.__validateIperf,
            "rapid-ping": self.__validateRapidping,
            "arp-table": self.__validateArp,
            "tcpdump": self.__validateTcpdump,
            "traceroute": self.__validateTraceRoute,
        }
        self.config = config

    def validate(self, inputDict):
        """Validate wrapper for debug action."""
        if "hostname" not in inputDict:
            raise BadRequestError("Hostname not specified in debug request.")
        if "type" in inputDict and inputDict["type"] not in self.functions:
            raise BadRequestError(
                f"Action {inputDict['type']} not supported. Supported actions: {self.functions.keys()}"
            )
        self.functions[inputDict["type"]](inputDict)

    @staticmethod
    def __validateTraceRoute(inputDict):
        """Validate traceroute debug request."""
        for key in ["ip"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")
        # One of these must be present:
        optional = False
        for key in ["from_interface", "from_ip"]:
            if key in inputDict:
                optional = True
        if not optional:
            raise BadRequestError("One of these keys must be present: from_interface, from_ip")

    @staticmethod
    def __validateArp(inputDict):
        """Validate aprdump debug request."""
        if "interface" not in inputDict:
            raise BadRequestError("Key interface not specified in debug request.")

    @staticmethod
    def __validateIperf(inputDict):
        """Validate iperfclient debug request."""
        for key in ["interface", "ip", "time", "port"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")
            # Do not allow time to be more than 5mins
            if int(inputDict["time"]) > 300:
                raise BadRequestError(
                    "Requested Runtime for debug request is more than 5mins."
                )

    @staticmethod
    def __validateIperfserver(inputDict):
        """Validate iperf server debug request."""
        for key in ["port", "ip", "time", "onetime"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")

    @staticmethod
    def __validateRapidping(inputDict):
        """Validate rapid ping debug request."""
        for key in ["ip", "time", "packetsize", "interface"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")
        # time not allow more than 5 minutes:
        if int(inputDict["time"]) > 300:
            raise BadRequestError(
                "Requested Runtime for rapidping request is more than 5mins."
            )
        # interval is optional - not allow lower than 0.2
        if "interval" in inputDict and float(inputDict["interval"]) < 0.2:
            raise BadRequestError(
                "Requested Interval is lower than 0.2. That would be considered DDOS and is not allowed."
            )
        if "packetsize" in inputDict and int(inputDict["packetsize"]) > 1500:
            raise BadRequestError(
                "Requested Packet Size is bigger than 1500. That would be considered DDOS and is not allowed."
            )

    @staticmethod
    def __validateTcpdump(inputDict):
        """Validate tcpdump debug request."""
        if "interface" not in inputDict:
            raise BadRequestError("Key interface not specified in debug request.")

    @staticmethod
    def __validateMetadata(inputDict):
        """Validate Metadata Parameters"""
        if "metadata" in inputDict:
            # Instance must be dictionary
            if not isinstance(inputDict["metadata"], dict):
                raise BadRequestError("Requested dictionary metadata is not dictionary")
            for key, val in inputDict["metadata"].items():
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                    raise BadRequestError(
                        f"Metadata Key {key} does not match prometheus label format"
                    )
                if not isinstance(val, str):
                    raise BadRequestError(
                        f"Metadata Key {key} value is not str. Only str supported"
                    )

    def __validatePrompush(self, inputDict):
        """Validate prometheus push debug request."""
        for key in ["hosttype", "gateway", "runtime", "resolution"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")
        if inputDict["hosttype"] not in ["host", "switch"]:
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
        totalRuntime = int(int(inputDict["runtime"]) - getUTCnow())
        if totalRuntime < 600 or totalRuntime > 86400:
            raise BadRequestError(
                f"Total Runtime must be within range of 600 < x < 86400 seconds since epoch. You requested {totalRuntime}"
            )
        # Check all metadata label parameters
        self.__validateMetadata(inputDict)
        # Check all filter parameters
        if "filter" in inputDict:
            if not isinstance(inputDict["filter"], dict):
                raise BadRequestError("Requested filter must be dictionary type")
            for filterKey, filterVals in inputDict["filter"].items():
                if filterKey not in ["mac", "snmp"]:
                    raise BadRequestError(
                        f"Requested filter {filterKey} not supported."
                    )
                if "operator" not in filterVals:
                    raise BadRequestError(
                        f"Requested filter: {filterVals}, does not have operator key"
                    )
                if filterVals["operator"] not in ["and", "or"]:
                    raise BadRequestError(
                        "Only 'and' or 'or' are supported filter operators"
                    )
                if "queries" not in filterVals:
                    raise BadRequestError("Requested filter does not have queries key")

    def __validateArppush(self, inputDict):
        """Validate arp push debug request."""
        for key in ["hosttype", "gateway", "runtime", "resolution"]:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")
        if inputDict["hosttype"] != "host":
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
        totalRuntime = int(inputDict["runtime"]) - getUTCnow()
        if totalRuntime < 600 or totalRuntime > 86400:
            raise BadRequestError(
                f"Total Runtime must be within range of 600 < x < 86400 seconds since epoch. You requested {totalRuntime}"
            )
        # Check all metadata label parameters
        self.__validateMetadata(inputDict)


class DebugCalls:
    """Site Frontend calls."""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()
        self.validator = CallValidator(self.config)

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

    def getdebug(self, environ, **kwargs):
        """Get Debug action for specific ID."""
        search = None
        if kwargs["debugvar"] != "ALL":
            search = [["id", kwargs["debugvar"]]]
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get(
            "debugrequests", orderby=["insertdate", "DESC"], search=search, limit=1000
        )

    def getalldebugids(self, environ, **kwargs):
        """Get All Debug IDs."""
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get(
            "debugrequestsids", orderby=["updatedate", "DESC"], limit=1000
        )

    def getalldebughostname(self, environ, **kwargs):
        """Get all Debug Requests for hostname"""
        search = [["hostname", kwargs["hostname"]], ["state", kwargs["hostname"]]]
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get(
            "debugrequests", orderby=["updatedate", "DESC"], search=search, limit=1000
        )

    def submitdebug(self, environ, **kwargs):
        """Submit new debug action request."""
        inputDict = read_input_data(environ)
        jsondump = jsondumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError(
                    "Unsupported symbol in input request. Contact Support"
                )
        self.validator.validate(inputDict)
        out = {
            "hostname": inputDict["hostname"],
            "state": "new",
            "requestdict": jsondump,
            "output": "",
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
        }
        insOut = self.dbI.insert("debugrequests", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": insOut[0], "ID": insOut[2]}

    def updatedebug(self, environ, **kwargs):
        """Update debug action information."""
        inputDict = read_input_data(environ)
        out = {
            "id": kwargs["debugvar"],
            "state": inputDict["state"],
            "output": inputDict["output"],
            "updatedate": getUTCnow(),
        }
        updOut = self.dbI.update("debugrequests", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}

    def deletedebug(self, environ, **kwargs):
        """Delete debug action information."""
        updOut = self.dbI.delete("debugrequests", [["id", kwargs["debugvar"]]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}
