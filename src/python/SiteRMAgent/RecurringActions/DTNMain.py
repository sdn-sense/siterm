#!/usr/bin/env python3
"""DTN Main Agent code, which executes all Plugins and publishes values to FE.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/01/29
"""
import copy
import socket
import sys

from deepdiff import DeepDiff
from SiteRMAgent import __version__
from SiteRMAgent.RecurringActions.Plugins.ArpInfo import ArpInfo
from SiteRMAgent.RecurringActions.Plugins.CertInfo import CertInfo
from SiteRMAgent.RecurringActions.Plugins.KubeInfo import KubeInfo
from SiteRMAgent.RecurringActions.Plugins.NetInfo import NetInfo
from SiteRMLibs.CustomExceptions import (
    NotFoundError,
    PluginException,
    PluginFatalException,
    ServiceWarning,
)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import (
    contentDB,
    createDirs,
    getFullUrl,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
)
from SiteRMLibs.MemDiskStats import MemDiskStats

COMPONENT = "RecurringAction"


class RecurringAction:
    """Provisioning service communicates with Local controllers and applies
    network changes."""

    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service="Agent")
        self.sitename = sitename
        self.classes = {}
        self._loadClasses()
        self.hostname = socket.getfqdn()
        self.agent = contentDB()
        fullUrl = getFullUrl(self.config)
        self.requestHandler = Requests(url=fullUrl, logger=self.logger)
        self.memDiskStats = MemDiskStats()
        self.lastout = {}

    def _loadClasses(self):
        """Load all classes"""
        for name, plugin in {
            "CertInfo": CertInfo,
            "KubeInfo": KubeInfo,
            "NetInfo": NetInfo,
            "ArpInfo": ArpInfo,
        }.items():
            self.classes[name] = plugin(self.config, self.logger)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self._loadClasses()
        fullUrl = getFullUrl(self.config)
        self.requestHandler.close()
        self.requestHandler = Requests(url=fullUrl, logger=self.logger)
        self.lastout = {}

    def reportMemDiskStats(self):
        """Report memory and disk statistics."""
        self.logger.info("Reporting memory and disk statistics")
        self.memDiskStats.reset()
        self.memDiskStats.updateStorageInfo()
        self.memDiskStats.updateMemStats(["sitermagent-update", "siterm-ruler", "Config-Fetcher"], 1)
        out = {"hostname": f"hostnamemem-{self.hostname}-Agent", "output": self.memDiskStats.getMemMonitor()}
        self.requestHandler.makeHttpCall("POST", f"/api/{self.sitename}/monitoring/stats", data=out, retries=1, raiseEx=False, useragent="Agent")
        out["hostname"] = f"hostnamedisk-{self.hostname}-Agent"
        out["output"] = self.memDiskStats.getStorageInfo()
        self.requestHandler.makeHttpCall("POST", f"/api/{self.sitename}/monitoring/stats", data=out, retries=1, raiseEx=False, useragent="Agent")
        self.logger.info("Memory and disk statistics reported successfully.")

    def prepareJsonOut(self):
        """Executes all plugins and prepares json output to FE."""
        excMsg = ""
        outputDict = {"Summary": {}}
        tmpName = None
        raiseError = False
        for tmpName, method in self.classes.items():
            try:
                tmp = method.get()
                if not isinstance(tmp, dict):
                    msg = f"Returned output from {tmpName} method is not a dictionary. Type: {type(tmp)}"
                    self.logger.error(msg)
                    raise ValueError(msg)
                outputDict[tmpName] = tmp
            except NotFoundError as ex:
                outputDict[tmpName] = {
                    "errorType": "NotFoundError",
                    "errorNo": -5,
                    "errMsg": str(ex),
                    "exception": str(ex),
                }
                excMsg += f" {str(ex)}"
                self.logger.error(
                    "%s received %s. Exception details: %s",
                    tmpName,
                    outputDict[tmpName]["errorType"],
                    outputDict[tmpName],
                )
                self.logger.error("This error is fatal. Will not continue to report back to FE.")
                raiseError = True
            except Exception as ex:
                excType, excValue = sys.exc_info()[:2]
                outputDict[tmpName] = {
                    "errorType": str(excType.__name__),
                    "errorNo": -6,
                    "errMsg": str(excValue),
                    "exception": str(ex),
                }
                excMsg += f" {str(excType.__name__)}: {str(excValue)}"
                self.logger.critical(
                    "%s received %s. Exception details: %s",
                    tmpName,
                    outputDict[tmpName]["errorType"],
                    outputDict[tmpName],
                )
        # Post processing of output (allows any class to modify output based on other Plugins output)
        for tmpName, method in self.classes.items():
            warnings = ""
            try:
                postMethod = getattr(method, "postProcess", None)
                if postMethod:
                    outputDict, warnings = postMethod(outputDict)
            except PluginFatalException as ex:
                self.logger.error(f"Plugin {tmpName} raised fatal exception. Will not continue to report back to FE.")
                self.logger.error(f"Exception details: {str(ex)}")
                excMsg += f" {str(ex)}"
                raiseError = True
            if warnings:
                self.logger.warning(f"Plugin {tmpName} raised warning. Will continue to report back to FE.")
                self.logger.warning(f"Exception details: {str(warnings)}")
                excMsg += f" {str(warnings)}"
                warnings = ""
        if raiseError:
            raise PluginException(excMsg)
        return outputDict, excMsg, raiseError

    def appendConfig(self, dic):
        """Append to dic values from config and also dates."""
        dic["hostname"] = self.config.get("agent", "hostname")
        dic["ip"] = self.config.get("general", "ip")
        dic["insertdate"] = getUTCnow()
        dic["updatedate"] = getUTCnow()
        dic["Summary"].setdefault("config", {})
        dic["Summary"]["config"] = self.config.getraw("MAIN")
        # Set default version info for metadata
        dic["Summary"]["config"].setdefault("general", {})
        dic["Summary"]["config"]["general"].setdefault("metadata", {})
        dic["Summary"]["config"]["general"]["metadata"].setdefault("version", __version__)
        return dic

    def comparediff(self, newdic):
        """Compare if 2 dictionaries are different."""
        tmpcopy = copy.deepcopy(newdic)
        tmpcopy.pop("updatedate", None)
        tmpcopy.pop("insertdate", None)
        if not self.lastout:
            self.lastout = tmpcopy
            return True
        diff = DeepDiff(self.lastout, newdic, ignore_order=True)
        if diff:
            self.logger.debug("Agent find differences in machine state:")
            self.logger.debug(diff.to_json(indent=2))
            self.lastout = tmpcopy
            return True
        return False

    def startwork(self):
        """Execute main script for SiteRM Agent output preparation."""
        workDir = self.config.get("general", "privatedir") + "/SiteRM/"
        createDirs(workDir)
        dic, excMsg, raiseError = self.prepareJsonOut()
        dic = self.appendConfig(dic)

        diffFromLast = self.comparediff(dic)
        self.logger.info("Output from Agent is different from last sent: %s", diffFromLast)
        if not diffFromLast:
            self.agent.dumpFileContentAsJson(workDir + "/latest-out.json", dic)
            # No need to send same data again, we just update timestamp.
            self.logger.info("Will Inform FE that Agent is alive.")
            tmpdic = {"hostname": dic["hostname"], "ip": dic["ip"], "updatedate": dic["updatedate"], "insertdate": dic["insertdate"], "nodatachange": True}
            outVals = self.requestHandler.makeHttpCall("PUT", f"/api/{self.sitename}/hosts", data=tmpdic, retries=1, raiseEx=False, useragent="Agent")
            if outVals[1] == 200:
                self.logger.info("FE informed that Agent is alive.")
            else:
                diffFromLast = True  # If we could not update timestamp, we will try to send full data again.
        if diffFromLast:
            self.logger.info("Will try to publish information to SiteFE")
            outVals = self.requestHandler.makeHttpCall("PUT", f"/api/{self.sitename}/hosts", data=dic, retries=1, raiseEx=False, useragent="Agent")
            self.logger.info("Update Host result %s", outVals)
            if outVals[1] != 200:
                outValsAdd = self.requestHandler.makeHttpCall("POST", f"/api/{self.sitename}/hosts", data=dic, retries=1, raiseEx=False, useragent="Agent")
                self.logger.info("Insert Host result %s", outValsAdd)
                if outValsAdd[1] != 200:
                    excMsg += " Could not publish to SiteFE Frontend."
                    excMsg += f"Update to FE: Error: {outVals[2]} HTTP Code: {outVals[1]}"
                    excMsg += f"Add tp FE: Error: {outValsAdd[2]} HTTP Code: {outValsAdd[1]}"
                    self.logger.error(excMsg)
        # Once we are done, we report memory and disk statistics
        self.reportMemDiskStats()
        if excMsg and raiseError:
            raise PluginException(excMsg)
        if excMsg:
            raise ServiceWarning(excMsg)


def execute(config):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    siteName = getSiteNameFromConfig(config)
    rec = RecurringAction(config, siteName)
    rec.startwork()


if __name__ == "__main__":
    CONFIG = getGitConfig()
    getLoggingObject(logType="StreamLogger", service="Agent")
    execute(CONFIG)
