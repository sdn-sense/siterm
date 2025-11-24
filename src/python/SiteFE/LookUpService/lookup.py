#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    LookUpService gets all information and prepares MRML schema.
Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""
import copy
import os
import time
from datetime import datetime, timezone

from rdflib import Graph
from rdflib.compare import isomorphic
from SiteFE.LookUpService.modules.deltainfo import DeltaInfo
from SiteFE.LookUpService.modules.nodeinfo import NodeInfo
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper
from SiteFE.LookUpService.modules.switchinfo import SwitchInfo
from SiteFE.PolicyService.policyService import PolicyService
from SiteFE.ProvisioningService.provisioningService import ProvisioningService
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.BWService import BWService
from SiteRMLibs.CustomExceptions import NoOptionError, NoSectionError
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.ipaddr import normalizedip
from SiteRMLibs.MainUtilities import (
    createDirs,
    externalCommand,
    firstRunCheck,
    generateHash,
    getActiveDeltas,
    getCurrentModel,
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
    parseRDFFile,
)
from SiteRMLibs.timing import Timing
from SiteRMLibs.Warnings import Warnings


class MultiWorker:
    """MultiWorker to launch Switch update workers"""

    def __init__(self, config, sitename, logger):
        super().__init__()
        self.config = config
        self.sitename = sitename
        self.logger = logger
        self.firstRun = True
        self.needRestart = False

    def _runCmd(self, action, device, foreground=False):
        """Start execution of new SwitchWroker process"""
        retOut = {"stdout": [], "stderr": [], "exitCode": -1}
        command = f"SwitchWorker --action {action} --devicename {device}"
        if action == "status":
            command += " --forceremovepid"
        if foreground:
            command += " --foreground"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut["stdout"] += out.split("\n")
        retOut["stderr"] += err.split("\n")
        retOut["exitCode"] = cmdOut.returncode
        return retOut

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.needRestart = True

    def startwork(self):
        """Multiworker main process"""
        self.logger.info("Started MultiWorker work to check switch processes")
        restarted = False
        siteName = getSiteNameFromConfig(self.config)
        for dev in self.config.get(siteName, "switch"):
            # Check status
            retOut = self._runCmd("status", dev)
            # If status failed, and first run, start it
            if retOut["exitCode"] != 0 and self.firstRun:
                self.logger.info(f"Starting SwitchWorker for {dev}")
                retOut = self._runCmd("start", dev, True)
                self.logger.info(f"Starting SwitchWorker for {dev} - {retOut}")
                restarted = True
                continue
            # If status failed, and not first run, restart it
            if retOut["exitCode"] != 0 and not self.firstRun:
                self.logger.error(f"SwitchWorker for {dev} failed: {retOut}")
                retOut = self._runCmd("restart", dev, True)
                self.logger.info(f"Restarting SwitchWorker for {dev} - {retOut}")
                restarted = True
                continue
            # If status is OK, and needRestart flag set - restart it
            if retOut["exitCode"] == 0 and self.needRestart:
                self.logger.info(f"Restarting SwitchWorker for {dev} as it is instructed by config change")
                retOut = self._runCmd("restart", dev, True)
                self.logger.info(f"Restarting SwitchWorker for {dev} - {retOut}")
                restarted = True
                continue
            # If status is OK, and needRestart flag set - restart it
            if retOut["exitCode"] != 0 and self.needRestart:
                self.logger.info(f"Restarting Failed SwitchWorker for {dev} as it is instructed by config change")
                retOut = self._runCmd("restart", dev, True)
                self.logger.info(f"Restarting SwitchWorker for {dev} - {retOut}")
                restarted = True
                continue
        # Mark as not first run, so if service stops, it uses restart
        if self.firstRun and restarted:
            self.logger.info("First run is done. Marking as not first run. Also sleep 1 minute so that it get's all data from switches")
            time.sleep(60)
        self.firstRun = False
        self.needRestart = False


