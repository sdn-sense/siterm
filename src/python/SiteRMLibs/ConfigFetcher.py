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

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.gitObj = GitConfig()
        self.config = None
        self.requestHandler.close()
        self.requestHandler = Requests(logger=self.logger)

    def _newfetch(self):
        """In case it is a new fetch, remove ready file"""
        if os.path.isfile("/tmp/config-fetcher-ready"):
            os.remove("/tmp/config-fetcher-ready")

    def _fetchFile(self, name, url):
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

    def fetchMapping(self):
        """Fetch mapping file from Github"""
        url = f"{self.gitObj.getFullGitUrl()}/mapping.yaml"
        return self._fetchFile("mapping", url)

    def fetchAgent(self):
        """Fetch Agent config file from Github"""
        if self.gitObj.config["MAPPING"]["type"] == "Agent":
            url = self.gitObj.getFullGitUrl([self.gitObj.config["MAPPING"]["config"], "main.yaml"])
            self._fetchFile("Agent-main", url)

    def fetchFE(self):
        """Fetch FE config file from Github"""
        if self.gitObj.config["MAPPING"]["type"] == "FE":
            url = self.gitObj.getFullGitUrl([self.gitObj.config["MAPPING"]["config"], "main.yaml"])
            self._fetchFile("FE-main", url)
            url = self.gitObj.getFullGitUrl([self.gitObj.config["MAPPING"]["config"], "auth.yaml"])
            self._fetchFile("FE-auth", url)
            url = self.gitObj.getFullGitUrl([self.gitObj.config["MAPPING"]["config"], "auth-re.yaml"])
            self._fetchFile("FE-auth-re", url)

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

    def startwork(self):
        """Start Config Fetcher Service."""
        self.gitObj.getLocalConfig()
        mapping = self.fetchMapping()
        self.gitObj.config["MAPPING"] = copy.deepcopy(mapping[self.gitObj.config["MD5"]])
        self.fetchAgent()
        self.fetchFE()
        # Create tmp file that fetcher is done. /tmp/config-fetcher-ready
        if not os.path.isfile("/tmp/config-fetcher-ready"):
            with open("/tmp/config-fetcher-ready", "w", encoding="utf-8") as fd:
                fd.write("Ready at: " + str(datetime.datetime.now()))


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="ConfigFetcher")
    cfgFecth = ConfigFetcher(logObj)
    cfgFecth.startwork()
