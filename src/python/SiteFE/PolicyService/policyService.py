#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Policy Service which manipulates delta, connection states in DB.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""
import argparse
import copy
import os
import pprint
import sys
import tempfile
import time

import dictdiffer
from dateutil import parser
from rdflib import URIRef
from rdflib.plugins.parsers.notation3 import BadSyntax
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper  # TODO: Move to general
from SiteFE.PolicyService.deltachecks import ConflictChecker
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.BWService import BWService
from SiteRMLibs.CustomExceptions import (
    NotFoundError,
    OverlapException,
    ServiceNotReady,
    WrongIPAddress,
)
from SiteRMLibs.DefaultParams import DELTA_COMMIT_TIMEOUT
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    contentDB,
    createDirs,
    decodebase64,
    dictSearch,
    evaldict,
    getActiveDeltas,
    getAllHosts,
    getCurrentModel,
    getDBConn,
    getFileContentAsJson,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
    parseRDFFile,
    writeActiveDeltas,
)
from SiteRMLibs.timing import Timing


def getError(ex):
    """Get Error from Exception."""
    errors = {
        IOError: -1,
        KeyError: -2,
        AttributeError: -3,
        IndentationError: -4,
        ValueError: -5,
        BadSyntax: -6,
        OverlapException: -7,
        WrongIPAddress: -8,
    }
    out = {"errType": "Unrecognized", "errNo": -100, "errMsg": "Unset"}
    out["errType"] = str(ex.__class__)
    if ex.__class__ in errors:
        out["errNo"] = str(errors[ex.__class__])
    if hasattr(ex, "message"):
        out["errMsg"] = ex.message
    else:
        out["errMsg"] = str(ex)
    return out


