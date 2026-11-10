#!/usr/bin/env python3
"""
Config Fetcher from Github.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/05/19
"""

import os
import time
import traceback

from SiteRMLibs.DBState import dbConfigured, getStateDB, publishSiteConfig
from SiteRMLibs.GitConfig import GitConfig
from SiteRMLibs.MainUtilities import getLoggingObject, getTempDir, getUTCnow


class ConfigFetcher:
    """Config Fetcher from Github."""

    def __init__(self, logger):
        self.logger = logger
        self.gitObj = GitConfig()
        self.config = None
        self.failedCounter = os.getenv("CONFIG_FETCHER_COUNTER", "/dev/shm/config-fetcher-counter")
        self.FetcherReadyFile = f"{getTempDir()}/config-fetcher-ready"
        self.lastFetchTime = None

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.gitObj = GitConfig()
        self.config = None
        self.failedCounter = os.getenv("CONFIG_FETCHER_COUNTER", "/dev/shm/config-fetcher-counter")
        self.FetcherReadyFile = f"{getTempDir()}/config-fetcher-ready"
        # A refresh means reload: fetch again on the next cycle.
        self.lastFetchTime = None

    def _ensureCounterDir(self):
        """Ensure the failure counter directory exists."""
        counterDir = os.path.dirname(self.failedCounter)
        if counterDir:
            os.makedirs(counterDir, exist_ok=True)

    def _resetCounter(self):
        """Reset Counter that informs other services about failures"""
        self._ensureCounterDir()
        with open(self.failedCounter, "w", encoding="utf-8") as fd:
            fd.write("0")

    def _getCounter(self):
        """Get Counter of total previous fetch failures"""
        if os.path.isfile(self.failedCounter):
            with open(self.failedCounter, "r", encoding="utf-8") as fd:
                try:
                    return int(fd.read().strip())
                except ValueError:
                    return 0
        return 0

    def _incrementCounter(self):
        """Increment Counter that informs other services about failures"""
        self.logger.info("Incrementing failure counter")
        currentval = self._getCounter()
        self._ensureCounterDir()
        with open(self.failedCounter, "w", encoding="utf-8") as fd:
            fd.write(str(currentval + 1))

    def _main(self):
        """Start Config Fetcher Service."""
        if self.gitObj.manualConfigEnabled():
            self.logger.info("Manual configuration files are configured. Skipping Git config fetch.")
        else:
            self.gitObj.getGitRepo()
        self.gitObj.getGitConfig(fromdb=False)
        # Create tmp file that fetcher is done (read by agent probes). {tmpdir}/config-fetcher-ready
        if not os.path.isfile(self.FetcherReadyFile):
            with open(self.FetcherReadyFile, "w", encoding="utf-8") as fd:
                fd.write("Ready at: " + str(getUTCnow()))

    def _publish(self):
        """Publish git-based FE configuration to the database; other FE components load it from there."""
        if not self.gitObj.config.get("MAPPING") or self.gitObj.config["MAPPING"].get("type") != "FE":
            return
        if self.gitObj.manualConfigEnabled() or not dbConfigured():
            return
        try:
            if publishSiteConfig(getStateDB(), self.gitObj.publishableConfig()):
                self.logger.info("Published new site configuration to the database.")
        except Exception as ex:  # pylint: disable=broad-except
            # Database may still be starting; retried on the next cycle without counting as a fetch failure.
            self.logger.error(f"Unable to publish configuration to the database: {ex}")

    def startwork(self):
        """Start work of Config Fetcher."""
        self._startwork()
        self._publish()

    def _startwork(self):
        """Fetch configuration from git (at most every 30 minutes)."""
        count = self._getCounter()
        if count >= 10:
            self.logger.error("Got 10 consecutive failures. Will not try to fetch config anymore")
            self.logger.error("In Kubernetes this will kick the liveness/readiness to be not ready and restart container.")
            self.logger.error("In docker, this will require manual intervention to restart container.")
            time.sleep(60)
            return
        try:
            if self.lastFetchTime and (getUTCnow() - self.lastFetchTime) < 1800:
                timediff = getUTCnow() - self.lastFetchTime
                self.logger.info(f"Last fetch was less than 30 minutes ago. Skipping fetch. Time since last fetch: {timediff} seconds")
                return
            self._main()
            self._resetCounter()
            self.lastFetchTime = getUTCnow()
        except Exception as ex:
            self.logger.error(f"Got exception during config fetch: {ex}")
            self.logger.error(traceback.format_exc())
            self._incrementCounter()
            count = self._getCounter()
            if count >= 10:
                self.logger.error("Got 10 consecutive failures. This will kick the liveness/readiness to be not ready")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="ConfigFetcher")
    cfgFecth = ConfigFetcher(logObj)
    cfgFecth.startwork()
