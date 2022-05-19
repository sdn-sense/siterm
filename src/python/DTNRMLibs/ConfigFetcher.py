#!/usr/bin/env python3
"""
Config Fetcher from Github.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/05/19
"""
import os
import copy
import shutil
import datetime
from yaml import safe_load as yload
from DTNRMLibs.MainUtilities import GitConfig
from DTNRMLibs.MainUtilities import getWebContentFromURL
from DTNRMLibs.MainUtilities import getLoggingObject

class ConfigFetcher():
    def __init__(self, logger):
        self.logger = logger
        self.gitObj = GitConfig()
        self.config = None

    def _fetchFile(self, name, url):
        output = {}
        datetimeNow = datetime.datetime.now() + datetime.timedelta(minutes=10)
        filename = '/tmp/%s-%s.yaml' % (datetimeNow.strftime('%Y-%m-%d-%H'), name)
        if os.path.isfile(filename):
            self.logger.info('Config files are not yet needed for update. For %s from %s' % (name, url))
            with open(filename, 'r', encoding='utf-8') as fd:
                output = yload(fd.read())
        else:
            self.logger.info('Fetching new config file for %s from %s' % (name, url))
            datetimelasthour = datetimeNow - datetime.timedelta(hours=1)
            prevfilename = '/tmp/%s-%s.yaml' % (datetimelasthour.strftime('%Y-%m-%d-%H'), name)
            print('Receiving new file from GIT for %s' % name)
            outyaml = getWebContentFromURL(url).text
            output = yload(outyaml)
            with open(filename, 'w', encoding='utf-8') as fd:
                fd.write(outyaml)
            try:
                shutil.copy(filename, '/tmp/dtnrm-link-%s.yaml' % name)
                if os.path.isfile(prevfilename):
                    self.logger.info('Remove previous old cache file %s' % prevfilename)
                    os.remove(prevfilename)
            except IOError as ex:
                self.logger.info('Got IOError: %s' % ex)
        return output

    def fetchMapping(self):
        url = "%s/mapping.yaml" % self.gitObj.getFullGitUrl()
        return self._fetchFile('mapping', url)

    def fetchAgent(self):
        if self.gitObj.config['MAPPING']['type'] == 'Agent':
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'main.yaml'])
            self._fetchFile('Agent-main', url)

    def fetchFE(self):
        if self.gitObj.config['MAPPING']['type'] == 'FE':
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'main.yaml'])
            self._fetchFile('FE-main', url)
            url = self.gitObj.getFullGitUrl([self.gitObj.config['MAPPING']['config'], 'auth.yaml'])
            self._fetchFile('FE-auth', url)

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
