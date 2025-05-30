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
from SiteRMLibs.ipaddr import ipVersion


class CallValidator:
    """Validator class for Debug Actions"""

    def __init__(self, config):
        self.functions = {
            "iperf-server": self.__validateIperfserver,
            "iperf-client": self.__validateIperf,
            "fdt-client": self.__validateFdtClient,
            "fdt-server": self.__validateFdtServer,
            "rapid-ping": self.__validateRapidping,
            "rapid-pingnet": self.__validateRapidpingnet,
            "arp-table": self.__validateArp,
            "tcpdump": self.__validateTcpdump,
            "traceroute": self.__validateTraceRoute,
            "traceroutenet": self.__validateTraceRouteNet,
        }
        self.defparams = {
            "iperf-server": {"onetime": True},
            "iperf-client": {"onetime": True},
            "fdt-client": {},
            "fdt-server": {},
            "rapid-ping": {},
            "rapid-pingnet": {"onetime": True},
            "arp-table": {"onetime": True},
            "tcpdump": {"onetime": True},
            "traceroute": {"onetime": True},
            "traceroutenet": {"onetime": True},
        }
        self.config = config

    def _addDefaults(self, inputDict):
        """Add default params (not controlled by outside)"""
        for key, val in self.defparams[inputDict["type"]].items():
            if key not in inputDict:
                inputDict[key] = val
        # If runtime not added, we add current timestamp + 10minutes
        if "runtime" not in inputDict:
            inputDict["runtime"] = getUTCnow() + 600
        return inputDict

    @staticmethod
    def __validateKeys(inputDict, keys):
        """Validate keys required for debug action"""
        for key in keys:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")

    def validate(self, inputDict):
        """Validate wrapper for debug action."""
        inputDict = self._addDefaults(inputDict)
        if "type" in inputDict and inputDict["type"] not in self.functions:
            raise BadRequestError(
                f"Action {inputDict['type']} not supported. Supported actions: {self.functions.keys()}"
            )
        self.functions[inputDict["type"]](inputDict)
        self.validateRuntime(inputDict)
        return inputDict

    def __validateTraceRouteNet(self, inputDict):
        """Validate traceroute debug request for network device"""
        self.__validateKeys(inputDict, ["ip"])

    def __validateTraceRoute(self, inputDict):
        """Validate traceroute debug request."""
        self.__validateKeys(inputDict, ["ip"])
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )
        # One of these must be present:
        optional = False
        for key in ["from_interface", "from_ip"]:
            if key in inputDict:
                optional = True
            if (
                key == "from_ip"
                and inputDict["from_ip"]
                and ipVersion(inputDict["from_ip"]) == -1
            ):
                raise BadRequestError(
                    f"Soure IP {inputDict['from_ip']} does not appear to be an IPv4 or IPv6"
                )
        if not optional:
            raise BadRequestError(
                "One of these keys must be present: from_interface, from_ip"
            )

    def __validateArp(self, inputDict):
        """Validate aprdump debug request."""
        self.__validateKeys(inputDict, ["interface"])

    def __validateIperf(self, inputDict):
        """Validate iperfclient debug request."""
        self.__validateKeys(inputDict, ["interface", "ip", "time", "port", "runtime"])
        # Do not allow time to be more than 5mins
        if int(inputDict["time"]) > 600:
            raise BadRequestError(
                "Requested Runtime for debug request is more than 10mins."
            )
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )

    def __validateIperfserver(self, inputDict):
        """Validate iperf server debug request."""
        self.__validateKeys(inputDict, ["port", "ip", "time", "runtime"])
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )

    def __validateFdtClient(self, inputDict):
        """Validate fdtclient debug request."""
        self.__validateKeys(inputDict, ["ip", "runtime"])
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )
        if int(inputDict["runtime"]) > 600:
            raise BadRequestError(
                "Requested Runtime for debug request is more than 10mins."
            )

    @staticmethod
    def __validateFdtServer(inputDict):
        """Validate fdt server debug request."""
        if int(inputDict["runtime"]) > 600:
            raise BadRequestError(
                "Requested Runtime for debug request is more than 10mins."
            )

    def __validateRapidpingnet(self, inputDict):
        """Validate rapid ping debug request for network device"""
        self.__validateKeys(inputDict, ["ip", "count", "timeout"])
        if int(inputDict["count"]) > 100:
            raise BadRequestError(
                "Count request is more than 100. Maximum allowed is 100"
            )
        if int(inputDict["timeout"]) > 30:
            raise BadRequestError(
                "Timeout request is more than 30 seconds. Maximum allowed is 30"
            )
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )

    def __validateRapidping(self, inputDict):
        """Validate rapid ping debug request."""
        self.__validateKeys(
            inputDict, ["ip", "time", "packetsize", "interface", "runtime"]
        )
        # time not allow more than 60 minutes:
        if int(inputDict["time"]) > 3600:
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
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )

    def __validateTcpdump(self, inputDict):
        """Validate tcpdump debug request."""
        self.__validateKeys(inputDict, ["interface"])

    def validateRuntime(self, inputDict):
        """Validate Runtime"""
        totalRuntime = int(int(inputDict["runtime"]) - getUTCnow())
        if totalRuntime < 600 or totalRuntime > 86400:
            raise BadRequestError(
                f"Total Runtime must be within range of 600 < x < 86400 seconds since epoch. You requested {totalRuntime}"
            )