class PolicyService(RDFHelper, Timing, BWService):
    """Policy Service to accept deltas."""

    def __init__(self, config, sitename, logger=None):
        self.sitename = sitename
        self.config = config
        if logger:
            self.logger = logger
        else:
            self.logger = getLoggingObject(config=self.config, service="PolicyService")
        self.siteDB = contentDB()
        self.dbI = getVal(getDBConn("PolicyService", self), **{"sitename": self.sitename})
        self.stateMachine = StateMachine(self.config)
        self.switch = Switch(config, sitename)
        self.hosts = {}
        workDir = os.path.join(self.config.get(sitename, "privatedir"), "PolicyService/")
        createDirs(workDir)
        self.getSavedPrefixes()
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []
        self.conflictChecker = ConflictChecker(config, sitename)
        self.currentActive = getActiveDeltas(self)
        self.newActive = {}
        self._refreshHosts()
        self.singleport = False
        self.startend = {}
        self._addedTriples = set()
        defbw = self.convertForBWService(self.config[self.sitename]["default_params"]["bw"])
        self.defaultBW = {
            "availableCapacity": defbw,
            "granularity": 100,
            "maximumCapacity": defbw,
            "priority": 0,
            "reservableCapacity": defbw,
            "type": "bestEffort",
            "unit": "mbps",
        }

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.stateMachine = StateMachine(self.config)
        self.switch = Switch(self.config, self.sitename)
        self.conflictChecker = ConflictChecker(self.config, self.sitename)
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []
        self.newActive = {}
        self._refreshHosts()
        self.singleport = False
        self.startend = {}
        defbw = self.convertForBWService(self.config[self.sitename]["default_params"]["bw"])
        self.defaultBW = {
            "availableCapacity": defbw,
            "granularity": 100,
            "maximumCapacity": defbw,
            "priority": 0,
            "reservableCapacity": defbw,
            "type": "bestEffort",
            "unit": "mbps",
        }

    def _refreshHosts(self):
        """Refresh all hosts information"""
        allHosts = getAllHosts(self.dbI)
        for host, hostDict in allHosts.items():
            self.hosts.setdefault(host, hostDict)
            for key in hostDict:
                if key == "hostinfo":
                    self.hosts[host]["hostinfo"] = getFileContentAsJson(hostDict["hostinfo"])
                    continue
                self.hosts[host][key] = hostDict[key]
        # Clean up hosts which are not in DB anymore
        for host in list(self.hosts.keys()):
            if host not in allHosts:
                del self.hosts[host]
        # Refresh switch info from DB
        self.switch.getinfo()

    def __clean(self):
        """Clean params of PolicyService"""
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []
        self.newActive = {}
        self._addedTriples = set()

    def __generateStartEnd(self):
        """Generate start and end time for existsDuring"""
        self.startend = {"default": {
                             "start": getUTCnow(**self.config[self.sitename]["default_params"]["starttime"]),
                             "end": getUTCnow(**self.config[self.sitename]["default_params"]["endtime"])}}

    def __setTime(self, existsDuring, uri):
        """Set time for existsDuring"""
        tmptimes = {}
        if uri in self.startend:
            tmptimes = self.startend[uri]
        else:
            tmptimes = self.startend["default"]
        existsDuring.setdefault("start", tmptimes["start"])
        existsDuring.setdefault("end", tmptimes["end"])
        existsDuring.setdefault("uri", f"{uri}:lifetime")
        # Once we are done, we add times to startend.
        self.startend[uri] = {"start": existsDuring["start"], "end": existsDuring["end"]}
        return existsDuring

    def __getDefBandwidth(self, suburi, currentBW):
        """Get default bandwidth"""
        for key, item in self.defaultBW.items():
            if not currentBW.get("type") or currentBW.get("type", "bestEffort") == "bestEffort":
                currentBW[key] = item
            else:
                currentBW.setdefault(key, item)
        currentBW.setdefault("uri", f"{suburi}:service+bw")
        return currentBW

    @staticmethod
    def _findsuburi(out, uri, hostname):
        """Find subURI inside rst based on connection id. TODO: Remove after #776 fix"""
        if not uri:
            return None
        uuid = uri.split(":")[-1].split("+")
        if len(uuid) == 2:
            uuid = uuid[1]
            for item in out.get("SubnetMapping", {}).get(hostname, {}).get("providesSubnet", {}).keys():
                if uuid in item:
                    return item
        return None

    def _addDefaultTimeBW(self, out, key):
        """Add default time,BW to vsw, singleport, kube output"""
        for uri in out.get(key, {}):
            # If _params exists, check and default timing
            if "_params" in out[key][uri]:
                out[key][uri]["_params"].setdefault("existsDuring", {})
                newTime = self.__setTime(out[key][uri]["_params"]["existsDuring"], uri)
                out[key][uri]["_params"]["existsDuring"] = newTime
            # Now we go deeper into switch, port and add params
            for key1 in out[key][uri]:
                if key1 == "_params":
                    continue
                for key2 in out[key][uri][key1]:
                    if key2 == "_params":
                        continue
                    # If params exists, check and default timing
                    out[key][uri][key1][key2].setdefault("_params", {})
                    if key == "rst":
                        suburi = self._findsuburi(
                            out,
                            out["rst"][uri][key1][key2].get("belongsToRoutingTable"),
                            key1,
                        )
                    else:
                        suburi = out[key][uri][key1][key2].get("uri")
                    # That should not happen, but just in case something breaks, leave resources active
                    if suburi:
                        out[key][uri][key1][key2]["_params"].setdefault("existsDuring", {})
                        newTime = self.__setTime(out[key][uri][key1][key2]["_params"]["existsDuring"], suburi)
                        out[key][uri][key1][key2]["_params"]["existsDuring"] = newTime
                        # This one checks for Bandwidth service and add defaults.
                        out[key][uri][key1][key2]["hasService"] = self.__getDefBandwidth(suburi, out[key][uri][key1][key2].get("hasService", {}))
        return out

    def _addDefaultTimeBWWrap(self, out):
        """Add default time and bw to all output"""
        for key in ["vsw", "singleport", "kube", "rst"]:
            out = self._addDefaultTimeBW(out, key)
        return out

    def intOut(self, inport, out):
        """
        SetDefault for out hostname, port, server, interface and use
        in output dictionary.
        """
        tmp = [f for f in str(inport)[len(self.prefixes["site"]) :].split(":") if f]
        for item in tmp:
            if not len(item.split("+")) > 1:
                out = out.setdefault(item, {})
        return out

    def hostsOnly(self, inport):
        """Scan only host isAliases"""
        tmp = [f for f in str(inport)[len(self.prefixes["site"]) :].split(":") if f]
        for item in tmp:
            if item in self.hosts:
                return True
        return False

    def getisAlias(self, gIn, bidPort):
        """Get isAlias from model"""
        out = self.queryGraph(
            gIn,
            bidPort,
            search=URIRef(f"{self.prefixes['nml']}isAlias"),
            allowMultiple=True,
        )
        if len(out) > 1:
            raise Exception(f"Multiple isAlias found for {bidPort}")
        if out:
            return str(out[0])
        return ""

    @staticmethod
    def queryGraph(graphIn, sub=None, pre=None, obj=None, search=None, allowMultiple=True):
        """Search inside the graph based on provided parameters."""
        foundItems = []
        for _sIn, pIn, oIn in graphIn.triples((sub, pre, obj)):
            if search:
                if search == pIn:
                    foundItems.append(oIn)
            else:
                foundItems.append(oIn)
        if not allowMultiple:
            if len(foundItems) > 1:
                raise Exception(f"Search returned multiple entries. Not Supported. Out: {foundItems}")
        return foundItems

    def getHasNetworkStatus(self, gIn, connectionID, connOut):
        """Identifying NetworkStatus of the service/vlan
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(
            gIn,
            connectionID,
            search=URIRef(f"{self.prefixes['mrs']}hasNetworkStatus"),
        )
        for statusuri in out:
            tout = self.queryGraph(gIn, statusuri, search=URIRef(f"{self.prefixes['mrs']}value"))
            if tout:
                scanVals = connOut.setdefault("_params", {})
                scanVals["networkstatus"] = str(tout[0])

    def getTimeScheduling(self, gIn, connectionID, connOut):
        """Identifying lifetime of the service.
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}existsDuring"))
        for timeline in out:
            times = connOut.setdefault("_params", {}).setdefault("existsDuring", {"uri": str(timeline)})
            for timev in ["end", "start"]:
                tout = self.queryGraph(gIn, timeline, search=URIRef(f"{self.prefixes['nml']}{timev}"))
                if not tout:
                    continue
                try:
                    temptime = int(parser.parse(str(tout[0])).timestamp())
                except Exception:
                    temptime = tout[0]
                try:
                    temptime = int(temptime)
                except ValueError:
                    continue
                if time.daylight:
                    temptime -= 3600
                times[timev] = temptime

    def _addCustomEntry(self, out, host, intf, tmpOut, key):
        """Add custom entry to output for kube and singleport - which usually has no switching service"""
        for mainkey, mainval in tmpOut.items():
            # If main key is equal our simple vlanport - ignore it;
            if mainkey.startswith(f'{self.prefixes["site"]}:{host}:{intf}:vlanport+'):
                continue
            # Check if that entry is already in output and alert if it is
            if mainkey in out.get(key, {}):
                self.logger.warning(f"Alias {mainkey} already exists in output. Will overwrite")
                self.logger.warning(f"Old: {out[key][mainkey]}")
                self.logger.warning(f"New: {mainval}")
            out.setdefault(key, {})[mainkey] = mainval

    def _parseHostInfo(self, gIn, out):
        """Parse Host information (kube based and config based isAlias definitions)."""
        for host, hostDict in self.hosts.items():
            kubeAliases = hostDict.get("hostinfo", {}).get("KubeInfo", {}).get("isAlias", {})
            configAliases = {}
            # Collect config-based aliases if they exist
            confSummary = hostDict.get("hostinfo", {}).get('Summary', {}).get('config', {})
            for intf in confSummary.get('agent', {}).get('interfaces', []):
                if confSummary.get(intf, {}).get('isAlias'):
                    configAliases[intf] = True

            allAliases = set(kubeAliases.keys()) | set(configAliases.keys())

            for intf in allAliases:
                self.logger.info(f"Parsing Kube requests for {host} and {intf}")

                connID = f"{self.prefixes['site']}:{host}:{intf}"
                tmpOut = self.parseL2Ports(gIn, URIRef(connID), {}, True)

                out.setdefault("kube", {})
                self._addCustomEntry(out, host, intf, tmpOut, "kube")
        return out

    def _parseSinglePort(self, gIn, out):
        """Parse SinglePort information"""
        # Parse single port which are not connected to any service;
        self.singleport = True
        for switchName in self.switch.getAllSwitches():
            for portName in self.switch.getAllAllowedPorts(switchName):
                connID = f"{self.prefixes['site']}:{switchName}:{self.switch.getSystemValidPortName(portName)}"
                if connID in self.scannedPorts:
                    continue
                try:
                    out.setdefault("singleport", {})
                    tmpOut = self.parseL2Ports(gIn, URIRef(connID), {}, True)
                    self._addCustomEntry(out, switchName, portName, tmpOut, "singleport")
                except NotFoundError:
                    continue
        self.singleport = False
        return out

    def parseModel(self, gIn):
        """Parse delta request and generateout"""
        self.__clean()
        out = {}
        for key in ["vsw", "rst"]:
            for switchName in self.config.get(self.sitename, "switch"):
                if switchName not in self.prefixes.get(key, {}):
                    self.logger.debug("Warning: %s parameter is not defined for %s.", key, switchName)
                    continue
                self.prefixes["main"] = self.prefixes[key][switchName]
                if key == "vsw":
                    self.logger.info("Parsing L2 information from model")
                    self.parsel2Request(gIn, out, switchName)
                elif key == "rst":
                    self.logger.info("Parsing L3 information from model")
                    self.parsel3Request(gIn, out, switchName)
        # Parse HostInfo, if isAlias defined as Kubernetes labels
        out = self._parseHostInfo(gIn, out)
        # Parse single ports which are not connected to any service
        out = self._parseSinglePort(gIn, out)
        # Generate new default start and end time
        self.__generateStartEnd()
        out = self._addDefaultTimeBWWrap(out)
        return out

    def getRoute(self, gIn, connID, returnout):
        """Get all routes from model for specific connID"""
        returnout.setdefault("hasRoute", {})
        routeout = returnout["hasRoute"].setdefault(str(connID), {})
        if str(connID) in self.scannedRoutes:
            return str(connID)
        for rtype in ["nextHop", "routeFrom", "routeTo"]:
            out = self.queryGraph(gIn, connID, search=URIRef(f"{self.prefixes['mrs']}{rtype}"))
            for item in out:
                mrstypes = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}type"))
                mrsvals = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}value"))
                if mrstypes and mrsvals and len(mrstypes) == len(mrsvals):
                    for index, mrtype in enumerate(mrstypes):
                        if mrtype and mrsvals[index]:
                            routeVals = routeout.setdefault(rtype, {}).setdefault(str(mrtype), {})
                            routeVals["type"] = str(mrtype)
                            routeVals["value"] = str(mrsvals[index])
                            routeVals["key"] = str(item)
                else:
                    self.logger.warning(f"Either val or type not defined. Key: {str(item)}, Type: {mrstypes}, Val: {mrsvals}")
        self.scannedRoutes.append(str(connID))
        return ""

    def getRouteTable(self, gIn, connID, returnout):
        """Get all route tables from model for specific connID and call getRoute"""
        out = self.queryGraph(gIn, connID, search=URIRef(f"{self.prefixes['mrs']}hasRoute"))
        tmpRet = []
        for item in out:
            tmpRet.append(self.getRoute(gIn, item, returnout))
        return tmpRet

    def parsel3Request(self, gIn, returnout, switchName):
        """Parse Layer 3 Delta Request."""
        self.logger.info(f"Lets try to get connection ID subject for {self.prefixes['main']}")
        for iptype in ["ipv4", "ipv6"]:
            uri = f"{self.prefixes['main']}-{iptype}"
            for rsttype in [
                {"key": "providesRoute", "call": self.getRoute},
                {"key": "providesRoutingTable", "call": self.getRouteTable},
            ]:
                out = self.queryGraph(
                    gIn,
                    URIRef(uri),
                    search=URIRef(f"{self.prefixes['mrs']}{rsttype['key']}"),
                )
                for connectionID in out:
                    if connectionID.startswith(f"{uri}:rt-table+vrf-") or connectionID.endswith("rt-table+main"):
                        # Ignoring default vrf and main table.
                        # This is not allowed to modify.
                        continue
                    self._recordMapping(
                        connectionID,
                        returnout,
                        "RoutingMapping",
                        rsttype["key"],
                        iptype,
                    )
                    returnout.setdefault("rst", {})
                    connOut = returnout["rst"].setdefault(str(connectionID), {}).setdefault(switchName, {}).setdefault(iptype, {})
                    self._hasService(gIn, connectionID, connOut)
                    self.getTimeScheduling(gIn, connectionID, connOut)
                    connOut[rsttype["key"]] = str(connectionID)
                    rettmp = rsttype["call"](gIn, connectionID, connOut)
                    if rettmp and rsttype["key"] == "providesRoutingTable":
                        # We need to know mapping back, which route belongs to which routing table
                        # There is no such mapping in json, so we manually add this from providesRoutingTable
                        for rttmp in rettmp:
                            returnout["rst"].setdefault(str(rttmp), {}).setdefault(switchName, {}).setdefault(iptype, {}).setdefault("belongsToRoutingTable", str(connectionID))

    def _parseNetworkAttributes(self, gIn, _bidPort, scanVals, attrkeys):
        """Query and parse all Network Attributes"""
        out = scanVals.setdefault("hasNetworkAttribute", {})
        for attrkey in attrkeys:
            attrout = out.setdefault(str(attrkey), {})
            mtype = self.queryGraph(
                gIn,
                attrkey,
                search=URIRef(f"{self.prefixes['mrs']}type"),
                allowMultiple=True,
            )
            if mtype:
                attrout["type"] = str("|".join(mtype))
            mvalue = self.queryGraph(
                gIn,
                attrkey,
                search=URIRef(f"{self.prefixes['mrs']}value"),
                allowMultiple=True,
            )
            if mvalue:
                attrout["value"] = str("|".join(mvalue))

    def _hasTags(self, gIn, bidPort, returnout, portScan=False, vswParams=False):
        """Query Graph and get Tags"""
        scanVals = returnout.setdefault("_params", {})
        keys = (
            {"tag": "mrs", "hasNetworkAttribute": "mrs"}
            if vswParams
            else {
                "tag": "mrs",
                "hasNetworkAttribute": "mrs",
                "belongsTo": "nml",
                "encoding": "nml",
            }
        )
        for tag, pref in keys.items():
            out = self.queryGraph(
                gIn,
                bidPort,
                search=URIRef(f"{self.prefixes[pref]}{tag}"),
                allowMultiple=True,
            )
            if out and tag != "hasNetworkAttribute":
                scanVals[tag] = str("|".join(out))
            elif out:
                self._parseNetworkAttributes(gIn, bidPort, scanVals, out)
        # In case it is portScan, which is == self.singleport
        # We check if tag is found. If no tag found - raise NotFoundError
        if vswParams:
            return
        if portScan and not scanVals.get("tag"):
            raise NotFoundError("PortScan is true and tag not found. Will not add interface")
        # Get network status if exists
        self.getHasNetworkStatus(gIn, bidPort, returnout)

    def _hasLabel(self, gIn, bidPort, returnout):
        """Query Graph and get Labels"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}hasLabel"))
        for item in out:
            scanVals = returnout.setdefault("hasLabel", {})
            out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['nml']}labeltype"))
            if out:
                scanVals["labeltype"] = "ethernet#vlan"
            out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['nml']}value"))
            if out:
                scanVals["value"] = int(out[0])
            scanVals["uri"] = str(item)

    def _hasService(self, gIn, bidPort, returnout):
        """Query Graph and get Services"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}hasService"))
        for item in out:
            scanVals = returnout.setdefault("hasService", {})
            scanVals["uri"] = str(item)
            self.getTimeScheduling(gIn, item, returnout)
            self._hasTags(gIn, item, scanVals)
            for key in [
                "availableCapacity",
                "granularity",
                "maximumCapacity",
                "priority",
                "reservableCapacity",
                "type",
                "unit",
            ]:
                out = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}{key}"))
                if out:
                    try:
                        scanVals[key] = int(out[0])
                    except ValueError:
                        scanVals[key] = str(out[0])

    def _hasNetwork(self, gIn, bidPort, returnout, vswParams=False):
        """Query Graph and get ip address, type and uri"""
        if not vswParams:
            self._hasTags(gIn, bidPort, returnout)
        # Get all hasNetworkAddress items
        out = self.queryGraph(gIn, bidPort, search=URIRef(f"{self.prefixes['mrs']}hasNetworkAddress"))
        for item in out:
            scanVals = returnout.setdefault("hasNetworkAddress", {})
            # Get item type
            out1 = self.queryGraph(
                gIn,
                item,
                search=URIRef(f"{self.prefixes['mrs']}type"),
                allowMultiple=True,
            )
            name = None
            if out1 and "ipv4-address" in str(out1):
                name = "ipv4-address"
            elif out1 and "ipv6-address" in str(out1):
                name = "ipv6-address"
            else:
                continue
            vals = scanVals.setdefault(name, {})
            vals["uri"] = str(item)
            vals["type"] = "|".join([str(item) for item in sorted(out1)])
            out2 = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}value"))
            if out2:
                vals["value"] = str(out2[0])
            self._hasTags(gIn, item, vals, False, vswParams)

    def _recordMapping(self, subnet, returnout, mappingKey, subKey, val=""):
        """Query Graph and add all mappings"""
        returnout = self.intOut(subnet, returnout.setdefault(mappingKey, {}))
        returnout.setdefault(subKey, {})
        returnout[subKey].setdefault(str(subnet), {})
        returnout[subKey][str(subnet)][val] = ""

    def parsePorts(self, gIn, connectionID, hostsOnly=False):
        """Get all ports for any connection and scan all of them"""
        for key in ["hasBidirectionalPort", "isAlias"]:
            tmpPorts = self.queryGraph(
                gIn,
                connectionID,
                search=URIRef(f"{self.prefixes['nml']}{key}"),
                allowMultiple=True,
            )
            for port in tmpPorts:
                if hostsOnly and not self.hostsOnly(port):
                    continue
                if port not in self.bidPorts and str(port) not in self.scannedPorts:
                    self.bidPorts.setdefault(port, [])
                    self.bidPorts[port].append(key)
                if str(port) in self.scannedPorts:
                    self.scannedPorts[str(port)].append(key)

    def _portScanFinish(self, bidPort):
        """Check if port was already scanned"""
        if str(bidPort) not in self.scannedPorts:
            self.scannedPorts[str(bidPort)] = self.bidPorts[bidPort]
        if bidPort in self.bidPorts:
            del self.bidPorts[bidPort]

    def parseL2Ports(self, gIn, connectionID, connOut, custom=False):
        """Parse L2 Ports"""
        # Get All Ports
        self.parsePorts(gIn, connectionID)
        # If not custom (means not kube or single port) - we need to get isAlias
        # and also any time scheduling information
        if not custom:
            alias = self.getisAlias(gIn, connectionID)
            if alias:
                connOut["isAlias"] = alias
            # Get time scheduling details for connection.
            self.getTimeScheduling(gIn, connectionID, connOut)
        # =======================================================
        while self.bidPorts:
            for bidPort in list(self.bidPorts.keys()):
                # Preset defaults in out (hostname,port)
                if not str(bidPort).startswith(self.prefixes["site"]):
                    # For L3 - it can include other endpoint port,
                    # We dont need to parse that and it is isAlias in dict
                    self._portScanFinish(bidPort)
                    continue
                if str(bidPort) in self.scannedPorts:
                    self._portScanFinish(bidPort)
                    continue
                if custom:
                    # Get isAlias - which will be used as key in output
                    tmpOut = connOut.setdefault(str(bidPort), {})
                    self.getTimeScheduling(gIn, bidPort, tmpOut)
                else:
                    tmpOut = connOut
                portOut = self.intOut(bidPort, tmpOut)
                # Record port URI
                portOut["uri"] = str(bidPort)
                # Parse all ports in port definition
                self.parsePorts(gIn, bidPort, True)
                alias = self.getisAlias(gIn, bidPort)
                if alias:
                    portOut["isAlias"] = alias
                # Get time scheduling information from delta
                self.getTimeScheduling(gIn, bidPort, portOut)
                # Get all tags for Port
                try:
                    self._hasTags(gIn, bidPort, portOut, self.singleport)
                except NotFoundError:
                    self._portScanFinish(bidPort)
                    if str(bidPort) in connOut:
                        del connOut[str(bidPort)]
                    continue
                # Get All Labels
                self._hasLabel(gIn, bidPort, portOut)
                # Get all Services
                self._hasService(gIn, bidPort, portOut)
                # Get all Network address configs
                self._hasNetwork(gIn, bidPort, portOut)
                # Move port to finished scan ports
                self._portScanFinish(bidPort)
        return connOut

    def parsel2Request(self, gIn, returnout, _switchName):
        """Parse L2 request."""
        self.logger.info(f"Lets try to get connection ID subject for {self.prefixes['main']}")
        cout = self.queryGraph(
            gIn,
            URIRef(self.prefixes["main"]),
            search=URIRef(f"{self.prefixes['mrs']}providesSubnet"),
        )
        for connectionID in cout:
            self._recordMapping(connectionID, returnout, "SubnetMapping", "providesSubnet")
            returnout.setdefault("vsw", {})
            connOut = returnout["vsw"].setdefault(str(connectionID), {})
            self._hasTags(gIn, connectionID, connOut)
            self.logger.info(f"This is our connection ID: {connectionID}")
            out = self.queryGraph(gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}labelSwapping"))
            if out:
                connOut.setdefault("_params", {}).setdefault("labelSwapping", str(out[0]))
            # Parse hasNetworkAddress (debugip)
            paramsOut = connOut.setdefault("_params", {})
            self._hasNetwork(gIn, connectionID, paramsOut, True)
            self.parseL2Ports(gIn, connectionID, connOut)
        return returnout

    @staticmethod
    def identifyglobalstate(tmpstates):
        """Based on all subdelta states, identify top level delta state"""
        if not tmpstates:
            return "activated" # TODO: Review after SC. 
        if "activate-error" in tmpstates:
            return "activate-error"
        if "deactivate-error" in tmpstates:
            return "deactivate-error"
        if tmpstates.count("activated") == len(tmpstates):
            return "activated"
        if tmpstates.count("deactivated") == len(tmpstates):
            return "deactivated"
        if "activated" in tmpstates:
            return "activating"
        if "deactivated" in tmpstates:
            return "deactivating"
        return "unknown"

    def topLevelDeltaState(self):
        """Identify and set top level delta state"""
        for key, vals in self.newActive["output"].get("vsw", {}).items():
            if "_params" in vals:
                tmpcopy = copy.deepcopy(vals)
                del tmpcopy["_params"]
                tmpstates = dictSearch("networkstatus", tmpcopy, [], ["hasService"])
                globst = self.identifyglobalstate(tmpstates)
                self.logger.debug(f"Identified global state for {key} as {globst}. All states: {tmpstates}")
                self.newActive["output"]["vsw"][key]["_params"]["networkstatus"] = globst

    def recordDeltaStates(self):
        """Record delta states in activeDeltas output"""
        changed = False
        for dbout in self.dbI.get("deltatimestates", limit=100, orderby=["insertdate", "DESC"]):
            if self.newActive["output"].get(dbout["uuidtype"], {}).get(dbout["uuid"], {}).get(dbout["hostname"], {}).get(dbout["hostport"], {}):
                actEntry = self.newActive["output"].setdefault(dbout["uuidtype"], {}).setdefault(dbout["uuid"], {}).setdefault(dbout["hostname"], {}).setdefault(dbout["hostport"], {})
                actEntry.setdefault("_params", {})
                actEntry["_params"]["networkstatus"] = dbout["uuidstate"]
                if "hasService" in actEntry:
                    actEntry["hasService"].setdefault("_params", {})
                    actEntry["hasService"]["_params"]["networkstatus"] = dbout["uuidstate"]
            changed = True
            self.dbI.delete("deltatimestates", [["id", dbout["id"]]])
        self.topLevelDeltaState()
        return changed

    def generateActiveConfigDict(self, currentGraph, usedIPs, usedVLANs):
        """Generate new config from parser model."""
        self._refreshHosts()
        changesApplied = False
        self.currentActive = getActiveDeltas(self)
        self.newActive = copy.deepcopy(self.currentActive)
        modelParseRan = False
        for delta in self.dbI.get(
            "deltas",
            limit=10,
            search=[["state", "activating"], ["modadd", "add"]],
            orderby=["insertdate", "ASC"],
        ):
            gCopy = copy.deepcopy(currentGraph)
            # Deltas keep string in DB, so we need to eval that
            # 1. Get delta content for reduction, addition
            # 2. Add into model and see if it overlaps with any
            delta["content"] = evaldict(delta["content"])
            # 3. Add to current graph
            currentGraph = self._addDeltasToModel(currentGraph, delta["content"])
            # Now we parse new model and generate new currentActive config
            self.newActive["output"] = self.parseModel(currentGraph)
            modelParseRan = True
            # Now we ready to check if any of deltas overlap
            # if they do - means new delta should not be added
            # And we should get again clean model for next delta check
            try:
                self.conflictChecker.checkConflicts(self, self.newActive["output"], self.currentActive["output"], False)
                self.stateMachine.modelstatechanger(self.dbI, "added", **delta)
                changesApplied = True
            except (OverlapException, WrongIPAddress, ServiceNotReady) as ex:
                self.stateMachine.modelstatechanger(self.dbI, "failed", **delta)
                # If delta apply failed we return right away without writing new Active config
                self.logger.debug(f"There was failure applying delta. Failure {ex}")
                # Overwrite back the model with original before failure.
                currentGraph = copy.deepcopy(gCopy)

        if not modelParseRan:
            self.newActive["output"] = self.parseModel(currentGraph)

        # Record all states
        if self.recordDeltaStates():
            changesApplied = True

        # Check if there is any difference between old and current.
        for diff in list(
            dictdiffer.diff(
                self.currentActive["output"],
                self.newActive["output"],
                ignore=set(["usedIPs", "usedVLANs"]),
            )
        ):
            self.logger.debug(f"New diff: {diff}")
        self.currentActive["output"] = copy.deepcopy(self.newActive["output"])

        # Check if there is any conflict with expired entities
        self.logger.info("Conflict Check of expired entities")
        newconf, cleaned = self.conflictChecker.checkActiveConfig(self.currentActive["output"])
        if cleaned:
            self.logger.info("IMPORTANT: State changed. Writing new config to DB.")
            self.currentActive["output"] = copy.deepcopy(newconf)
            changesApplied = True

        # Check if there are any forced cleanups (via API)
        newconf, override = self._instanceoverride(self.currentActive["output"])
        if override:
            self.logger.info("IMPORTANT: State changed due to forced DB timestamp change. Writing new config to DB.")
            self.currentActive["output"] = copy.deepcopy(newconf)
            changesApplied = True
        # Include used IPs and VLANs
        self.currentActive["output"]["usedIPs"] = usedIPs
        self.currentActive["output"]["usedVLANs"] = usedVLANs
        # Write active deltas to DB (either changed or not changed).
        writeActiveDeltas(self, self.currentActive["output"])
        if changesApplied:
            self.logger.info("-" * 100)
            self.logger.info("Here is new current Active output")
            self.logger.info(pprint.pformat(self.currentActive["output"]))
        return changesApplied

    def _instanceoverride(self, currentActive):
        """Check if there are any forced cleanups (via API)."""

        def __setlifetime(initem, timestamps):
            """Set lifetime inside initem."""
            lifetime = initem.setdefault("existsDuring", {})
            if timestamps[0] != 0:
                lifetime["start"] = timestamps[0]
            else:
                del lifetime["start"]
            if timestamps[1] != 0:
                lifetime["end"] = timestamps[1]
            else:
                del lifetime["end"]

        def __loopsubitems(indeltas, outdeltas, timestamps):
            """Loop subitems under instance and set lifetime."""
            for key, val in indeltas.items():
                if key == "_params":
                    workitem = outdeltas.setdefault("_params", {})
                    __setlifetime(workitem, timestamps)
                elif isinstance(val, dict):
                    workitem = outdeltas.setdefault(key, {})
                    __loopsubitems(val, workitem, timestamps)

        modified = False
        # Get from database all overrides in instancestartend database
        newconf = copy.deepcopy(currentActive)
        for override in self.dbI.get("instancestartend", limit=100):
            instanceid = override["instanceid"]
            timestamps = (
                int(override["starttimestamp"]),
                int(override["endtimestamp"]),
            )
            # Identify if it vsw or rst
            if instanceid in newconf.get("vsw", {}):
                args = ("vsw", instanceid)
            elif instanceid in newconf.get("rst", {}):
                args = ("rst", instanceid)
            else:
                continue
            # Set lifetime for all subitems
            __loopsubitems(currentActive[args[0]][args[1]], newconf[args[0]][args[1]], timestamps)
            # Remove from database
            self.dbI.delete("instancestartend", [["id", override["id"]]])
            modified = True
        return newconf, modified

    def startworklookup(self, currentGraph, usedIPs, usedVlans):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started via Lookup")
        self.__clean()
        # generate new out
        changesApplied = self.generateActiveConfigDict(currentGraph, usedIPs, usedVlans)
        return changesApplied

    def startwork(self):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        speedup = False
        fnewdir = os.path.join(self.config.get(self.sitename, "privatedir"), "PolicyService", "httpnew")
        ffinishdir = os.path.join(
            self.config.get(self.sitename, "privatedir"),
            "PolicyService",
            "httpfinished",
        )
        # Find all files in new directory (not ending with .tmp)
        for fname in os.listdir(fnewdir):
            if fname.endswith(".tmp"):
                continue
            fullpath = os.path.join(fnewdir, fname)
            self.logger.info(f"Processing delta {fullpath}")
            out = self.acceptDelta(fullpath)
            # Write output to a new file in finished directory
            self.siteDB.saveContent(os.path.join(ffinishdir, fname), out)
            self.siteDB.removeFile(fullpath)
            speedup = True
        self.logger.info("Component PolicyService Finished")
        return speedup

    def deltaToModel(self, currentGraph, deltaPath, action):
        """Add delta to current Model. If no delta provided, returns current Model"""
        if not currentGraph:
            _, currentGraph = getCurrentModel(self, True)
            self._refreshHosts()
            self.getSavedPrefixes()
        if deltaPath and action:
            gIn = parseRDFFile(deltaPath)
            if action == "reduction":
                currentGraph -= gIn
            elif action == "addition":
                currentGraph += gIn
            else:
                raise Exception(f"Unknown delta action. Action submitted {action}")
        return currentGraph

    def _addDeltasToModel(self, currentGraph, deltaContent):
        """Add deltas to current graph."""
        for key, value in deltaContent.items():
            if not value:
                continue
            if key not in ["reduction", "addition"]:
                continue
            self.logger.debug(f"Adding Content {value} for key {key}")
            with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                tmpFile = fd.name
                try:
                    fd.write(value)
                except ValueError:
                    fd.write(decodebase64(value))
            currentGraph = self.deltaToModel(currentGraph, tmpFile, key)
            os.unlink(tmpFile)
        return currentGraph

    def _addAllPendingDeltas(self, currentGraph):
        """Add all accepted deltas to the current graph."""
        self.logger.info(f"Adding all accepted deltas to the current graph, not older than {DELTA_COMMIT_TIMEOUT} seconds")
        for delta in self.dbI.get("deltas", search=[["state", "accepted"], ["insertdate", ">", getUTCnow() - DELTA_COMMIT_TIMEOUT]], limit=50):
            delta["content"] = evaldict(delta["content"])
            self.logger.debug(f"Adding delta {delta['uid']} to current graph")
            currentGraph = self._addDeltasToModel(currentGraph, delta["content"])
        # We also need to add all committing, committed, activating
        for state in ["committing", "committed", "activating"]:
            self.logger.info(f"Adding all {state} deltas to the current graph")
            # We limit to 50 deltas, so we do not overload the system
            # This is needed for cases when we have multiple deltas in committing state
            # and we want to apply them all at once.
            for delta in self.dbI.get("deltas", search=[["state", state]], limit=50):
                delta["content"] = evaldict(delta["content"])
                self.logger.debug(f"Adding delta {delta['uid']} to current graph")
                currentGraph = self._addDeltasToModel(currentGraph, delta["content"])
        return currentGraph

    def acceptDelta(self, deltapath):
        """Accept delta."""
        self._refreshHosts()
        currentGraph = self.deltaToModel(None, None, None)
        currentGraph = self._addAllPendingDeltas(currentGraph)
        self.currentActive = getActiveDeltas(self)
        self.newActive = {"output": {}}
        fileContent = self.siteDB.getFileContentAsJson(deltapath)
        self.logger.info(f"Called Accept Delta. Content Location: {deltapath}")
        self.siteDB.removeFile(deltapath)
        toDict = dict(fileContent)
        toDict["State"] = "accepting"
        toDict["Type"] = "submission"
        toDict["modadd"] = "idle"
        try:
            self._addDeltasToModel(currentGraph, toDict.get("content", {}))
            self.newActive["output"] = self.parseModel(currentGraph)
            try:
                self.conflictChecker.checkConflicts(self, self.newActive["output"], self.currentActive["output"], True)
            except (OverlapException, WrongIPAddress, ServiceNotReady) as ex:
                self.logger.info(f"There was failure accepting delta. Failure {ex}")
                toDict["State"] = "failed"
                toDict["Error"] = getError(ex)
                self.stateMachine.failed(self.dbI, toDict)
                return toDict
        except IOError as ex:
            toDict["State"] = "failed"
            toDict["Error"] = getError(ex)
            self.stateMachine.failed(self.dbI, toDict)
        else:
            toDict["State"] = "accepted"
            self.stateMachine.accepting(self.dbI, toDict)
            # =================================
        return toDict


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args:
        if args.sitename:
            policer = PolicyService(config, args.sitename)
            if args.action == "accept":
                out = policer.acceptDelta(args.delta)
                pprint.pprint(out)
            elif args.action == "acceptid" and args.deltaid:
                delta = policer.dbI.get("deltas", search=[["uid", args.deltaid]], limit=1)
                if not delta:
                    raise Exception(f"Delta {args.deltaid} not found in database")
                delta = delta[0]
                delta["content"] = evaldict(delta["content"])
                tmpfd = tempfile.NamedTemporaryFile(delete=False, mode="w+")
                tmpfd.close()
                policer.siteDB.saveContent(tmpfd.name, delta)
                out = policer.acceptDelta(tmpfd.name)
                pprint.pprint(out)
            elif args.action in ["addition", "reduction"]:
                newModel = policer.deltaToModel(None, args.delta, args.action)
                out = policer.parseModel(newModel)
                pprint.pprint(out)
        elif args.action == "fullRun":
            policer = PolicyService(config, getSiteNameFromConfig(config))
            policer.startwork()


def get_parser():
    """Returns the argparse parser."""
    # pylint: disable=line-too-long
    oparser = argparse.ArgumentParser(
        description="This daemon is used for delta reduction, addition parsing",
        prog=os.path.basename(sys.argv[0]),
        add_help=True,
    )
    # Main arguments
    oparser.add_argument(
        "--action",
        dest="action",
        default="",
        help="Actions to execute. Options: [accept,acceptid, addition, reduction, fullRun]",
    )
    oparser.add_argument(
        "--sitename",
        dest="sitename",
        default="",
        help="Sitename of FE. Must be present in configuration and database.",
    )
    oparser.add_argument(
        "--delta",
        dest="delta",
        default="",
        help="Delta path. In case of accept action - need to be json format from DB. Otherwise - delta from Orchestrator",
    )
    oparser.add_argument(
        "--deltaid",
        dest="deltaid",
        required=False,
        default="",
        help="Delta id from db. In case of accept action - will load from database",
    )

    return oparser


if __name__ == "__main__":
    argparser = get_parser()
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    if len(sys.argv) == 1:
        argparser.print_help()
    inargs = argparser.parse_args(sys.argv[1:])
    getLoggingObject(logType="StreamLogger", service="PolicyService")
    execute(args=inargs)
