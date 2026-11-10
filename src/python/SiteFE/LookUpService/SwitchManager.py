#!/usr/bin/env python3
"""
SwitchManager keeps one SwitchWorker process running for every device owned by this replica.
Devices are split between SwitchManager replicas through database leases.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2026/11/09
"""

from SiteRMLibs.DBState import Sharder
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    externalCommand,
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getVal,
)


class SwitchManager:
    """Start, restart and stop per-device SwitchWorker processes for the devices this replica owns."""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="SwitchManager")
        self.dbI = getVal(getDBConn("SwitchManager", self), sitename=self.sitename)
        self.sharder = Sharder("SwitchManager", dbI=self.dbI, logger=self.logger)
        self.running = set()
        self.needRestart = False

    def refreshthread(self):
        """Reload configuration; running workers are restarted to pick it up."""
        self.config = getGitConfig()
        self.needRestart = True

    @staticmethod
    def _runCmd(action, device, foreground=False):
        """Run a SwitchWorker control command for one device."""
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

    def startwork(self):
        """Match running SwitchWorkers to the devices this replica owns."""
        devices = self.config.get(self.sitename, "switch")
        owned = self.sharder.myShare(sorted(devices))
        for dev in sorted(self.running - set(owned)):
            self.logger.info(f"Device {dev} is no longer owned by this replica (moved or removed). Stopping its SwitchWorker.")
            self.logger.info(f"Stop SwitchWorker for {dev} - {self._runCmd('stop', dev)}")
            self.running.discard(dev)
        for dev in owned:
            retOut = self._runCmd("status", dev)
            if retOut["exitCode"] != 0:
                action = "restart" if dev in self.running else "start"
                self.logger.info(f"SwitchWorker for {dev} is not running. Action: {action}")
                self.logger.info(f"{action} SwitchWorker for {dev} - {self._runCmd(action, dev, True)}")
            elif self.needRestart:
                self.logger.info(f"Restarting SwitchWorker for {dev} as it is instructed by config change")
                self.logger.info(f"Restart SwitchWorker for {dev} - {self._runCmd('restart', dev, True)}")
            self.running.add(dev)
        self.needRestart = False
        self.logger.info(f"SwitchManager owns {len(owned)}/{len(devices)} devices: {owned}")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="SwitchManager")
    gconfig = getGitConfig()
    manager = SwitchManager(gconfig, getSiteNameFromConfig(gconfig))
    manager.startwork()
