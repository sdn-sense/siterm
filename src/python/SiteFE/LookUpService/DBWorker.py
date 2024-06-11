#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    DBWorker - Database worker thread for changing delta states.
Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2024/06/10
"""
import os
import time
from SiteRMLibs.MainUtilities import (getDBConn, getLoggingObject, getVal, getUTCnow)
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

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.police.refreshthread()

    def stateActions(self):
        """Change states of the delta states."""
        self.logger.debug("Start state actions and change states")
        for job in [["committing", self.police.stateMachine.committing],
                    ["committed", self.police.stateMachine.committed],
                    ["activating", self.police.stateMachine.activating],
                    ["activated", self.police.stateMachine.activated],
                    ["remove", self.police.stateMachine.remove],
                    ["removed", self.police.stateMachine.removed]]:
            self.logger.debug("Start %s", job[0])
            job[1](self.dbI)
            # Sleep 0.1 sec between diff checks
            time.sleep(0.5)

    def modelactions(self):
        """Clean up process to remove old data"""
        # Clean Up old models (older than 24h.)
        self.logger.debug("Start model actions and clean up old models")
        for model in self.dbI.get("models", limit=500, orderby=["insertdate", "ASC"]):
            if model["insertdate"] < int(getUTCnow() - 86400):
                self.logger.debug("delete %s", model["fileloc"])
                try:
                    os.unlink(model["fileloc"])
                except OSError as ex:
                    self.logger.debug(f"Got OS Error removing this model {model['fileloc']}. Exc: {str(ex)}")
                self.dbI.delete("models", [["id", model["id"]]])

    def startwork(self):
        """Database thread worker - to change delta states"""
        self.stateActions()
        self.modelactions()


if __name__ == "__main__":
    logObj = getLoggingObject(logType='StreamLogger', service='DBWorker')
    gconfig = getGitConfig()
    for siteName in gconfig.get("general", "sites"):
        dbworker = DBWorker(gconfig, siteName)
        dbworker.startwork()