# pylint: disable=too-many-instance-attributes
class LookUpService(SwitchInfo, NodeInfo, DeltaInfo, RDFHelper, BWService, Timing, Warnings):
    """Lookup Service prepares MRML model about the system."""

    def __init__(self, config, sitename):
        super().__init__()
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="LookUpService")
        self.dbI = getVal(getDBConn("LookUpService", self), **{"sitename": self.sitename})
        self.newGraph = None
        self.shared = "notshared"
        self.hosts = {}
        self.switch = Switch(config, sitename)
        self.prefixes = {}
        self.police = PolicyService(self.config, self.sitename, self.logger)
        self.provision = ProvisioningService(self.config, self.sitename, self.logger)
        self.tmpout = {}
        self.activeDeltas = {}
        self.multiworker = MultiWorker(self.config, self.sitename, self.logger)
        self.URIs = {"vlans": {}, "ips": {}}
        self.usedVlans = {"deltas": {}, "system": {}}
        self.usedIPs = {"deltas": {}, "system": {}}  # Reset used IPs.
        for dirname in ["LookUpService", "SwitchWorker"]:
            createDirs(f"{self.config.get(self.sitename, 'privatedir')}/{dirname}/")
        self.firstRun = True
        self._addedTriples = set()
        self.modelDiffCounter = 0

    def __clean(self):
        """Clean params of LookUpService"""
        self._addedTriples = set()
        # Clean errors after 100 cycles
        # pylint: disable=E1101
        self.runcount += 1
        if self.runcount >= 100:
            self.cleanWarnings()

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)
        self.police.refreshthread()
        self.provision.refreshthread()
        self.multiworker.refreshthread()

    def _getIPURIs(self, indict, host, iptype):
        """Get All IP URIs if any"""
        if "hasNetworkAddress" in indict and f"{iptype}-address" in indict["hasNetworkAddress"]:
            uri = indict["hasNetworkAddress"][f"{iptype}-address"].get("uri", "")
            ip = indict["hasNetworkAddress"][f"{iptype}-address"].get("value", "")
            if ip:
                ip = normalizedip(ip)
                self.usedIPs["deltas"].setdefault(host, {"ipv4": [], "ipv6": []})
                if ip not in self.usedIPs["deltas"][host][iptype]:
                    self.usedIPs["deltas"][host][iptype].append(ip)
            if uri and ip:
                self.URIs["ips"].setdefault(normalizedip(ip), indict["hasNetworkAddress"][f"{iptype}-address"])

    def _getUniqueVlanURIs(self, qtype):
        """Get Unique URI for VLANs"""
        # pylint: disable=too-many-nested-blocks
        for _subnet, hostDict in self.activeDeltas.get("output", {}).get(qtype, {}).items():
            if not self.checkIfStarted(hostDict):
                continue
            for host, portDict in hostDict.items():
                if not isinstance(portDict, dict):
                    continue
                if not self.checkIfStarted(portDict):
                    continue
                for port, reqDict in portDict.items():
                    if not isinstance(reqDict, dict):
                        continue
                    if "uri" in reqDict and reqDict["uri"] and "hasLabel" in reqDict and reqDict["hasLabel"]:
                        vlan = reqDict["hasLabel"].get("value", 0)
                        if vlan:
                            self.URIs["vlans"].setdefault(host, {})
                            self.URIs["vlans"][host].setdefault(port, {})
                            self.URIs["vlans"][host][port][int(vlan)] = reqDict["uri"]
                            # Add vlan into used vlans list
                            self.usedVlans["deltas"].setdefault(host, [])
                            if int(vlan) not in self.usedVlans["deltas"][host]:
                                self.usedVlans["deltas"][host].append(int(vlan))
                    self._getIPURIs(reqDict, host, "ipv4")
                    self._getIPURIs(reqDict, host, "ipv6")

    def checkForModelDiff(self, saveName):
        """Check if models are different."""
        currentModel, currentGraph = getCurrentModel(self, False)
        if not currentModel or not currentGraph:
            self.logger.error("Current model or graph is empty. Cannot compare.")
            return False, None
        newGraph = parseRDFFile(saveName)
        return isomorphic(currentGraph, newGraph), currentModel

    def getModelSavePath(self):
        """Get Model Save Location."""
        now = datetime.now(timezone.utc)
        saveDir = f"{self.config.get(self.sitename, 'privatedir')}/LookUpService/"
        version = f"{now.year}-{now.month}-{now.day}:{now.hour}:{now.minute}:{now.second}"
        return f"{saveDir}/{version}.mrml"

    def saveModel(self, saveName, onlymaster=False):
        """Save Model."""
        if not onlymaster:
            for retmodeltype in ["json-ld", "ntriples", "turtle"]:
                saveNameSub = f"{saveName}.{retmodeltype}"
                with open(saveNameSub, "w", encoding="utf-8") as fd:
                    fd.write(self.newGraph.serialize(format=retmodeltype))
        # Save original file too
        with open(saveName, "w", encoding="utf-8") as fd:
            fd.write(self.newGraph.serialize(format="ntriples"))

    def _addTopTology(self):
        """Add Main Topology definition to Model."""
        out = {
            "sitename": self.sitename,
            "labelswapping": "false",
            "name": self.prefixes["site"],
        }
        if self.config.has_option("general", "webdomain"):
            out["webdomain"] = self.config.get("general", "webdomain")
        self._addSite(**out)
        self._addMetadata(**out)
        return out

    def defineTopology(self):
        """Defined Topology and Main Services available."""
        # Add main Topology
        out = self._addTopTology()
        # Add Service for each Switch
        for switchName in self.config.get(self.sitename, "switch"):
            out["hostname"] = switchName
            try:
                out["vsw"] = self.config.get(switchName, "vsw")
            except (NoOptionError, NoSectionError) as ex:
                self.logger.debug(
                    "Warning: vsw parameter is not defined for %s. Err: %s",
                    switchName,
                    ex,
                )
                continue
            try:
                out["labelswapping"] = self.config.get(switchName, "labelswapping")
            except NoOptionError:
                self.logger.debug("Warning. Labelswapping parameter is not defined. Default is False.")
            out["nodeuri"] = self._addNode(**out)
            out["switchingserviceuri"] = self._addSwitchingService(**out)
            self._addLabelSwapping(**out)

    def recordSystemIPs(self, switchName, key, val):
        """Record System IPs."""
        if key not in ["ipv4", "ipv6"]:
            return
        self.usedIPs["system"].setdefault(switchName, {"ipv4": [], "ipv6": []})
        for item in val:
            if "address" not in item or "masklen" not in item:
                continue
            ipaddr = f"{item.get('address', '')}/{item.get('masklen', '')}"
            if ipaddr not in self.usedIPs["system"][switchName][key] and ipaddr not in self.usedIPs["deltas"].get(switchName, {}).get(key, []):
                self.usedIPs["system"][switchName][key].append(ipaddr)

    def filterOutAvailbVlans(self, hostname, vlanrange):
        """Filter out available vlans for a hostname."""
        tmprange = copy.deepcopy(vlanrange)
        if hostname in self.usedVlans.get("deltas", {}):
            for vlan in self.usedVlans["deltas"][hostname]:
                if vlan in tmprange:
                    tmprange.remove(vlan)
        if hostname in self.usedVlans.get("system", {}):
            for vlan in self.usedVlans["system"][hostname]:
                if vlan in tmprange:
                    tmprange.remove(vlan)
        return tmprange

    def checkVlansWarnings(self):
        """Check and raise warnings in case some vlans are used/configured manually."""
        # Check that for all vlan range, if it is on system usedVlans - it should be on deltas too;
        # otherwise it means vlan is configured manually (or deletion did not happen)
        for host, vlans in self.usedVlans["system"].items():
            if host in self.config.config.get("MAIN", {}):
                # Means it is a switch (host check remains for Agents itself)
                all_vlan_range_list = self.config.config.get("MAIN", {}).get(host, {}).get("all_vlan_range_list", [])
                for vlan in vlans:
                    if vlan in all_vlan_range_list and vlan not in self.usedVlans["deltas"].get(host, []):
                        self.addWarning(f"Vlan {vlan} is configured manually on {host}. It comes not from delta." "Either deletion did not happen or was manually configured.")
        # Add switchwarnings (in case any exists)
        # pylint: disable=E1101
        self.warnings += self.switch.getWarnings()

    def cleanModelDirectory(self):
        """Clean Model Directory."""
        saveDir = f"{self.config.get(self.sitename, 'privatedir')}/LookUpService/"
        # Find out all files in the directory, older than 7 days
        for file in os.listdir(saveDir):
            filePath = os.path.join(saveDir, file)
            if not os.path.isfile(filePath):
                continue
            # Get file creation time
            fileTime = os.path.getmtime(filePath)
            if fileTime < getUTCnow() - 604800:
                self.logger.info(f"Removing old model file {filePath}")
                os.unlink(filePath)

    def startwork(self):
        """Main start."""
        # pylint: disable=too-many-statements
        speedup = False
        self.logger.info("Started LookupService work")
        firstRunCheck(self.firstRun, "LookUpService")
        self.__clean()
        stateChangedFirstRun = False
        if self.firstRun:
            self.logger.info("Because it is first run, we will start apply first to all devices individually")
            self.logger.info("In case there are many resources, it might take a while. Check ProvisioningService logs for more information")
            stateChangedFirstRun = self.provision.startwork(self.firstRun)
            self.firstRun = False
        self.multiworker.startwork()
        self.activeDeltas = getActiveDeltas(self)
        self.URIs = {"vlans": {}, "ips": {}}  # Reset URIs
        self.usedVlans = {"deltas": {}, "system": {}}  # Reset used vlans
        self.usedIPs = {"deltas": {}, "system": {}}  # Reset used IPs.
        for key in ["vsw", "kube", "singleport"]:
            self._getUniqueVlanURIs(key)
        self.newGraph = Graph()
        # ==================================================================================
        # Define Basic MRML Prefixes
        # ==================================================================================
        self.defineMRMLPrefixes()
        # ==================================================================================
        # Define Topology Site
        # ==================================================================================
        self.defineTopology()
        self.hosts = {}
        # ==================================================================================
        # Define Node inside yaml
        # ==================================================================================
        self.addNodeInfo()
        # ==================================================================================
        # Define Switch information from Switch Lookup Plugin
        # ==================================================================================
        self.addSwitchInfo()
        # ==================================================================================
        # Add all active running config
        # ==================================================================================
        self.addDeltaInfo()
        # ==================================================================================
        # Print used IPs and vlans
        # ==================================================================================
        self.logger.info(f"Used IPs: {self.usedIPs}")
        self.logger.info(f"Used vlans: {self.usedVlans}")
        # ==================================================================================
        # Start Policy Service and apply any changes (if any)
        # ==================================================================================
        changesApplied = self.police.startworklookup(self.newGraph, self.usedIPs, self.usedVlans)
        self.logger.info(f"Changes there recorded in db: {changesApplied}")
        self.activeDeltas = getActiveDeltas(self)
        self.addDeltaInfo()

        saveName = self.getModelSavePath()
        self.saveModel(saveName, onlymaster=True)
        serialized = self.newGraph.serialize(format="ntriples")
        hashNum = generateHash(serialized)

        self.logger.info("Checking if new model is different from previous")
        modelsEqual, modelinDB = self.checkForModelDiff(saveName)
        lastKnownModel = {"uid": hashNum, "insertdate": getUTCnow(), "fileloc": saveName}
        updateNeeded = False
        if modelsEqual:
            if modelinDB[0]["insertdate"] < int(getUTCnow() - 3600):
                # Force to update model every hour, Even there is no update;
                self.logger.info("Forcefully update model in db as it is older than 1h")
                self.saveModel(saveName)
                self.dbI.insert("models", [lastKnownModel])
                self.modelDiffCounter = 0
                speedup = True
            else:
                self.logger.info("Models are equal.")
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
                # Check if model difference counter is more than 60 - if yes, then raise warning
                if self.modelDiffCounter >= 60:
                    self.addWarning("Model has updated more than 60 times. Please check LookupService/PolicyService for possible issues.")
        else:
            updateNeeded = True
            self.logger.info("Models are different. Update DB")
            self.modelDiffCounter += 1
            self.saveModel(saveName)
            self.dbI.insert("models", [lastKnownModel])
            speedup = True

        self.logger.debug(f"Last Known Model: {str(lastKnownModel['fileloc'])}")

        # Start Provisioning Service and apply any config changes.
        self.logger.info("Start Provisioning Service")
        stateChanged = self.provision.startwork(self.firstRun)
        # pylint: disable=E1101,E0203,W0201
        if updateNeeded or stateChanged or stateChangedFirstRun:
            self.logger.info("Update is needed. Informing to renew all devices state")
            # If models are different, we need to update all devices information
            self.switch.deviceUpdate(self.sitename)
            speedup = True
        elif self.warningstart and self.warningstart >= getUTCnow() + 3600:  # If warnings raise an hour ago - refresh
            self.warningstart = 0
            self.logger.info("Warnings were raised more than 1hr ago. Informing to renew all devices state")
            self.switch.deviceUpdate(self.sitename)
            speedup = True
        self.checkVlansWarnings()
        if not speedup:
            self.checkAndRaiseWarnings()
            self.cleanModelDirectory()
        return speedup


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    siteName = getSiteNameFromConfig(config)
    lserv = LookUpService(config, siteName)
    i = 20
    while i > 0:
        lserv.startwork()
        time.sleep(5)
        i -= 1


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="LookUpService")
    execute()
