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
import random

from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.ipaddr import ipVersion
from SiteRMLibs.MainUtilities import getUTCnow


def validateAddDefaults(config, inputDict):
    """Add default params (not controlled by outside)"""
    if inputDict["type"] not in config["MAIN"]["debuggers"]:
        raise BadRequestError(f"Debug type {inputDict['type']} not supported. Supported types: {config['MAIN']['debuggers'].keys()}")
    for key, val in config["MAIN"]["debuggers"][inputDict["type"]].get("defaults", {}).items():
        if key not in inputDict:
            inputDict[key] = val
    # If runtime not added, we add random between defruntime and maxruntime
    if "runtime" not in inputDict:
        randtime = random.randint(
            config["MAIN"]["debuggers"][inputDict["type"]]["defruntime"] + 60,
            config["MAIN"]["debuggers"][inputDict["type"]]["maxruntime"],
        )
        inputDict["runtime"] = getUTCnow() + randtime
    # If hostname not added, we add undefined hostname. To be identified by backend.
    if "hostname" not in inputDict:
        inputDict["hostname"] = "undefined"
    return inputDict


def validateKeys(inputDict, keys):
    """Validate keys required for debug action"""
    for key in keys:
        if key not in inputDict:
            raise BadRequestError(f"Key {key} not specified in debug request.")


def validateIP(_config, inputDict):
    """Validate IP is IPv4/6"""
    if ipVersion(inputDict["ip"]) == -1:
        raise BadRequestError(f"IP {inputDict['ip']} does not appear to be an IPv4 or IPv6")


def validateStreams(config, inputDict):
    """Validate streams is within configuration"""
    maxStreams = config["MAIN"]["debuggers"][inputDict["type"]]["maxstreams"]
    minStreams = config["MAIN"]["debuggers"][inputDict["type"]]["minstreams"]
    if inputDict["streams"] > maxStreams:
        raise BadRequestError(f"Requested streams is higher than allowed by Site Configuration. Requests is {inputDict['streams']}. Max allowed: {maxStreams}")
    if inputDict["streams"] < minStreams:
        raise BadRequestError(f"Requested streams is low than allowed by Site Configuration. Requests is {inputDict['streams']}. Min allowed: {minStreams}")


def validateTraceRouteNet(config, inputDict):
    """Validate traceroute debug request for network device"""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip"])
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)


def validateTraceRoute(config, inputDict):
    """Validate traceroute debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip"])
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)
    # One of these must be present:
    optional = False
    for key in ["from_interface", "from_ip"]:
        if key in inputDict:
            optional = True
        if key == "from_ip" and inputDict["from_ip"] and ipVersion(inputDict["from_ip"]) == -1:
            raise BadRequestError(f"Soure IP {inputDict['from_ip']} does not appear to be an IPv4 or IPv6")
    if not optional:
        raise BadRequestError("One of these keys must be present: from_interface, from_ip")


def validateArp(config, inputDict):
    """Validate aprdump debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["interface"])
    validateRuntime(config, inputDict)


def validateIperfClient(config, inputDict):
    """Validate iperfclient debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip", "time", "port", "runtime", "streams"])
    validateIP(config, inputDict)
    validateStreams(config, inputDict)
    validateRuntime(config, inputDict)


def validateIperfServer(config, inputDict):
    """Validate iperf server debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["port", "time", "runtime"])
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)


def validateFdtClient(config, inputDict):
    """Validate fdtclient debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip", "runtime", "streams"])
    validateIP(config, inputDict)
    validateStreams(config, inputDict)
    validateRuntime(config, inputDict)


def validateFdtServer(config, inputDict):
    """Validate fdt server debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["runtime"])
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)


def validateRapidpingNet(config, inputDict):
    """Validate rapid ping debug request for network device"""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip", "count", "timeout"])
    maxcount = config["MAIN"]["debuggers"][inputDict["type"]]["maxcount"]
    if int(inputDict["count"]) > maxcount:
        raise BadRequestError(f"Count request is more than {maxcount}. Requested {inputDict['count']}")
    maxtimeout = config["MAIN"]["debuggers"][inputDict["type"]]["maxtimeout"]
    if int(inputDict["timeout"]) > maxtimeout:
        raise BadRequestError(f"Timeout request is more than {maxtimeout} seconds. Requested {inputDict['timeout']}")
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)


def validateRapidping(config, inputDict):
    """Validate rapid ping debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["ip", "time", "packetsize", "interface", "runtime"])
    # time reply wait <deadline> in seconds
    maxtimeout = config["MAIN"]["debuggers"][inputDict["type"]]["maxtimeout"]
    if int(inputDict["time"]) > maxtimeout:
        raise BadRequestError(f"Requested Runtime for rapidping request is more than {maxtimeout} sec. Requested: {inputDict['time']}")
    # interval is optional - not allow lower than config
    mininterval = config["MAIN"]["debuggers"][inputDict["type"]]["mininterval"]
    if "interval" in inputDict and float(inputDict["interval"]) < mininterval:
        raise BadRequestError(f"Requested Interval is lower than {mininterval}. That would be considered DDOS and is not allowed.")
    maxmtu = config["MAIN"]["debuggers"][inputDict["type"]]["maxmtu"]
    if "packetsize" in inputDict and int(inputDict["packetsize"]) > maxmtu:
        raise BadRequestError(f"Requested Packet Size is bigger than {maxmtu}. That would be considered DDOS and is not allowed.")
    validateIP(config, inputDict)
    validateRuntime(config, inputDict)


def validateTcpdump(config, inputDict):
    """Validate tcpdump debug request."""
    inputDict = validateAddDefaults(config, inputDict)
    validateKeys(inputDict, ["interface"])
    validateRuntime(config, inputDict)


def validateRuntime(config, inputDict):
    """Validate Runtime"""
    inputDict = validateAddDefaults(config, inputDict)
    totalRuntime = int(int(inputDict["runtime"]) - getUTCnow())
    defRuntime = config["MAIN"]["debuggers"][inputDict["type"]]["defruntime"]
    maxRuntime = config["MAIN"]["debuggers"][inputDict["type"]]["maxruntime"]
    if totalRuntime < defRuntime or totalRuntime > maxRuntime:
        raise BadRequestError(f"Total Runtime must be within range of {defRuntime} < x < {maxRuntime} seconds since epoch. You requested {totalRuntime}")


def validator(config, inputDict):
    """Validate debug request"""
    debug_type = inputDict["type"]

    if debug_type == "traceroute-net":
        validateTraceRouteNet(config, inputDict)
    elif debug_type == "traceroute":
        validateTraceRoute(config, inputDict)
    elif debug_type == "arp-table":
        validateArp(config, inputDict)
    elif debug_type == "iperf-client":
        validateIperfClient(config, inputDict)
    elif debug_type == "iperf-server":
        validateIperfServer(config, inputDict)
    elif debug_type == "fdt-client":
        validateFdtClient(config, inputDict)
    elif debug_type == "fdt-server":
        validateFdtServer(config, inputDict)
    elif debug_type == "rapid-pingnet":
        validateRapidpingNet(config, inputDict)
    elif debug_type == "rapid-ping":
        validateRapidping(config, inputDict)
    elif debug_type == "tcpdump":
        validateTcpdump(config, inputDict)
    else:
        raise BadRequestError(f"Debug type {debug_type} not supported. Supported types: {config['MAIN']['debuggers'].keys()}")
    return True
