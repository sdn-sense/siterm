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
from SiteRMLibs.ipaddr import ipVersion
from SiteRMLibs.MainUtilities import getUTCnow


def validateAddDefaults(config, dbid, inputDict):
    """Add default params (not controlled by outside)"""
    if inputDict["type"] not in config["MAIN"]["debuggers"]:
        raise BadRequestError(f"Debug type {inputDict['type']} not supported. Supported types: {config['MAIN']['debuggers'].keys()}")
    for key, val in config["MAIN"]["debuggers"][inputDict["type"]].get("defaults", {}).items():
        if key not in inputDict:
            inputDict[key] = val
    # Runtime is not for the user to control, and we keep it for admins to set max time to be in the queue.
    inputDict["runtime"] = getUTCnow() + config["MAIN"]["debuggers"][inputDict["type"]]["maxruntime"]
    # If hostname not added, we add undefined hostname. To be identified by backend.
    if "hostname" not in inputDict:
        inputDict["hostname"] = "undefined"
    # In case it is fdt-server, iperf-server, ethr-server - we need to assign port if not specified
    if inputDict["type"] in ["fdt-server", "iperf-server", "ethr-server"]:
        # This will wrap it between minport and maxports range, based on id (which is databse entry)
        inputDict["port"] = config["MAIN"]["debuggers"][inputDict["type"]]["minport"] + (dbid % config["MAIN"]["debuggers"][inputDict["type"]]["maxports"])
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
    validateKeys(inputDict, ["ip"])
    validateIP(config, inputDict)


def validateTraceRoute(config, inputDict):
    """Validate traceroute debug request."""
    validateKeys(inputDict, ["ip"])
    validateIP(config, inputDict)
    # One of these must be present:
    optional = False
    for key in ["from_interface", "from_ip"]:
        if key in inputDict:
            optional = True
        if key == "from_ip" and inputDict["from_ip"] and ipVersion(inputDict["from_ip"]) == -1:
            raise BadRequestError(f"Soure IP {inputDict['from_ip']} does not appear to be an IPv4 or IPv6")
    if not optional:
        raise BadRequestError("One of these keys must be present: from_interface, from_ip")


def validateArp(_config, inputDict):
    """Validate aprdump debug request."""
    validateKeys(inputDict, ["interface"])


def validateTransferClient(config, inputDict):
    """Validate transfer client debug request, e.g. FDT, Iperf, Ethr"""
    validateKeys(inputDict, ["ip", "time", "port", "runtime", "streams"])
    validateIP(config, inputDict)
    validateStreams(config, inputDict)


def validateTransferServer(_config, inputDict):
    """Validate transfer server debug request, e.g. FDT, Iperf, Ethr"""
    validateKeys(inputDict, ["time", "runtime"])


def validateRapidpingNet(config, inputDict):
    """Validate rapid ping debug request for network device"""
    validateKeys(inputDict, ["ip", "count", "timeout"])
    maxcount = config["MAIN"]["debuggers"][inputDict["type"]]["maxcount"]
    if int(inputDict["count"]) > maxcount:
        raise BadRequestError(f"Count request is more than {maxcount}. Requested {inputDict['count']}")
    maxtimeout = config["MAIN"]["debuggers"][inputDict["type"]]["maxtimeout"]
    if int(inputDict["timeout"]) > maxtimeout:
        raise BadRequestError(f"Timeout request is more than {maxtimeout} seconds. Requested {inputDict['timeout']}")
    validateIP(config, inputDict)


def validateRapidping(config, inputDict):
    """Validate rapid ping debug request."""
    validateKeys(inputDict, ["ip", "time", "packetsize", "runtime"])
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


def validateTcpdump(_config, inputDict):
    """Validate tcpdump debug request."""
    validateKeys(inputDict, ["interface"])


def validator(config, dbid, inputDict):
    """Validate debug request"""
    debugType = inputDict.get("type", "")
    if not debugType:
        raise BadRequestError("Debug type not specified in debug request.")
    inputDict = validateAddDefaults(config, dbid, inputDict)
    inputDict["action"] = debugType
    if debugType == "traceroute-net":
        validateTraceRouteNet(config, inputDict)
    elif debugType == "traceroute":
        validateTraceRoute(config, inputDict)
    elif debugType == "arp-table":
        validateArp(config, inputDict)
    elif debugType == "rapid-pingnet":
        validateRapidpingNet(config, inputDict)
    elif debugType == "rapid-ping":
        validateRapidping(config, inputDict)
    elif debugType == "tcpdump":
        validateTcpdump(config, inputDict)
    elif debugType in ["iperf-client", "ethr-client", "fdt-client"]:
        validateTransferClient(config, inputDict)
    elif debugType in ["iperf-server", "ethr-server", "fdt-server"]:
        validateTransferServer(config, inputDict)
    else:
        raise BadRequestError(f"Debug type {debugType} not supported. Supported types: {config['MAIN']['debuggers'].keys()}")
    return inputDict
