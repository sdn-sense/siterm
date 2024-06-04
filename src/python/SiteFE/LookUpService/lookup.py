#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    LookUpService gets all information and prepares MRML schema.
Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from __future__ import division

import threading
from datetime import datetime, timezone
import os
import time

from rdflib import Graph, URIRef
from rdflib.compare import isomorphic
from SiteFE.LookUpService.modules.deltainfo import DeltaInfo
from SiteFE.LookUpService.modules.nodeinfo import NodeInfo
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper
from SiteFE.LookUpService.modules.switchinfo import SwitchInfo
from SiteFE.PolicyService.policyService import PolicyService
from SiteFE.ProvisioningService.provisioningService import ProvisioningService
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import NoOptionError, NoSectionError
from SiteRMLibs.MainUtilities import (createDirs, generateHash,
                                      getActiveDeltas, getCurrentModel,
                                      getDBConn, getLoggingObject, getUTCnow, getVal,
                                      externalCommand)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.BWService import BWService
from SiteRMLibs.ipaddr import normalizedip

class MultiWorker():
    """SNMP Monitoring Class"""
    def __init__(self, config, sitename, logger):
        super().__init__()
        self.config = config
        self.sitename = sitename
        self.logger = logger
        self.firstRun = True

    def _runCmd(self, action, device, foreground=False):
        """Start execution of new requests"""
        retOut = {'stdout': [], 'stderr': [], 'exitCode': -1}
        command = f"SwitchWorker --action {action} --devicename {device}"
        if foreground:
            command += " --foreground"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut['stdout'] += out.decode("utf-8").split('\n')
        retOut['stderr'] += err.decode("utf-8").split('\n')
        retOut['exitCode'] = cmdOut.returncode
        return retOut

    def startwork(self):
        """Multiworker main process"""
        self.logger.info("Started MultiWorker work to check switch processes")
        for siteName in self.config.get("general", "sites"):
            for dev in self.config.get(siteName, "switch"):
                # Check status
                retOut = self._runCmd('status', dev)
                if retOut['exitCode'] != 0 and self.firstRun:
                    self.logger.info(f"Starting SwitchWorker for {dev}")
                    retOut = self._runCmd('start', dev, True)
                    self.logger.info(f"Starting SwitchWorker for {dev} - {retOut}")
                    continue
                if retOut['exitCode'] != 0 and not self.firstRun:
                    self.logger.error(f"SwitchWorker for {dev} failed: {retOut}")
                    retOut = self._runCmd('restart', dev, True)
                    self.logger.info(f"Restarting SwitchWorker for {dev} - {retOut}")
                    continue
        # Mark as not first run, so if service stops, it uses restart
        if self.firstRun:
            self.logger.info("First run is done. Marking as not first run. Also sleep 1 minute so that it get's all data from switches")
            time.sleep(60)
        self.firstRun = False