class DebugCalls:
    """Site Frontend calls."""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()
        self.validator = CallValidator(self.config)
        self.debugdirs = {}
        for sitename in self.sites:
            if sitename != "MAIN":
                self.debugdirs.setdefault(sitename, "")
                self.debugdirs[sitename] = os.path.join(
                    self.config.get(sitename, "privatedir"), "DebugServices"
                )

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "getdebug": {"allowedMethods": ["GET"]},
            "getalldebughostname": {"allowedMethods": ["GET"]},
            "submitdebug": {"allowedMethods": ["PUT", "POST"]},
            "updatedebug": {"allowedMethods": ["PUT", "POST"]},
            "deletedebug": {"allowedMethods": ["DELETE"]},
            "adddebugservice": {"allowedMethods": ["PUT"]},
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
        self.routeMap.connect(
            "adddebugservice",
            "/json/frontend/adddebugservice",
            action="adddebugservice",
        )

    def adddebugservice(self, environ, **kwargs):
        """Adding new debug service to DB."""
        inputDict = read_input_data(environ)
        if "hostname" not in inputDict:
            raise BadRequestError("Key 'hostname' not specified in debug request.")
        host = self.dbI.get(
            "debugworkers", limit=1, search=[["hostname", inputDict["hostname"]]]
        )
        if not host:
            fname = os.path.join(
                self.debugdirs[kwargs["sitename"]],
                inputDict["hostname"],
                "hostinfo.json",
            )
            out = {
                "hostname": inputDict["hostname"],
                "insertdate": inputDict["insertTime"],
                "updatedate": inputDict["updateTime"],
                "hostinfo": fname,
            }
            self.dumpFileContentAsJson(fname, inputDict)
            self.dbI.insert("hosts", [out])
        else:
            # Update existing host information
            out = {
                "hostname": inputDict["hostname"],
                "updatedate": getUTCnow(),
                "hostinfo": os.path.join(
                    self.debugdirs[kwargs["sitename"]],
                    inputDict["hostname"],
                    "hostinfo.json",
                ),
            }
            self.dumpFileContentAsJson(out["hostinfo"], inputDict)
            updOut = self.dbI.update("debugworkers", [out])
            if not updOut[0]:
                raise BadRequestError(
                    f"Failed to update debug service for {inputDict['hostname']}"
                )
        self.responseHeaders(environ, **kwargs)
        return {"Status": "OK"}

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
        debugdir = os.path.join(
            self.config.get(kwargs["sitename"], "privatedir"), "DebugRequests"
        )
        # Get Request JSON
        requestfname = os.path.join(
            debugdir, out["hostname"], kwargs["debugvar"], "request.json"
        )
        out["requestdict"] = self.getFileContentAsJson(requestfname)
        # Get Output JSON
        outputfname = os.path.join(
            debugdir, out["hostname"], kwargs["debugvar"], "output.json"
        )
        out["output"] = self.getFileContentAsJson(outputfname)
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
        jsondump = jsondumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError(
                    "Unsupported symbol in input request. Contact Support"
                )
        inputDict = self.validator.validate(inputDict)
        # This submit a new request to the database, and then based on the ID/Hostanem
        # write request to the file.
        out = {
            "hostname": inputDict.get("hostname", "undefined"),
            "state": "new",
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
        }
        insOut = self.dbI.insert("debugrequests", [out])
        debugdir = os.path.join(
            self.config.get(kwargs["sitename"], "privatedir"), "DebugRequests"
        )
        requestfname = os.path.join(
            debugdir, inputDict["hostname"], str(insOut[2]), "request.json"
        )
        self.dumpFileContentAsJson(requestfname, inputDict)
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
        debugdir = os.path.join(
            self.config.get(kwargs["sitename"], "privatedir"), "DebugRequests"
        )
        requestfname = os.path.join(
            debugdir, dbentry["hostname"], kwargs["debugvar"], "output.json"
        )
        self.dumpFileContentAsJson(requestfname, inputDict.get("output", {}))

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
        if not self._getdebuginfo(environ, **kwargs):
            raise BadRequestError(
                f"Debug request with ID {kwargs['debugvar']} not found."
            )
        # ==================================
        updOut = self.dbI.delete("debugrequests", [["id", kwargs["debugvar"]]])
        self.responseHeaders(environ, **kwargs)
        return {"Status": updOut[0], "ID": updOut[2]}
