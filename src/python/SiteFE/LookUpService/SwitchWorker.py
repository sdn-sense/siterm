#!/usr/bin/env python3
"""
Switch Worker for SiteRM for each individual switch.

Authors:
  Justas Balcas jbalcas (at) es.net

Date: 2022/05/19
"""
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.GitConfig import getGitConfig
from SiteFE.LookUpService import lookup as LS

class SwitchWorker():
    """Config Fetcher from Github."""
    def __init__(self, config, sitename, device):
        self.config = config
        self.sitename = sitename
        self.device = device
        self.logger = getLoggingObject(config=self.config, service="SwitchWorker")
        self.lookup = LS.LookUpService(self.config, self.sitename)
        self.config = None

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.lookup = LS.LookUpService(self.config, self.sitename)

    def startwork(self):
        """Start Switch Worker Service."""
        self.logger.info(f"Starting Switch Worker for {self.device}")
        self.lookup.startworkrenew([self.device])

if __name__ == "__main__":
    logObj = getLoggingObject(logType='StreamLogger', service='SwitchWorker')
    config = getGitConfig()
    for siteName in config.get("general", "sites"):
        for dev in config.get(siteName, "switch"):
            swWorker = SwitchWorker(config, siteName, dev)
            swWorker.startwork()
