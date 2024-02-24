#!/usr/bin/env python3
"""
Config Fetcher from Github.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/05/19
"""
import copy
import datetime
import os
import shutil

from SiteRMLibs.MainUtilities import getLoggingObject, getWebContentFromURL
from SiteRMLibs.GitConfig import GitConfig
from yaml import safe_load as yload


class ConfigFetcher():
    """Config Fetcher from Github."""
    def __init__(self, logger):
        self.logger = logger
        self.gitObj = GitConfig()
        self.config = None

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.gitObj = GitConfig()
        self.config = None

    def _fetchFile(self, name, url):
        output = {}
        datetimeNow = datetime.datetime.now() + datetime.timedelta(minutes=10)
        filename = f"/tmp/{datetimeNow.strftime('%Y-%m-%d-%H')}-{name}.yaml"
        if os.path.isfile(filename):
            self.logger.info(f'Config files are not yet needed for update. For {name} from {url}')
            with open(filename, 'r', encoding='utf-8') as fd:
                output = yload(fd.read())
        else:
            self.logger.info(f'Fetching new config file for {name} from {url}')
            datetimelasthour = datetimeNow - datetime.timedelta(hours=1)
            prevfilename = f"/tmp/{datetimelasthour.strftime('%Y-%m-%d-%H')}-{name}.yaml"
            print(f'Receiving new file from GIT for {name}')
            outyaml = getWebContentFromURL(url).text
            output = yload(outyaml)
            with open(filename, 'w', encoding='utf-8') as fd:
                fd.write(outyaml)
            try:
                shutil.copy(filename, f'/tmp/siterm-link-{name}.yaml')
                if os.path.isfile(prevfilename):
                    self.logger.info(f'Remove previous old cache file {prevfilename}')
                    os.remove(prevfilename)
            except IOError as ex:
                self.logger.info(f'Got IOError: {ex}')
        return output

    def fetchMapping(self):
        """Fetch mapping file from Github"""
        url = f"{self.gitObj.getFullGitUrl()}/mapping.yaml"
        return self._fetchFile('mapping', url)

    def fetchAgent(self):
        """Fetch Agent config file from Github"""
        if self.gitObj.config['MAPPING']['type'] == 'Agent':
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'main.yaml'])
            self._fetchFile('Agent-main', url)

    def fetchFE(self):
        """Fetch FE config file from Github"""
        if self.gitObj.config['MAPPING']['type'] == 'FE':
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'main.yaml'])
            self._fetchFile('FE-main', url)
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'auth.yaml'])
            self._fetchFile('FE-auth', url)

    def cleaner(self):
        """Clean files from /tmp/ directory"""
        datetimeNow = datetime.datetime.now() + datetime.timedelta(minutes=10)
        for name in ["mapping", "Agent-main", "FE-main", "FE-auth"]:
            filename = f"/tmp/{datetimeNow.strftime('%Y-%m-%d-%H')}-{name}.yaml"
            if os.path.isfile(filename):
                os.remove(filename)
            filename = f'/tmp/siterm-link-{name}.yaml'
            if os.path.isfile(filename):
                os.remove(filename)
        # Once removed - reget configs
        self.startwork()

    def startwork(self):
        """Start Config Fetcher Service."""
        self.gitObj.getLocalConfig()
        mapping = self.fetchMapping()
        self.gitObj.config['MAPPING'] = copy.deepcopy(mapping[self.gitObj.config['MD5']])
        self.fetchAgent()
        self.fetchFE()


if __name__ == "__main__":
    logObj = getLoggingObject(logType='StreamLogger', service='ConfigFetcher')
    cfgFecth = ConfigFetcher(logObj)
    cfgFecth.startwork()
