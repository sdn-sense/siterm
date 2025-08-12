#!/usr/bin/env python3
"""
Switch Worker for SiteRM for each individual switch.

Authors:
  Justas Balcas jbalcas (at) es.net

Date: 2022/05/19
"""
import os

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject, getSiteNameFromConfig


class SwitchWorker:
    """Config Fetcher from Github."""

    def __init__(self, config, sitename, device):
        self.config = config
        self.sitename = sitename
        self.device = device
        self.logger = getLoggingObject(config=self.config, service="SwitchWorker")
        self.switch = Switch(config, sitename)
        self.config = None
        self.renewsNeeded = 1

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def startwork(self):
        """Start Switch Worker Service."""
        self.logger.info(f"Starting Switch Worker for {self.device}")
        fname = f"{self.config.get(self.sitename, 'privatedir')}/SwitchWorker/{self.device}.update"
        if os.path.isfile(fname):
            self.logger.info(f"Renew is needed for {self.device}")
            self.renewsNeeded = 1
            try:
                os.unlink(fname)
            except OSError as ex:
                self.logger.error(f"Got OS Error removing {fname}. {ex}")
        if self.renewsNeeded:
            self.logger.info(f"Renew needed for {self.device}. Renewing {self.renewsNeeded} times.")
            self.switch.getinfoNew(self.device)
            self.renewsNeeded -= 1
        else:
            self.logger.info(f"No renew needed for {self.device}")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="SwitchWorker")
    gconfig = getGitConfig()
    siteName = getSiteNameFromConfig(gconfig)
    logObj.info(f"Starting Switch Worker for {siteName}")
    for dev in gconfig.get(siteName, "switch"):
        swWorker = SwitchWorker(gconfig, siteName, dev)
        swWorker.startwork()
        logObj.info(f"Finished Switch Worker for {dev}")
    logObj.info("Switch Worker finished all devices.")
