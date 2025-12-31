#!/usr/bin/env python3
"""
Config Fetcher from Github.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/05/19
"""
import os
import time

from SiteRMLibs.GitConfig import GitConfig
from SiteRMLibs.MainUtilities import getLoggingObject, getTempDir, getUTCNow


class ConfigFetcher:
    """Config Fetcher from Github."""

    def __init__(self, logger):
        self.logger = logger
        self.gitObj = GitConfig()
        self.config = None
        self.failedCounter = "/dev/shm/config-fetcher-counter"
        self.FetcherReadyFile = f"{getTempDir()}/config-fetcher-ready"
        self.lastFetchTime = None

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.gitObj = GitConfig()
        self.config = None
        self.failedCounter = "/dev/shm/config-fetcher-counter"
        self.FetcherReadyFile = f"{getTempDir()}/config-fetcher-ready"

    def _resetCounter(self):
        """Reset Counter that informs other services about failures"""
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
        with open(self.failedCounter, "w", encoding="utf-8") as fd:
            fd.write(str(currentval + 1))

    def _main(self):
        """Start Config Fetcher Service."""
        self.gitObj.getGitConfig()
        # Create tmp file that fetcher is done. /tmp/config-fetcher-ready
        if not os.path.isfile(self.FetcherReadyFile):
            with open(self.FetcherReadyFile, "w", encoding="utf-8") as fd:
                fd.write("Ready at: " + str(getUTCNow()))

    def startwork(self):
        """Start work of Config Fetcher."""
        count = self._getCounter()
        if count >= 10:
            self.logger.error("Got 10 consecutive failures. Will not try to fetch config anymore")
            self.logger.error("In Kubernetes this will kick the liveness/readiness to be not ready and restart container.")
            self.logger.error("In docker, this will require manual intervention to restart container.")
            time.sleep(60)
            return
        try:
            if self.lastFetchTime and (getUTCNow() - self.lastFetchTime)< 1800:
                timediff = getUTCNow() - self.lastFetchTime
                self.logger.info(f"Last fetch was less than 30 minutes ago. Skipping fetch. Time since last fetch: {timediff} seconds")
                return
            self._main()
            self._resetCounter()
            self.lastFetchTime = getUTCNow()
        except Exception as ex:
            self.logger.error(f"Got exception during config fetch: {ex}")
            self._incrementCounter()
            count = self._getCounter()
            if count >= 10:
                self.logger.error("Got 10 consecutive failures. This will kick the liveness/readiness to be not ready")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="ConfigFetcher")
    cfgFecth = ConfigFetcher(logObj)
    cfgFecth.startwork()
