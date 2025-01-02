#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Policy Service which manipulates delta, connection states in DB.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

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
from rdflib import Graph, URIRef
from rdflib.plugins.parsers.notation3 import BadSyntax
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper  # TODO: Move to general
from SiteFE.PolicyService.deltachecks import ConflictChecker
from SiteFE.PolicyService.stateMachine import StateMachine
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import OverlapException, WrongIPAddress
from SiteRMLibs.MainUtilities import (
    contentDB, createDirs, decodebase64, dictSearch,
    evaldict, getActiveDeltas, getAllHosts, getCurrentModel,
    getDBConn, getLoggingObject, getVal, writeActiveDeltas,
    getFileContentAsJson
)
from SiteRMLibs.GitConfig import getGitConfig
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


class PolicyService(RDFHelper, Timing):
    """Policy Service to accept deltas."""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="PolicyService")
        self.siteDB = contentDB()
        self.dbI = getVal(getDBConn("PolicyService", self), **{"sitename": self.sitename})
        self.stateMachine = StateMachine(self.config)
        self.switch = Switch(config, sitename)
        self.hosts = {}
        for siteName in self.config.get("general", "sites"):
            workDir = os.path.join(self.config.get(siteName, "privatedir"), "PolicyService/")
            createDirs(workDir)
        self.getSavedPrefixes(self.hosts.keys())
        self.bidPorts = {}
        self.scannedPorts = {}
        self.scannedRoutes = []
        self.conflictChecker = ConflictChecker(config, sitename)
        self.currentActive = getActiveDeltas(self)
        self.newActive = {}
        self._refreshHosts()
        self.kube = False

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
        self.kube = False

    def _refreshHosts(self):
        """Refresh all hosts information"""
        allHosts = getAllHosts(self.dbI)
        for host, hostDict in allHosts.items():
            self.hosts.setdefault(host, hostDict)
            self.hosts[host]["hostinfo"] = getFileContentAsJson(hostDict["hostinfo"])
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
        tmp = [f for f in str(inport)[len(self.prefixes["site"]):].split(":") if f]
        for item in tmp:
            if item in self.hosts:
                return True
        return False

    def addIsAlias(self, _gIn, bidPort, returnout):
        """Add is Alias to activeDeltas output"""
        if "isAlias" in self.bidPorts.get(
            URIRef(bidPort), []
        ) or "isAlias" in self.scannedPorts.get(bidPort, []):
            returnout["isAlias"] = str(bidPort)

    @staticmethod
    def queryGraph(
        graphIn, sub=None, pre=None, obj=None, search=None, allowMultiple=True
    ):
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
                raise Exception(
                    f"Search returned multiple entries. Not Supported. Out: {foundItems}"
                )
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
            tout = self.queryGraph(
                gIn, statusuri, search=URIRef(f"{self.prefixes['mrs']}value")
            )
            if tout:
                scanVals = connOut.setdefault("_params", {})
                scanVals["networkstatus"] = str(tout[0])

    def getTimeScheduling(self, gIn, connectionID, connOut):
        """Identifying lifetime of the service.
        In case it fails to get correct timestamp, resources will be
        provisioned right away.
        """
        out = self.queryGraph(
            gIn, connectionID, search=URIRef(f"{self.prefixes['nml']}existsDuring")
        )
        for timeline in out:
            times = connOut.setdefault("_params", {}).setdefault(
                "existsDuring", {"uri": str(timeline)}
            )
            for timev in ["end", "start"]:
                tout = self.queryGraph(
                    gIn, timeline, search=URIRef(f"{self.prefixes['nml']}{timev}")
                )
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

    def parseModel(self, gIn):
        """Parse delta request and generateout"""
        self.__clean()
        out = {}
        for key in ["vsw", "rst"]:
            for switchName in self.config.get(self.sitename, "switch"):
                if switchName not in self.prefixes.get(key, {}):
                    self.logger.debug(
                        "Warning: %s parameter is not defined for %s.", key, switchName
                    )
                    continue
                self.prefixes["main"] = self.prefixes[key][switchName]
                if key == "vsw":
                    self.logger.info("Parsing L2 information from model")
                    self.parsel2Request(gIn, out, switchName)
                elif key == "rst":
                    self.logger.info("Parsing L3 information from model")
                    self.parsel3Request(gIn, out, switchName)
        # Parse Host information (a.k.a Kubernetes nodes connected via isAlias)
        for host, hostDict in self.hosts.items():
            if hostDict.get("hostinfo", {}).get("KubeInfo", {}).get("isAlias"):
                self.logger.info("Parsing Kube requests from model")
                for intf, _val in hostDict["hostinfo"]["KubeInfo"]["isAlias"].items():
                    self.kube = True
                    connID = f"{self.prefixes['site']}:{host}:{intf}"
                    out.setdefault("kube", {})
                    connOut = out["kube"].setdefault(str(connID), {})
                    self.parseL2Ports(gIn, URIRef(connID), connOut)
                    self.kube = False
        return out

    def getRoute(self, gIn, connID, returnout):
        """Get all routes from model for specific connID"""
        returnout.setdefault("hasRoute", {})
        routeout = returnout["hasRoute"].setdefault(str(connID), {})
        if str(connID) in self.scannedRoutes:
            return str(connID)
        for rtype in ["nextHop", "routeFrom", "routeTo"]:
            out = self.queryGraph(
                gIn, connID, search=URIRef(f"{self.prefixes['mrs']}{rtype}")
            )
            for item in out:
                mrstypes = self.queryGraph(
                    gIn, item, search=URIRef(f"{self.prefixes['mrs']}type")
                )
                mrsvals = self.queryGraph(
                    gIn, item, search=URIRef(f"{self.prefixes['mrs']}value")
                )
                if mrstypes and mrsvals and len(mrstypes) == len(mrsvals):
                    for index, mrtype in enumerate(mrstypes):
                        if mrtype and mrsvals[index]:
                            routeVals = routeout.setdefault(rtype, {}).setdefault(
                                str(mrtype), {}
                            )
                            routeVals["type"] = str(mrtype)
                            routeVals["value"] = str(mrsvals[index])
                            routeVals["key"] = str(item)
                else:
                    self.logger.warning(
                        f"Either val or type not defined. Key: {str(item)}, Type: {mrstypes}, Val: {mrsvals}"
                    )
        self.scannedRoutes.append(str(connID))
        return ""

    def getRouteTable(self, gIn, connID, returnout):
        """Get all route tables from model for specific connID and call getRoute"""
        out = self.queryGraph(
            gIn, connID, search=URIRef(f"{self.prefixes['mrs']}hasRoute")
        )
        tmpRet = []
        for item in out:
            tmpRet.append(self.getRoute(gIn, item, returnout))
        return tmpRet

    def parsel3Request(self, gIn, returnout, switchName):
        """Parse Layer 3 Delta Request."""
        self.logger.info(
            f"Lets try to get connection ID subject for {self.prefixes['main']}"
        )
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
                    if connectionID.startswith(
                        f"{uri}:rt-table+vrf-"
                    ) or connectionID.endswith("rt-table+main"):
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
                    connOut = (
                        returnout["rst"]
                        .setdefault(str(connectionID), {})
                        .setdefault(switchName, {})
                        .setdefault(iptype, {})
                    )
                    self._hasService(gIn, connectionID, connOut)
                    self.getTimeScheduling(gIn, connectionID, connOut)
                    connOut[rsttype["key"]] = str(connectionID)
                    rettmp = rsttype["call"](gIn, connectionID, connOut)
                    if rettmp and rsttype["key"] == "providesRoutingTable":
                        # We need to know mapping back, which route belongs to which routing table
                        # There is no such mapping in json, so we manually add this from providesRoutingTable
                        returnout["rst"].setdefault(str(rettmp[0]), {}).setdefault(
                            switchName, {}
                        ).setdefault(iptype, {}).setdefault(
                            "belongsToRoutingTable", str(connectionID)
                        )

    def _hasTags(self, gIn, bidPort, returnout):
        """Query Graph and get Tags"""
        scanVals = returnout.setdefault("_params", {})
        for tag, pref in {"tag": "mrs", "belongsTo": "nml", "encoding": "nml"}.items():
            out = self.queryGraph(
                gIn,
                bidPort,
                search=URIRef(f"{self.prefixes[pref]}{tag}"),
                allowMultiple=True,
            )
            if out:
                scanVals[tag] = str("|".join(out))
        # Get network status if exists
        self.getHasNetworkStatus(gIn, bidPort, returnout)

    def _hasLabel(self, gIn, bidPort, returnout):
        """Query Graph and get Labels"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(
            gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}hasLabel")
        )
        for item in out:
            scanVals = returnout.setdefault("hasLabel", {})
            out = self.queryGraph(
                gIn, item, search=URIRef(f"{self.prefixes['nml']}labeltype")
            )
            if out:
                scanVals["labeltype"] = "ethernet#vlan"
            out = self.queryGraph(
                gIn, item, search=URIRef(f"{self.prefixes['nml']}value")
            )
            if out:
                scanVals["value"] = int(out[0])
            scanVals["uri"] = str(item)

    def _hasService(self, gIn, bidPort, returnout):
        """Query Graph and get Services"""
        self._hasTags(gIn, bidPort, returnout)
        out = self.queryGraph(
            gIn, bidPort, search=URIRef(f"{self.prefixes['nml']}hasService")
        )
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
                out = self.queryGraph(
                    gIn, item, search=URIRef(f"{self.prefixes['mrs']}{key}")
                )
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
            out1 = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}type"), allowMultiple=True)
            name = None
            if out1 and "ipv4-address" in str(out1):
                name = "ipv4-address"
            elif out1 and "ipv6-address" in str(out1):
                name = "ipv6-address"
            else:
                continue
            vals = scanVals.setdefault(name, {})
            vals["uri"] = str(item)
            vals["type"] = "|".join([str(item) for item in out1])
            out2 = self.queryGraph(gIn, item, search=URIRef(f"{self.prefixes['mrs']}value"))
            if out2:
                vals["value"] = str(out2[0])
            if not vswParams:
                self._hasTags(gIn, item, vals)

    def _recordMapping(self, subnet, returnout, mappingKey, subKey, val=""):
        """Query Graph and add all mappings"""
        returnout = self.intOut(subnet, returnout.setdefault(mappingKey, {}))
        returnout.setdefault(subKey, {})
        returnout[subKey].setdefault(str(subnet), {})
        returnout[subKey][str(subnet)][val] = ""

    def parsePorts(self, gIn, connectionID, connOut, hostsOnly=False):
        """Get all ports for any connection and scan all of them"""
        for key in ["hasBidirectionalPort", "isAlias"]:
            tmpPorts = self.queryGraph(
                gIn,
                connectionID,
                search=URIRef(f"{self.prefixes['nml']}{key}"),
                allowMultiple=True,
            )
            for port in tmpPorts:
                if hostsOnly:
                    # If hostsOnly is set - this already parses a subInterface of port;
                    # which usually is a isAlias. It should be parsed on it's own in another
                    # scan - as it needs to be in correct layout. (IsAlias defined by modeling, no force add)
                    if self.kube and (not port.startswith(self.prefixes['site'])):
                        connOut["isAlias"] = str(port)
                    elif key == 'isAlias':
                        connOut["isAlias"] = str(port)
                    if not self.hostsOnly(port):
                        continue
                if port not in self.bidPorts and port not in self.scannedPorts:
                    self.bidPorts.setdefault(port, [])
                    self.bidPorts[port].append(key)
                if port in self.scannedPorts:
                    self.scannedPorts[port].append(key)
                if key == "isAlias":
                    connOut["isAlias"] = str(port)

    def _portScanFinish(self, bidPort):
        """Check if port was already scanned"""
        if bidPort not in self.scannedPorts:
            self.scannedPorts[bidPort] = self.bidPorts[bidPort]
        if bidPort in self.bidPorts:
            del self.bidPorts[bidPort]

    def parseL2Ports(self, gIn, connectionID, connOut):
        """Parse L2 Ports"""
        # Get All Ports
        self.parsePorts(gIn, connectionID, connOut)
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
                portOut = self.intOut(bidPort, connOut)
                # Record port URI
                portOut["uri"] = str(bidPort)
                # Parse all ports in port definition
                self.parsePorts(gIn, bidPort, portOut, True)
                # Get time scheduling information from delta
                self.getTimeScheduling(gIn, bidPort, portOut)
                # Get all tags for Port
                self._hasTags(gIn, bidPort, portOut)
                # Get All Labels
                self._hasLabel(gIn, bidPort, portOut)
                # Get all Services
                self._hasService(gIn, bidPort, portOut)
                # Get all Network address configs
                self._hasNetwork(gIn, bidPort, portOut)
                # Move port to finished scan ports
                self._portScanFinish(bidPort)

    def parsel2Request(self, gIn, returnout, _switchName):
        """Parse L2 request."""
        self.logger.info(
            f"Lets try to get connection ID subject for {self.prefixes['main']}"
        )
        cout = self.queryGraph(
            gIn,
            URIRef(self.prefixes["main"]),
            search=URIRef(f"{self.prefixes['mrs']}providesSubnet"),
        )
        for connectionID in cout:
            self._recordMapping(
                connectionID, returnout, "SubnetMapping", "providesSubnet"
            )
            returnout.setdefault("vsw", {})
            connOut = returnout["vsw"].setdefault(str(connectionID), {})
            self._hasTags(gIn, connectionID, connOut)
            self.logger.info(f"This is our connection ID: {connectionID}")
            out = self.queryGraph(
                gIn,
                connectionID,
                search=URIRef(f"{self.prefixes['nml']}labelSwapping"),
            )
            if out:
                connOut.setdefault("_params", {}).setdefault(
                    "labelSwapping", str(out[0])
                )
            # Parse hasNetworkAddress (debugip)
            paramsOut = connOut.setdefault("_params", {})
            self._hasNetwork(gIn, connectionID, paramsOut, True)
            self.logger.debug(f'ParamsOut: {paramsOut}')
            self.parseL2Ports(gIn, connectionID, connOut)
        return returnout

    @staticmethod
    def identifyglobalstate(tmpstates):
        """Based on all subdelta states, identify top level delta state"""
        if not tmpstates:
            return "deactivated"
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
            for reqkey, reqdict in vals.items():
                if reqkey == "_params":
                    continue
                # TODO Ignore keys hasService should depend on switch configuration
                # if QoS is enabled or not.
                tmpstates = dictSearch("networkstatus", reqdict, [], ['hasService'])
                globst = self.identifyglobalstate(tmpstates)
                if "_params" in vals:
                    self.newActive["output"]["vsw"][key]["_params"][
                        "networkstatus"
                    ] = globst

    def recordDeltaStates(self):
        """Record delta states in activeDeltas output"""
        changed = False
        for dbout in self.dbI.get(
            "deltatimestates", limit=100, orderby=["insertdate", "DESC"]
        ):
            if (
                self.newActive["output"]
                .get(dbout["uuidtype"], {})
                .get(dbout["uuid"], {})
                .get(dbout["hostname"], {})
                .get(dbout["hostport"], {})
            ):
                actEntry = (
                    self.newActive["output"]
                    .setdefault(dbout["uuidtype"], {})
                    .setdefault(dbout["uuid"], {})
                    .setdefault(dbout["hostname"], {})
                    .setdefault(dbout["hostport"], {})
                )
                actEntry.setdefault("_params", {})
                actEntry["_params"]["networkstatus"] = dbout["uuidstate"]
                if "hasService" in actEntry:
                    actEntry["hasService"]["networkstatus"] = dbout["uuidstate"]
            changed = True
            self.dbI.delete("deltatimestates", [["id", dbout["id"]]])
        self.topLevelDeltaState()
        return changed

    def generateActiveConfigDict(self, currentGraph):
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
            for key in ["reduction", "addition"]:
                if delta.get("content", {}).get(key, {}):
                    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                        tmpFile = fd.name
                        try:
                            fd.write(delta["content"][key])
                        except ValueError:
                            fd.write(decodebase64(delta["content"][key]))
                    currentGraph = self.deltaToModel(currentGraph, tmpFile, key)
                    os.unlink(tmpFile)
            # Now we parse new model and generate new currentActive config
            self.newActive["output"] = self.parseModel(currentGraph)
            modelParseRan = True
            # Now we ready to check if any of deltas overlap
            # if they do - means new delta should not be added
            # And we should get again clean model for next delta check
            try:
                self.conflictChecker.checkConflicts(
                    self, self.newActive["output"],
                    self.currentActive["output"], False)
                self.stateMachine.modelstatechanger(self.dbI, "added", **delta)
                changesApplied = True
            except (OverlapException, WrongIPAddress) as ex:
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
        for diff in list(dictdiffer.diff(self.currentActive["output"], self.newActive["output"])):
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
        newconf, override =self._instanceoverride(self.currentActive["output"])
        if override:
            self.logger.info("IMPORTANT: State changed due to forced DB timestamp change. Writing new config to DB.")
            self.currentActive["output"] = copy.deepcopy(newconf)
            changesApplied = True
        # Write active deltas to DB (either changed or not changed).
        writeActiveDeltas(self, self.currentActive["output"])
        return changesApplied

    def _instanceoverride(self, currentActive):
        """Check if there are any forced cleanups (via API)."""
        def __setlifetime(initem, timestamps):
            """Set lifetime inside initem."""
            lifetime = initem.setdefault('existsDuring', {})
            if timestamps[0] != 0:
                lifetime['start'] = timestamps[0]
            else:
                del lifetime['start']
            if timestamps[1] != 0:
                lifetime['end'] = timestamps[1]
            else:
                del lifetime['end']

        def __loopsubitems(indeltas, outdeltas, timestamps):
            """Loop subitems under instance and set lifetime."""
            for key, val in indeltas.items():
                if key == '_params':
                    workitem = outdeltas.setdefault('_params', {})
                    __setlifetime(workitem, timestamps)
                elif isinstance(val, dict):
                    workitem = outdeltas.setdefault(key, {})
                    __loopsubitems(val, workitem, timestamps)

        modified = False
        # Get from database all overrides in instancestartend database
        newconf = copy.deepcopy(currentActive)
        for override in self.dbI.get("instancestartend", limit=100):
            instanceid = override["instanceid"]
            timestamps = (int(override["starttimestamp"]), int(override["endtimestamp"]))
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


    def startworklookup(self, currentGraph):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started via Lookup")
        self.__clean()
        # generate new out
        changesApplied = self.generateActiveConfigDict(currentGraph)
        return changesApplied

    def startwork(self):
        """Start Policy Service."""
        self.logger.info("=" * 80)
        self.logger.info("Component PolicyService Started")
        fnewdir = os.path.join(self.config.get(self.sitename, "privatedir"), "PolicyService", "httpnew")
        ffinishdir = os.path.join(self.config.get(self.sitename, "privatedir"), "PolicyService", "httpfinished")
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
        self.logger.info("Component PolicyService Finished")

    def deltaToModel(self, currentGraph, deltaPath, action):
        """Add delta to current Model. If no delta provided, returns current Model"""
        if not currentGraph:
            _, currentGraph = getCurrentModel(self, True)
            self._refreshHosts()
            self.getSavedPrefixes(self.hosts.keys())
        if deltaPath and action:
            gIn = Graph()
            gIn.parse(deltaPath, format="turtle")
            if action == "reduction":
                currentGraph -= gIn
            elif action == "addition":
                currentGraph += gIn
            else:
                raise Exception(f"Unknown delta action. Action submitted {action}")
        return currentGraph

    def acceptDelta(self, deltapath):
        """Accept delta."""
        self._refreshHosts()
        currentGraph = self.deltaToModel(None, None, None)
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
            for key in ["reduction", "addition"]:
                if toDict.get("Content", {}).get(key, {}):
                    self.logger.debug(
                        f"Got Content {toDict['Content'][key]} for key {key}"
                    )
                    with tempfile.NamedTemporaryFile(delete=False, mode="w+") as fd:
                        tmpFile = fd.name
                        try:
                            fd.write(toDict["Content"][key])
                        except ValueError:
                            fd.write(decodebase64(toDict["Content"][key]))
                    currentGraph = self.deltaToModel(currentGraph, tmpFile, key)
                    os.unlink(tmpFile)
            self.newActive["output"] = self.parseModel(currentGraph)
            try:
                self.conflictChecker.checkConflicts(
                    self, self.newActive["output"],
                    self.currentActive["output"], True)
            except (OverlapException, WrongIPAddress) as ex:
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
            self.stateMachine.accepted(self.dbI, toDict)
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
                delta = policer.dbI.get(
                    "deltas", search=[["uid", args.deltaid]], limit=1
                )
                if not delta:
                    raise Exception(f"Delta {args.deltaid} not found in database")
                delta = delta[0]
                delta["Content"] = evaldict(delta["content"])
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
            for sitename in config.get("general", "sites"):
                policer = PolicyService(config, sitename)
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
