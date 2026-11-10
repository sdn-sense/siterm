#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    DBWorker - Database worker thread for changing delta states.
Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2024/06/10
"""

from SiteFE.PolicyService.policyService import PolicyService
from SiteRMLibs.CustomExceptions import DELTA_STATE_TRANSITION_ERROR
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getVal,
)
from SiteRMLibs.Warnings import Warnings


class DBWorker(Warnings):
    """Config Fetcher from Github."""

    def __init__(self, config, sitename):
        super().__init__()
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
        for job in [
            ["committing", self.police.stateMachine.committing],
            ["committed", self.police.stateMachine.committed],
            ["activating", self.police.stateMachine.activating],
            ["activated", self.police.stateMachine.activated],
            ["remove", self.police.stateMachine.remove],
            ["removed", self.police.stateMachine.removed],
        ]:
            self.logger.debug("Start %s", job[0])
            errormsg = job[1](self.dbI)
            if errormsg:
                self.addWarning(errormsg, code=DELTA_STATE_TRANSITION_ERROR)

    def startwork(self):
        """Database thread worker - to change delta states"""
        # Run state actions (old models are removed by DBCleaner)
        self.stateActions()
        # Decrease counters
        self.checkAndRaiseWarnings()


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="DBWorker")
    gconfig = getGitConfig()
    siteName = getSiteNameFromConfig(gconfig)
    logObj.info(f"Starting DBWorker for {siteName}")
    dbworker = DBWorker(gconfig, siteName)
    dbworker.startwork()
    logObj.info("DBWorker finished all actions.")
