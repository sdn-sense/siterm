#!/usr/bin/env python3
"""
Switch Worker for SiteRM for each individual switch.

Authors:
  Justas Balcas jbalcas (at) es.net

Date: 2022/05/19
"""

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.DBState import consumeDeviceUpdate
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject, getSiteNameFromConfig, getUTCnow


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
        self.lastRenew = 0

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def startwork(self):
        """Start Switch Worker Service."""
        self.logger.info(f"Starting Switch Worker for {self.device}")
        if consumeDeviceUpdate(self.switch.dbI, self.device):
            self.logger.info(f"Renew is needed for {self.device}")
            self.renewsNeeded = 1
        # Nothing else re-polls an idle device, so an unreachable one would otherwise go unnoticed.
        renewInterval = self.config.get("daemoncontrols", "SwitchWorker", {}).get("renewinterval", 600)
        if not self.renewsNeeded and getUTCnow() - self.lastRenew >= renewInterval:
            self.logger.info(f"Last successful renew for {self.device} is older than {renewInterval}s. Forcing renew.")
            self.renewsNeeded = 1
        if self.renewsNeeded:
            self.logger.info(f"Renew needed for {self.device}. Renewing {self.renewsNeeded} times.")
            self.switch.getinfoNew(self.device)
            self.renewsNeeded -= 1
            self.lastRenew = getUTCnow()
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
