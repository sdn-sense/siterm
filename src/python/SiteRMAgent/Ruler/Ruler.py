#!/usr/bin/env python3
# pylint: disable=R0902, R0912
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/01/20
"""
import os

from SiteRMAgent.Ruler.Components.QOS import QOS
from SiteRMAgent.Ruler.Components.Routing import Routing
from SiteRMAgent.Ruler.Components.VInterfaces import VInterfaces
from SiteRMAgent.Ruler.OverlapLib import OverlapLib
from SiteRMLibs.CustomExceptions import FailedGetDataFromFE
from SiteRMLibs.ipaddr import checkOverlap
from SiteRMLibs.MainUtilities import (
    contentDB,
    createDirs,
    evaldict,
    callSiteFE,
    getFileContentAsJson,
    getFullUrl,
    getLoggingObject,
)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.BWService import BWService
from SiteRMLibs.timing import Timing

COMPONENT = "Ruler"


class Ruler(QOS, OverlapLib, BWService, Timing):
    """Ruler class to create interfaces on the system."""

    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service="Ruler")
        self.workDir = self.config.get("general", "privatedir") + "/SiteRM/RulerAgent/"
        createDirs(self.workDir)
        self.sitename = sitename
        self.siteDB = contentDB()
        self.fullURL = getFullUrl(self.config, self.sitename)
        self.hostname = self.config.get("agent", "hostname")
        self.logger.info("====== Ruler Start Work. Hostname: %s", self.hostname)
        self.activeDeltas = {}
        self.activeFromFE = {}
        self.activeNew = {}
        self.activeNow = {}
        QOS.__init__(self)
        OverlapLib.__init__(self)
        # L2,L3 move it to Class Imports at top.
        self.layer2 = VInterfaces(self.config, self.sitename)
        self.layer3 = Routing(self.config, self.sitename, self)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.fullURL = getFullUrl(self.config, self.sitename)
        self.hostname = self.config.get("agent", "hostname")
        self.layer2 = VInterfaces(self.config, self.sitename)
        self.layer3 = Routing(self.config, self.sitename, self)

    def getData(self, url):
        """Get data from FE."""
        out = callSiteFE({}, self.fullURL, url, "GET")
        if out[2] != "OK":
            msg = (
                f"Received a failure getting information from Site Frontend {str(out)}"
            )
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
        return evaldict(out[0])

    def getActiveDeltas(self):
        """Get Delta information."""
        failurefile = f"{self.workDir}/fefailure.json"
        data = {}
        try:
            data = self.getData(f"/api/{self.sitename}/frontend/activedeltas")
        except FailedGetDataFromFE as ex:
            self.siteDB.dumpFileContentAsJson(failurefile, {"exc": str(ex)})
            self.logger.critical("Failed to get data from FE: %s", str(ex))
            raise FailedGetDataFromFE from ex
        if os.path.isfile(failurefile):
            os.remove(failurefile)
        return data

    def checkIfOverlap(self, ip, intf, iptype):
        """Check if IPs overlap with what is set in configuration"""
        print(ip, intf, iptype)
        vlan = intf.split(".")
        if len(vlan) == 2:
            vlan = int(vlan[1])
        overlap = False
        for mintf in self.config["MAIN"]["agent"]["interfaces"]:
            if vlan in self.config["MAIN"][mintf].get("all_vlan_range_list", []):
                if f"{iptype}-address-pool" in self.config["MAIN"][mintf]:
                    overlap = checkOverlap(
                        self.config["MAIN"][mintf][f"{iptype}-address-pool"], ip, iptype
                    )
                    if overlap:
                        break
        return overlap

    def activeComparison(self, actKey, actCall):
        """Compare active vs file on node config"""
        self.logger.info(f"Active Comparison for {actKey}")
        if actKey in ["vsw", "kube"]:
            for key, vals in (
                self.activeDeltas.get("output", {}).get(actKey, {}).items()
            ):
                if not isinstance(vals, dict):
                    continue
                if self.hostname in vals:
                    if not self._started(vals):
                        # This resource has not started yet. Continue.
                        continue
                    if (
                        key
                        in self.activeFromFE.get("output", {}).get(actKey, {}).keys()
                        and self.hostname
                        in self.activeFromFE["output"][actKey][key].keys()
                    ):
                        if (
                            vals[self.hostname]
                            == self.activeFromFE["output"][actKey][key][self.hostname]
                        ):
                            continue
                        actCall.modify(
                            vals[self.hostname],
                            self.activeFromFE["output"][actKey][key][self.hostname],
                            key,
                        )
                    else:
                        actCall.terminate(vals[self.hostname], key)
        if actKey == "rst":
            for key, val in self.activeNow.items():
                for uuid, rvals in val.items():
                    if not self.activeNew.get(key, {}).get(uuid, {}):
                        actCall.terminate(rvals, uuid)
                        continue
                    if rvals != self.activeNew.get(key, {}).get(uuid, {}):
                        actCall.terminate(rvals, uuid)

    def activeEnsure(self, actKey, actCall):
        """Ensure all active resources are enabled, configured"""
        self.logger.info(f"Active Ensure for {actKey}")
        if actKey in ["vsw", "kube"]:
            for key, vals in (
                self.activeFromFE.get("output", {}).get(actKey, {}).items()
            ):
                if not isinstance(vals, dict):
                    continue
                if self.hostname in vals:
                    if self.checkIfStarted(vals):
                        # Means resource is active at given time.
                        actCall.activate(vals[self.hostname], key)
                    else:
                        # Termination. Here is a bit of an issue
                        # if FE is down or broken - and we have multiple deltas
                        # for same vlan, but different times.
                        # So we are not doing anything to terminate it and termination
                        # will happen at activeComparison - once delta is removed in FE.
                        continue
        if actKey == "rst":
            for key, val in self.activeNew.items():
                for uuid, rvals in val.items():
                    actCall.activate(rvals, uuid)

    def startwork(self):
        """Start execution and get new requests from FE."""
        # if activeDeltas did not change - do not do any comparison
        # Comparison is needed to identify if any param has changed.
        # Otherwise - do precheck if all resources are active
        # And start QOS Ruler if it is configured so.
        activeDeltasFile = f"{self.workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)
        self.activeNow = self.getAllOverlaps(self.activeDeltas)

        self.activeFromFE = self.getActiveDeltas()
        self.activeNew = self.getAllOverlaps(self.activeFromFE)
        if self.activeDeltas != self.activeFromFE:
            self.siteDB.dumpFileContentAsJson(activeDeltasFile, self.activeFromFE)

        if not self.config.getboolean("agent", "norules"):
            self.logger.info("Agent is configured to apply rules")
            for actKey, actCall in {
                "vsw": self.layer2,
                "rst": self.layer3,
                "kube": self.layer2,
            }.items():
                if self.activeDeltas != self.activeFromFE:
                    self.activeComparison(actKey, actCall)
                self.activeEnsure(actKey, actCall)
            # QoS Can be modified and depends only on Active
            self.activeNow = self.activeNew
            if not self.config.getboolean("agent", "noqos"):
                self.startqos()
            else:
                self.logger.info("QoS is not configured to be applied")
        else:
            self.logger.info("Agent is not configured to apply rules")
        self.logger.info("Ended function start")
        self.logger.info("Started IP Consistency Check")


def execute(config=None):
    """Execute main script for SiteRM Agent output preparation."""
    if not config:
        config = getGitConfig()
    for sitename in config.get("general", "sitename"):
        ruler = Ruler(config, sitename)
        ruler.startwork()


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="Ruler")
    execute()
