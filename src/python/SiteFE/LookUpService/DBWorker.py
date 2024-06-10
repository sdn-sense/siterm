#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    DBWorker - Database worker thread for changing delta states.
Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2024/06/10
"""
import time
from SiteRMLibs.MainUtilities import (getDBConn, getLoggingObject, getVal)
from SiteRMLibs.GitConfig import getGitConfig
from SiteFE.PolicyService.policyService import PolicyService


class DBWorker():
    """Config Fetcher from Github."""
    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="DBWorker")
        self.dbI = getVal(getDBConn("DBWorker", self), **{"sitename": self.sitename})
        self.police = PolicyService(self.config, self.sitename)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()

    def startwork(self):
        """Database thread worker - to change delta states"""
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


if __name__ == "__main__":
    logObj = getLoggingObject(logType='StreamLogger', service='SwitchWorker')
    config = getGitConfig()
    for siteName in config.get("general", "sites"):
        dbworker = DBWorker(config, siteName)
        dbworker.startwork()
