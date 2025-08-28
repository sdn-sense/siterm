#!/usr/bin/env python3
"""
    Debug Service

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2023/03/22
"""
import os
import traceback

from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import (
    contentDB,
    createDirs,
    evaldict,
    externalCommand,
    getFullUrl,
    getLoggingObject,
    getUTCnow,
)


class DebugService:
    """Debug Service Class"""

    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.sitename = sitename
        self.diragent = contentDB()
        self.logger = getLoggingObject(config=self.config, service="DebugService")
        self.workDir = self.config.get("general", "privatedir") + "/SiteRM/background/"
        createDirs(self.workDir)
        fullURL = getFullUrl(self.config)
        self.requestHandler = Requests(url=fullURL, logger=self.logger)
        self.activeProcesses = {}

    def publishToFE(self, inDic):
        """Publish debug runtime to FE"""
        # If dbI is defined, than we publish to DB directly.
        if hasattr(self, "dbI"):
            out = {"id": inDic["id"], "state": inDic["state"], "output": inDic["output"]}
            self.dbI.update("debugrequests", [out])
            return
        self.requestHandler.makeHttpCall("PUT", f"/api/{self.sitename}/debug/{inDic['id']}", data=inDic, useragent="DebugService")

    def resetActiveProcesses(self):
        """Reset active processes"""
        self.activeProcesses = {}

    def _startNewProcesses(self, item):
        """Check and return true/false to start new process."""
        if item["state"] != "new":
            return True
        # In case it is fdt-server, fdt-client, iperf-server, iperf-client, ethr-server, ethr-client
        # We can run only one instance per action per hostname.
        if item["action"] in ["fdt-server", "fdt-client", "iperf-server", "iperf-client", "ethr-server", "ethr-client"] and item["action"] in self.activeProcesses:
            self.logger.warning(f"Active process for {item['action']} already exists. Active IDs: {self.activeProcesses[item['action']]}.")
            return False
        return True

    def _logActiveProcesses(self, item):
        """Log active processes."""
        # "state": "active", "action": "fdt-client",
        if item["state"] != "active":
            return
        self.activeProcesses.setdefault(item["action"], []).append(item["id"])

    def backgroundProcessItemExists(self, item):
        """Check if background process item exists"""
        fname = self.workDir + f"/background-process-{item['id']}.json"
        if not os.path.isfile(fname):
            return False
        try:
            out = self.diragent.getFileContentAsJson(fname)
            if out.get("id", -1) == item["id"]:
                return True
            self.logger.warning(f"Background process item {item['id']} does not match with file: {fname}")
            self.logger.warning(f"File content: {out}")
            self.logger.warning(f"Item content: {item}")
        except Exception as ex:
            self.logger.warning(f"Error while checking background process item: {ex}")
        return False

    def checkBackgroundProcess(self, item):
        """Start Background work on specific item"""
        fname = self.workDir + f"/background-process-{item['id']}.json"
        if not os.path.isfile(fname):
            self.diragent.dumpFileContentAsJson(fname, item)
        else:
            itemfe = self.diragent.getFileContentAsJson(fname)
            # Check state of the item and if it is not the same, then we need to update it.
            if itemfe.get("state", "new") != item["state"]:
                itemfe["state"] = item["state"]
                self.diragent.dumpFileContentAsJson(fname, itemfe)
            item = itemfe
        try:
            self._logActiveProcesses(item)
            if not self._startNewProcesses(item):
                self.logger.info(f"Skipping start (already running this service) of new process for item {item['id']}")
                # Publish to FE that we skipped starting it.
                msg = f"Skipping start, because already running this action type (might be another process) for {item['id']}. Report timestamp: {getUTCnow()}"
                out = {
                    "id": item["id"],
                    "state": item["state"],
                    "output": {
                        "processOut": [msg],
                        "stdout": [],
                        "stderr": [msg],
                        "jsonout": {"exitCode": 0, "output": [msg]},
                        "exitCode": 0,
                    },
                    "updatedate": getUTCnow(),
                }
                return
            out, exitCode, newstate = self.run(item)
        except (ValueError, KeyError, OSError) as ex:
            out = {
                "processOut": [],
                "stdout": [],
                "stderr": [],
                "jsonout": {},
                "exitCode": 501,
            }
            out["stderr"].append(str(ex))
            out["stderr"].append(traceback.format_exc())
            exitCode = 501
            newstate = "failed"
        self.logger.debug(f"Finish check of process on debug action {item['id']}. ExitCode: {exitCode} NewState: {newstate}")
        if exitCode == -1 and newstate == "unknown":
            # We skip this as it is up to the process to decide what to do.
            return

        out = {
            "id": item["id"],
            "state": newstate,
            "output": out,
            "updatedate": getUTCnow(),
        }
        self.logger.debug(f"Updating state of debug: {out['id']} to {newstate}")
        self.logger.debug(f"Output of process: {out}")
        self.publishToFE(out)

    def _getOut(self, pid, logtype):
        """Get output from background process log file."""
        fname = self.workDir + f"/background-process-{pid}.{logtype}"
        tmpOut = self.diragent.getFileContentAsList(fname)
        out = [f"Output for {logtype} for {pid} does not exist", "=" * 80, ""]
        if tmpOut:
            out = [f"Output for {logtype} for {pid}", "=" * 80, ""]
        out += tmpOut
        return out

    def _getOutjson(self, pid, logtype):
        """Get output from background process log file."""
        fname = self.workDir + f"/background-process-{pid}.{logtype}"
        out = self.diragent.getFileContentAsJson(fname)
        out["output"] = evaldict(out.get("output", {}))
        return out

    def _runCmd(self, inputDict, action, foreground):
        """Start execution of new requests"""
        retOut = {
            "processOut": [],
            "stdout": [],
            "stderr": [],
            "jsonout": {},
            "exitCode": -1,
        }
        command = f"siterm-bgprocess --action {action} --noreporting --runnum {inputDict['id']}"
        if foreground:
            command += " --foreground"
        onetime = inputDict["requestdict"].get("onetime", False)
        if onetime:
            command += " --onetime"
        self.logger.debug(f"Running command: {command}")
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut["stdout"] += out.split("\n") + self._getOut(inputDict["id"], "stdout")
        retOut["stderr"] += err.split("\n") + self._getOut(inputDict["id"], "stderr")
        retOut["processOut"] += self._getOut(inputDict["id"], "process")
        retOut["jsonout"] = self._getOutjson(inputDict["id"], "jsonout")
        retOut["exitCode"] = cmdOut.returncode
        return retOut

    def _clean(self, inputDict):
        """Clean up after process is finished"""
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.json")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stdout")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.stderr")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.process")
        self.diragent.removeFile(self.workDir + f"/background-process-{inputDict['id']}.jsonout")

    def run(self, inputDict):
        """Run a specific debug service in a separate thread"""
        inputDict["requestdict"] = evaldict(inputDict["requestdict"])
        self.logger.debug(f"Check background process: {inputDict}")
        # Check Status first
        retOut = self._runCmd(inputDict, "status", False)

        # If this first start, then start it.
        if retOut["exitCode"] != 0 and inputDict["state"] == "new":
            self.logger.info(f"Starting background process: {inputDict['id']}")
            retOut = self._runCmd(inputDict, "start", True)
            retOut["processOut"].append(f"Starting background process: {inputDict['id']}")
            return retOut, 0, "active"

        # If it is active, and process is active, then get output from it.
        if retOut["exitCode"] == 0 and inputDict["state"] == "active":
            self.logger.info(f"Checking background process: {inputDict['id']}")
            retOut["processOut"].append(f"Checking background process: {inputDict['id']}")
            return retOut, 0, "active"

        # If it is active, but process exited, then it failed.
        if retOut["exitCode"] != 0 and inputDict["state"] == "active":
            onetime = inputDict["requestdict"].get("onetime", False)
            # Check that it should run only once.
            if onetime:
                self.logger.info(f"One time run and process finished: {inputDict['id']}")
                retOut["processOut"].append(f"One time run process finished for: {inputDict['id']}")
                if retOut["jsonout"].get("exitCode", -1) == 0:
                    self._clean(inputDict)
                    return retOut, 2, "finished"
                return retOut, 1, "failed"
            # Check if we should restart it based on runtime parameters.
            utcNow = int(getUTCnow())
            # Check that it should run until specific time.
            rununtil = int(inputDict["requestdict"].get("runtime", utcNow))
            if rununtil > utcNow:
                self.logger.info(f"Restarting background process: {inputDict['id']}")
                retOut = self._runCmd(inputDict, "restart", True)
                retOut["processOut"].append(f"Restarting background process: {inputDict['id']}")
                return retOut, 0, "active"
            self.logger.info(f"Force stoping background process (time finished): {inputDict['id']}")
            retOut = self._runCmd(inputDict, "stop", True)
            retOut["processOut"].append(f"Force stoping background process: {inputDict['id']}")
            if retOut["jsonout"].get("exitCode", -1) == 0:
                self._clean(inputDict)
                return retOut, 2, "finished"
            # In case failed, we keep logs remaining. Not best practice, but we keep it for now.
            return retOut, 1, "failed"

        self.logger.warning(f"Unknown state for background process: {inputDict['id']}")
        self.logger.warning(f"Return Out of Process: {retOut}")
        return retOut, -1, "unknown"