class LookUpService(SwitchInfo, NodeInfo, DeltaInfo, RDFHelper, BWService):
    """Lookup Service prepares MRML model about the system."""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="LookUpService")
        self.dbI = getVal(
            getDBConn("LookUpService", self), **{"sitename": self.sitename}
        )
        self.newGraph = None
        self.shared = "notshared"
        self.hosts = {}
        self.switch = Switch(config, sitename)
        self.prefixes = {}
        self.police = PolicyService(self.config, self.sitename)
        self.provision = ProvisioningService(self.config, self.sitename)
        self.tmpout = {}
        self.modelVersion = ""
        self.activeDeltas = {}
        self.renewsNeeded = 3
        self.multiworker = MultiWorker(self.config, self.sitename, self.logger)
        self.URIs = {}
        self.stopThread = False
        self.threads = threading.Thread(target=self._dbthread)
        self.threads.start()
        for dirname in ['LookUpService', 'SwitchWorker']:
            createDirs(f"{self.config.get(self.sitename, 'privatedir')}/{dirname}/")

    def refreshthread(self, *args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.stopThread = True
        self.config = getGitConfig()
        self.dbI = getVal(
            getDBConn("LookUpService", self), **{"sitename": self.sitename}
        )
        self.switch = Switch(self.config, self.sitename)
        self.police.refreshthread(*args)
        self.provision.refreshthread(*args)
        if not args[1]:
            self.__cleanup()
        # Sleep 2 sec to make sure all threads are stopped
        time.sleep(2)
        # And start new thread
        self.threads = threading.Thread(target=self._dbthread)
        self.threads.start()
        self.stopThread = False

    def _dbthread(self):
        """Database thread worker - to change delta states"""
        while not self.stopThread:
            for job in [
                ["committing", self.police.stateMachine.committing],
                ["committed", self.police.stateMachine.committed],
                ["activating", self.police.stateMachine.activating],
                ["activated", self.police.stateMachine.activated],
                ["remove", self.police.stateMachine.remove],
                ["removed", self.police.stateMachine.removed],
            ]:
                job[1](self.dbI)
                # Sleep 0.1 sec between diff checks
                time.sleep(0.5)
            # Sleep 1 sec between diff thread runs
            time.sleep(1)


    def __cleanup(self):
        """Clean up process to remove old data"""
        # Clean Up old models (older than 24h.)
        for model in self.dbI.get("models", limit=100, orderby=["insertdate", "ASC"]):
            if model["insertdate"] < int(getUTCnow() - 86400):
                self.logger.debug("delete %s", model["fileloc"])
                try:
                    os.unlink(model["fileloc"])
                except OSError as ex:
                    self.logger.debug(
                        f"Got OS Error removing this model {model['fileloc']}. Exc: {str(ex)}"
                    )
                self.dbI.delete("models", [["id", model["id"]]])

    def _getIPURIs(self, indict, iptype):
        """Get All IP URIs if any"""
        if 'hasNetworkAddress' in indict and f'{iptype}-address' in indict['hasNetworkAddress']:
            uri = indict['hasNetworkAddress'][f'{iptype}-address'].get('uri', '')
            ip = indict['hasNetworkAddress'][f'{iptype}-address'].get('value', '')
            if uri and ip:
                self.URIs['ips'].setdefault(normalizedip(ip), indict['hasNetworkAddress'][f'{iptype}-address'])

    def _getUniqueVlanURIs(self, qtype):
        """Get Unique URI for VLANs"""
        for _subnet, hostDict in self.activeDeltas.get('output', {}).get(qtype, {}).items():
            for host, portDict in hostDict.items():
                if not isinstance(portDict, dict):
                    continue
                for port, reqDict in portDict.items():
                    if 'uri' in reqDict and reqDict['uri'] and 'hasLabel' in reqDict and reqDict['hasLabel']:
                        vlan = reqDict['hasLabel'].get('value', 0)
                        if vlan:
                            self.URIs['vlans'].setdefault(host, {})
                            self.URIs['vlans'][host].setdefault(port, {})
                            self.URIs['vlans'][host][port][int(vlan)] = reqDict['uri']
                    self._getIPURIs(reqDict, 'ipv4')
                    self._getIPURIs(reqDict, 'ipv6')


    def checkForModelDiff(self, saveName):
        """Check if models are different."""
        currentModel, currentGraph = getCurrentModel(self, False)
        newGraph = Graph()
        newGraph.parse(saveName, format="turtle")
        return isomorphic(currentGraph, newGraph), currentModel

    def getModelSavePath(self):
        """Get Model Save Location."""
        now = datetime.now(timezone.utc)
        saveDir = f"{self.config.get(self.sitename, 'privatedir')}/LookUpService/"
        self.modelVersion = (
            f"{now.year}-{now.month}-{now.day}:{now.hour}:{now.minute}:{now.second}"
        )
        return f"{saveDir}/{self.modelVersion}.mrml"

    def saveModel(self, saveName):
        """Save Model."""
        with open(saveName, "w", encoding="utf-8") as fd:
            fd.write(self.newGraph.serialize(format="turtle"))

    def getVersionFromCurrentModel(self):
        """Get Current Version from Model."""
        _, currentGraph = getCurrentModel(self, False)
        out = self.police.queryGraph(
            currentGraph, URIRef(f"{self.prefixes['site']}:version")
        )
        if out:
            self.modelVersion = str(out[2])
        else:
            self.getModelSavePath()

    def _addTopTology(self):
        """Add Main Topology definition to Model."""
        out = {
            "sitename": self.sitename,
            "labelswapping": "false",
            "name": self.prefixes["site"],
            "version": self.modelVersion,
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
                self.logger.debug(
                    "Warning. Labelswapping parameter is not defined. Default is False."
                )
            out["nodeuri"] = self._addNode(**out)
            out["switchingserviceuri"] = self._addSwitchingService(**out)
            self._addLabelSwapping(**out)

    def _deviceUpdate(self):
        """Update all devices information."""
        self.logger.info("Forcefully update all device information")
        for siteName in self.config.get("general", "sites"):
            for dev in self.config.get(siteName, "switch"):
                fname = f"{self.config.get(siteName, 'privatedir')}/SwitchWorker/{dev}.update"
                self.logger.info(f"Set Update flag for device {dev} {siteName}, {fname}")
                success = False
                while not success:
                    try:
                        with open(fname, "w", encoding="utf-8") as fd:
                            # write timetsamp
                            fd.write(str(getUTCnow()))
                            success = True
                    except OSError as ex:
                        self.logger.error(f"Got OS Error writing {fname}. {ex}")
                        time.sleep(1)

    def startwork(self):
        """Main start."""
        self.logger.info("Started LookupService work")
        self.multiworker.startwork()
        self.activeDeltas = getActiveDeltas(self)
        self.URIs = {'vlans': {}, 'ips': {}} # Reset URIs
        self._getUniqueVlanURIs('vsw')
        self._getUniqueVlanURIs('kube')
        self.newGraph = Graph()
        # ==================================================================================
        # 1. Define Basic MRML Prefixes
        # ==================================================================================
        self.defineMRMLPrefixes()
        # 2. Get old model and version number
        # ==================================================================================
        self.getVersionFromCurrentModel()
        # ==================================================================================
        # 3. Define Topology Site
        # ==================================================================================
        self.defineTopology()
        self.hosts = {}
        # ==================================================================================
        # 4. Define Node inside yaml
        # ==================================================================================
        self.addNodeInfo()
        # ==================================================================================
        # 5. Define Switch information from Switch Lookup Plugin
        # ==================================================================================
        self.addSwitchInfo()
        # ==================================================================================
        # 6. Add all active running config
        # ==================================================================================
        self.addDeltaInfo()
        changesApplied = self.police.startwork(self.newGraph)
        if changesApplied:
            self.addDeltaInfo()

        saveName = self.getModelSavePath()
        self.saveModel(saveName)
        hashNum = generateHash(self.newGraph.serialize(format="turtle"))

        self.logger.info("Checking if new model is different from previous")
        modelsEqual, modelinDB = self.checkForModelDiff(saveName)
        lastKnownModel = {
            "uid": hashNum,
            "insertdate": getUTCnow(),
            "fileloc": saveName,
            "content": str(self.newGraph.serialize(format="turtle")),
        }
        if modelsEqual:
            if modelinDB[0]["insertdate"] < int(getUTCnow() - 3600):
                # Force to update model every hour, Even there is no update;
                self.logger.info("Forcefully update model in db as it is older than 1h")
                # Force version update
                self._updateVersion(
                    **{"version": self.modelVersion}
                )  # This will force to update Version to new value
                self.saveModel(saveName)
                self.dbI.insert("models", [lastKnownModel])
            else:
                self.logger.info("Models are equal.")
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
        else:
            self.logger.info("Models are different. Update DB")
            self._updateVersion(
                **{"version": self.modelVersion}
            )  # This will force to update Version to new value
            self.saveModel(saveName)
            self.dbI.insert("models", [lastKnownModel])
            # If models are different, we need to update all devices information
            self._deviceUpdate()

        # Start Provisioning Service and apply any config changes.
        self.provision.startwork()

        self.logger.debug(f"Last Known Model: {str(lastKnownModel['fileloc'])}")

    def startworkrenew(self, hosts=None):
        """Start work renew."""
        self.logger.info("Started LookupService work to renew network devices")
        for host in hosts:
            fname = f"{self.config.get(self.sitename, 'privatedir')}/SwitchWorker/{host}.update"
            if os.path.isfile(fname):
                self.renewsNeeded += 3
                try:
                    os.unlink(fname)
                except OSError as ex:
                    self.logger.error(f"Got OS Error removing {fname}. {ex}")
                    continue
        if self.renewsNeeded:
            self.switch.getinfoNew(hosts)
            self.renewsNeeded -= 1
        else:
            self.logger.info("No renew needed")
        self.logger.info("Finished LookupService work to renew network devices")

def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for siteName in config.get("general", "sites"):
        lserv = LookUpService(config, siteName)
        i = 20
        while i > 0:
            lserv.startwork()
            time.sleep(5)
            i -= 1


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="LookUpService")
    execute()
