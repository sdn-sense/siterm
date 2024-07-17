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
from SiteRMLibs.ipaddr import ipVersion


class CallValidator:
    """Validator class for Debug Actions"""

    def __init__(self, config):
        self.functions = {
            "prometheus-push": self.__validatePrompush,
            "arp-push": self.__validateArppush,
            "iperf-server": self.__validateIperfserver,
            "iperf-client": self.__validateIperf,
            "rapid-ping": self.__validateRapidping,
            "rapid-pingnet": self.__validateRapidpingnet,
            "arp-table": self.__validateArp,
            "tcpdump": self.__validateTcpdump,
            "traceroute": self.__validateTraceRoute,
            "traceroutenet": self.__validateTraceRouteNet
        }
        self.defparams = {"prometheus-push": {},
                          "arp-push": {},
                          "iperf-server": {"onetime": True},
                          "iperf-client": {"onetime": True},
                          "rapid-ping": {},
                          "rapid-pingnet": {},
                          "arp-table": {"onetime": True},
                          "tcpdump": {"onetime": True},
                          "traceroute": {"onetime": True},
                          "traceroutenet": {}}
        self.config = config

    def _addDefaults(self, inputDict):
        """Add default params (not controlled by outside)"""
        for key, val in self.defparams[inputDict["type"]].items():
            if key not in inputDict:
                inputDict[key] = val
        return inputDict

    def __validateKeys(self, inputDict, keys):
        """Validate keys required for debug action"""
        for key in keys:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")

    def validate(self, inputDict):
        """Validate wrapper for debug action."""
        self.__validateKeys(inputDict, ["hostname"])
        if "type" in inputDict and inputDict["type"] not in self.functions:
            raise BadRequestError(f"Action {inputDict['type']} not supported. Supported actions: {self.functions.keys()}")
        self.functions[inputDict["type"]](inputDict)
        self.__validateRuntime(inputDict)
        return self._addDefaults(inputDict)

    def __validateTraceRouteNet(self, inputDict):
        """Validate traceroute debug request for network device"""
        self.__validateKeys(inputDict, ["ip"])

    def __validateTraceRoute(self, inputDict):
        """Validate traceroute debug request."""
        self.__validateKeys(inputDict, ["ip"])
        if ipVersion(inputDict['ip']) == -1:
            raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")
        # One of these must be present:
        optional = False
        for key in ["from_interface", "from_ip"]:
            if key in inputDict:
                optional = True
            if key == "from_ip":
                if ipVersion(inputDict['from_ip']) == -1:
                    raise BadRequestError(f"IP {inputDict['from_ip']} does not appear to be an IPv4 or IPv6")
        if not optional:
            raise BadRequestError("One of these keys must be present: from_interface, from_ip")


    def __validateArp(self, inputDict):
        """Validate aprdump debug request."""
        self.__validateKeys(inputDict, ["interface"])


    def __validateIperf(self, inputDict):
        """Validate iperfclient debug request."""
        self.__validateKeys(inputDict, ["interface", "ip", "time", "port", "runtime"])
        # Do not allow time to be more than 5mins
        if int(inputDict["time"]) > 300:
            raise BadRequestError("Requested Runtime for debug request is more than 5mins.")
        if ipVersion(inputDict['ip']) == -1:
            raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")

    def __validateIperfserver(self, inputDict):
        """Validate iperf server debug request."""
        self.__validateKeys(inputDict, ["port", "ip", "time", "runtime"])
        if ipVersion(inputDict['ip']) == -1:
            raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")

    def __validateRapidpingnet(self, inputDict):
        """Validate rapid ping debug request for network device"""
        self.__validateKeys(inputDict, ["ip", "count", "timeout"])
        if int(inputDict["count"]) > 100:
            raise BadRequestError("Count request is more than 100. Maximum allowed is 100")
        if int(inputDict["timeout"] > 30):
            raise BadRequestError("Timeout request is more than 30 seconds. Maximum allowed is 30")
        if ipVersion(inputDict['ip']) == -1:
            raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")

    def __validateRapidping(self, inputDict):
        """Validate rapid ping debug request."""
        self.__validateKeys(inputDict, ["ip", "time", "packetsize", "interface", "runtime"])
        # time not allow more than 60 minutes:
        if int(inputDict["time"]) > 3600:
            raise BadRequestError("Requested Runtime for rapidping request is more than 5mins.")
        # interval is optional - not allow lower than 0.2
        if "interval" in inputDict and float(inputDict["interval"]) < 0.2:
            raise BadRequestError("Requested Interval is lower than 0.2. That would be considered DDOS and is not allowed.")
        if "packetsize" in inputDict and int(inputDict["packetsize"]) > 1500:
            raise BadRequestError("Requested Packet Size is bigger than 1500. That would be considered DDOS and is not allowed.")
        if ipVersion(inputDict['ip']) == -1:
            raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")

    def __validateTcpdump(self, inputDict):
        """Validate tcpdump debug request."""
        self.__validateKeys(inputDict, ["interface"])

    @staticmethod
    def __validateMetadata(inputDict):
        """Validate Metadata Parameters"""
        if "metadata" in inputDict:
            # Instance must be dictionary
            if not isinstance(inputDict["metadata"], dict):
                raise BadRequestError("Requested dictionary metadata is not dictionary")
            for key, val in inputDict["metadata"].items():
                if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", key):
                    raise BadRequestError(f"Metadata Key {key} does not match prometheus label format")
                if not isinstance(val, str):
                    raise BadRequestError(f"Metadata Key {key} value is not str. Only str supported")

    def __validateRuntime(self, inputDict):
        """Validate Runtime"""
        totalRuntime = int(int(inputDict["runtime"]) - getUTCnow())
        if totalRuntime < 600 or totalRuntime > 86400:
            raise BadRequestError(
                f"Total Runtime must be within range of 600 < x < 86400 seconds since epoch. You requested {totalRuntime}"
            )

    def __validatePrompush(self, inputDict):
        """Validate prometheus push debug request."""
        self.__validateKeys(inputDict, ["hosttype", "gateway", "runtime", "resolution"])
        if inputDict["hosttype"] not in ["host", "switch"]:
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
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
        self.__validateKeys(inputDict, ["hosttype", "gateway", "runtime", "resolution"])
        if inputDict["hosttype"] not in ["host", "switch"]:
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
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
        search = [["hostname", kwargs["hostname"]], ["state", kwargs["state"]]]
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
                raise BadRequestError("Unsupported symbol in input request. Contact Support")
        inputDict = self.validator.validate(inputDict)
        out = {"hostname": inputDict["hostname"],
               "state": "new",
               "requestdict": jsondumps(inputDict),
               "output": "",
               "insertdate": getUTCnow(),
               "updatedate": getUTCnow()
               }
        insOut = self.dbI.insert("debugrequests", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": insOut[0], "ID": insOut[2]}

    def updatedebug(self, environ, **kwargs):
        """Update debug action information."""
        inputDict = read_input_data(environ)
        out = {"id": kwargs["debugvar"],
               "state": inputDict["state"],
               "output": inputDict["output"],
               "updatedate": getUTCnow()
               }
        updOut = self.dbI.update("debugrequests", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}

    def deletedebug(self, environ, **kwargs):
        """Delete debug action information."""
        updOut = self.dbI.delete("debugrequests", [["id", kwargs["debugvar"]]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}
