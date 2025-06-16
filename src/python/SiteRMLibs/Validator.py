#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Debug API Call Validator

Copyright 2023 ESnet
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
@Copyright              : Copyright (C) 2025 ESnet
Date                    : 2025/06/14
"""
from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.ipaddr import ipVersion


class Validator:
    """Validator class for Debug Actions"""

    def __init__(self, config):
        self.functions = {
            "iperf-server": self.__validateIperfserver,
            "iperf-client": self.__validateIperfClient,
            "fdt-client": self.__validateFdtClient,
            "fdt-server": self.__validateFdtServer,
            "rapid-ping": self.__validateRapidping,
            "rapid-pingnet": self.__validateRapidpingnet,
            "arp-table": self.__validateArp,
            "tcpdump": self.__validateTcpdump,
            "traceroute": self.__validateTraceRoute,
            "traceroutenet": self.__validateTraceRouteNet,
        }
        self.config = config

    def _addDefaults(self, inputDict):
        """Add default params (not controlled by outside)"""
        for key, val in self.config["MAIN"]["debuggers"][inputDict["type"]].get(
            "defaults", {}
        ):
            if key not in inputDict:
                inputDict[key] = val
        # If runtime not added, we add current timestamp + 10minutes
        if "runtime" not in inputDict:
            inputDict["runtime"] = (
                getUTCnow()
                + self.config["MAIN"]["debuggers"][inputDict["type"]]["defruntime"]
            )
        # If hostname not added, we add undefined hostname. To be identified by backend.
        if "hostname" not in inputDict:
            inputDict["hostname"] = "undefined"
        return inputDict

    @staticmethod
    def __validateKeys(inputDict, keys):
        """Validate keys required for debug action"""
        for key in keys:
            if key not in inputDict:
                raise BadRequestError(f"Key {key} not specified in debug request.")

    def __validateIP(self, inputDict):
        """Validate IP is IPv4/6"""
        if ipVersion(inputDict["ip"]) == -1:
            raise BadRequestError(
                f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6"
            )

    def __validateStreams(self, inputDict):
        """Validate streams is within configuration"""
        maxStreams = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxstreams"]
        minStreams = self.config["MAIN"]["debuggers"][inputDict["type"]]["minstreams"]
        if inputDict["streams"] > maxStreams:
            raise BadRequestError(
                f"Requested streams is higher than allowed by Site Configuration. Requests is {inputDict['streams']}. Max allowed: {maxStreams}"
            )
        if inputDict["streams"] < minStreams:
            raise BadRequestError(
                f"Requested streams is low than allowed by Site Configuration. Requests is {inputDict['streams']}. Min allowed: {minStreams}"
            )

    def validate(self, inputDict):
        """Validate wrapper for debug action."""
        inputDict = self._addDefaults(inputDict)
        if "type" in inputDict and inputDict["type"] not in self.functions:
            raise BadRequestError(
                f"Action {inputDict['type']} not supported. Supported actions: {self.functions.keys()}"
            )
        if inputDict["hostname"] == "undefined":
            if not inputDict.get("dynamicfrom", None):
                raise BadRequestError(
                    "Hostname is undefined,and dynamicfrom is not defined either. "
                    "Please provide either hostname or dynamicfrom."
                )
            return inputDict
        self.functions[inputDict["type"]](inputDict)
        self.validateRuntime(inputDict)
        return inputDict

    def __validateTraceRouteNet(self, inputDict):
        """Validate traceroute debug request for network device"""
        self.__validateKeys(inputDict, ["ip"])
        self.__validateIP(inputDict)

    def __validateTraceRoute(self, inputDict):
        """Validate traceroute debug request."""
        self.__validateKeys(inputDict, ["ip"])
        self.__validateIP(inputDict)
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

    def __validateIperfClient(self, inputDict):
        """Validate iperfclient debug request."""
        self.__validateKeys(inputDict, ["ip", "time", "port", "runtime", "streams"])
        self.__validateIP(inputDict)
        self.__validateStreams(inputDict)

    def __validateIperfserver(self, inputDict):
        """Validate iperf server debug request."""
        self.__validateKeys(inputDict, ["port", "time", "runtime"])
        self.__validateIP(inputDict)

    def __validateFdtClient(self, inputDict):
        """Validate fdtclient debug request."""
        self.__validateKeys(inputDict, ["ip", "runtime", "streams"])
        self.__validateIP(inputDict)
        self.__validateStreams(inputDict)

    def __validateFdtServer(self, inputDict):
        """Validate fdt server debug request."""
        self.__validateKeys(inputDict, ["runtime"])
        self.__validateIP(inputDict)

    def __validateRapidpingnet(self, inputDict):
        """Validate rapid ping debug request for network device"""
        self.__validateKeys(inputDict, ["ip", "count", "timeout"])
        maxcount = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxcount"]
        if int(inputDict["count"]) > maxcount:
            raise BadRequestError(
                f"Count request is more than {maxcount}. Requested {inputDict['count']}"
            )
        maxtimeout = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxtimeout"]
        if int(inputDict["timeout"]) > maxtimeout:
            raise BadRequestError(
                f"Timeout request is more than {maxtimeout} seconds. Reuqsted {inputDict['timeout']}"
            )
        self.__validateIP(inputDict)

    def __validateRapidping(self, inputDict):
        """Validate rapid ping debug request."""
        self.__validateKeys(
            inputDict, ["ip", "time", "packetsize", "interface", "runtime"]
        )
        # time reply wait <deadline> in seconds
        maxtimeout = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxtimeout"]
        if int(inputDict["time"]) > maxtimeout:
            raise BadRequestError(
                f"Requested Runtime for rapidping request is more than {maxtimeout} sec. Requested: {inputDict['time']}"
            )
        # interval is optional - not allow lower than config
        mininterval = self.config["MAIN"]["debuggers"][inputDict["type"]]["mininterval"]
        if "interval" in inputDict and float(inputDict["interval"]) < mininterval:
            raise BadRequestError(
                f"Requested Interval is lower than {mininterval}. That would be considered DDOS and is not allowed."
            )
        maxmtu = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxmtu"]
        if "packetsize" in inputDict and int(inputDict["packetsize"]) > maxmtu:
            raise BadRequestError(
                f"Requested Packet Size is bigger than {maxmtu}. That would be considered DDOS and is not allowed."
            )
        self.__validateIP(inputDict)

    def __validateTcpdump(self, inputDict):
        """Validate tcpdump debug request."""
        self.__validateKeys(inputDict, ["interface"])

    def validateRuntime(self, inputDict):
        """Validate Runtime"""
        totalRuntime = int(int(inputDict["runtime"]) - getUTCnow())
        defRuntime = self.config["MAIN"]["debuggers"][inputDict["type"]]["mininterval"]
        maxRuntime = self.config["MAIN"]["debuggers"][inputDict["type"]]["maxruntime"]
        if totalRuntime < defRuntime or totalRuntime > maxRuntime:
            raise BadRequestError(
                f"Total Runtime must be within range of {defRuntime} < x < {maxRuntime} seconds since epoch. You requested {totalRuntime}"
            )
