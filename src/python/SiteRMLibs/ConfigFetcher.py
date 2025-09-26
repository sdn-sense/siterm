#!/usr/bin/env python3
"""
Config Fetcher from Github.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/05/19
"""
import copy
import datetime
import os
import shutil
import time

from SiteRMLibs.GitConfig import GitConfig
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import getLoggingObject
from yaml import safe_dump as ydump
from yaml import safe_load as yload


class ConfigFetcher:
    """Config Fetcher from Github."""

    def __init__(self, logger):
        self.logger = logger
        self.gitObj = GitConfig()
        self.config = None
        self.requestHandler = Requests(logger=self.logger)
        self.failedCounter = "/dev/shm/config-fetcher-counter"
        self.FetcherReadyFile = "/tmp/config-fetcher-ready"

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.gitObj = GitConfig()
        self.config = None
        self.requestHandler.close()
        self.requestHandler = Requests(logger=self.logger)
        self.failedCounter = "/dev/shm/config-fetcher-counter"
        self.FetcherReadyFile = "/tmp/config-fetcher-ready"

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

    def _newfetch(self):
        """In case it is a new fetch, remove ready file"""
        if os.path.isfile(self.FetcherReadyFile):
            os.remove(self.FetcherReadyFile)

    def _fetchFile(self, name, url, raiseEx=True):
        def retryPolicy(outObj, retries=3):
            if outObj[1] == -1:
                self.logger.debug(f"Got -1 (Timeout usually error. Will retry up to 3 times (5sec sleep): {outObj}")
                retries -= 1
            elif outObj[1] != 200:
                self.logger.debug(f"Got status code {outObj[1]} for {url}")
                retries -= 1
            else:
                return -1
            if retries == 0:
                self.logger.debug(f"Got too many retries. Will stop retrying to get config file: {outObj}")
            else:
                time.sleep(5)
            return retries

        output = {}
        datetimeNow = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
        filename = f"/tmp/{datetimeNow.strftime('%Y-%m-%d-%H')}-{name}.yaml"
        if os.path.isfile(filename):
            with open(filename, "r", encoding="utf-8") as fd:
                output = yload(fd.read())
        else:
            self._newfetch()
            self.logger.info(f"Fetching new config file for {name} from {url}")
            datetimelasthour = datetimeNow - datetime.timedelta(hours=1)
            prevfilename = f"/tmp/{datetimelasthour.strftime('%Y-%m-%d-%H')}-{name}.yaml"
            print(f"Receiving new file from GIT for {name}")
            retries = 3
            while retries > 0:
                self.requestHandler.setHost(url)
                outObj = self.requestHandler.makeHttpCall("GET", url, SiteRMHTTPCall=False)
                retries = retryPolicy(outObj, retries)
                if retries == 0:
                    output = {}
                elif retries == -1:
                    output = yload(outObj[0])
                else:
                    continue
                # If retries is 0 and raiseEx is True - raise exception
                if retries == 0 and raiseEx:
                    raise Exception(f"Unable to fetch config file {name} from {url}. Last output: {outObj}")
                with open(filename, "w", encoding="utf-8") as fd:
                    fd.write(ydump(output))
                try:
                    shutil.copy(filename, f"/tmp/siterm-link-{name}.yaml")
                    if os.path.isfile(prevfilename):
                        self.logger.info(f"Remove previous old cache file {prevfilename}")
                        os.remove(prevfilename)
                except IOError as ex:
                    self.logger.info(f"Got IOError: {ex}")
        return output

    def _fetcher(self, fetchlist):
        """Multiple file fetcher and url modifier"""
        def getMappings(itemname):
            """Get mappings for an URL"""
            if self.gitObj.config.get("MAPPING", {}).get("config", ""):
                return [self.gitObj.config["MAPPING"]["config"], itemname]
            return [itemname]
        output = {}
        url = None
        for item in fetchlist:
            failure = False
            mappings = getMappings(item[1])
            try:
                url = self.gitObj.getFullGitUrl(mappings)
                output[item[0]] = self._fetchFile(item[0], url)
            except Exception as ex:
                self.logger.error(f"Got exception during fetching {item[0]} from {url}: {ex}")
                failure = True
            if not failure:
                self.logger.info(f"Successfully fetched {item[0]} from {url}")
                continue
            # Here we retry with modified URL to include ref/heads
            try:
                url = self.gitObj.getFullGitUrl(mappings, refhead=True)
                output[item[0]] = self._fetchFile(item[0], url, raiseEx=False)
            except Exception as ex:
                self.logger.error(f"Got exception during fetching {item[0]} from {url}: {ex}")
                raise ex
        return output

    def fetchMapping(self):
        """Fetch mapping file from Github"""
        return self._fetcher([["mapping", "mapping.yaml"]]).get("mapping", {})

    def fetchAgent(self):
        """Fetch Agent config file from Github"""
        if self.gitObj.config["MAPPING"]["type"] == "Agent":
            self._fetcher([["Agent-main", "main.yaml"]])

    def fetchFE(self):
        """Fetch FE config file from Github"""
        if self.gitObj.config["MAPPING"]["type"] == "FE":
            self._fetcher([["FE-main", "main.yaml"], ["FE-auth", "auth.yaml"], ["FE-auth-re", "auth-re.yaml"]])

    def cleaner(self):
        """Clean files from /tmp/ directory"""
        datetimeNow = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=10)
        for name in ["mapping", "Agent-main", "FE-main", "FE-auth"]:
            filename = f"/tmp/{datetimeNow.strftime('%Y-%m-%d-%H')}-{name}.yaml"
            if os.path.isfile(filename):
                os.remove(filename)
            filename = f"/tmp/siterm-link-{name}.yaml"
            if os.path.isfile(filename):
                os.remove(filename)
        # Once removed - reget configs
        self.startwork()

    def _main(self):
        """Start Config Fetcher Service."""
        self.gitObj.getLocalConfig()
        mapping = self.fetchMapping()
        self.gitObj.config["MAPPING"] = copy.deepcopy(mapping[self.gitObj.config["MD5"]])
        self.fetchAgent()
        self.fetchFE()
        # Create tmp file that fetcher is done. /tmp/config-fetcher-ready
        if not os.path.isfile(self.FetcherReadyFile):
            with open(self.FetcherReadyFile, "w", encoding="utf-8") as fd:
                fd.write("Ready at: " + str(datetime.datetime.now()))

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
            self._main()
            self._resetCounter()
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
