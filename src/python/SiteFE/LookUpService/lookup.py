#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    LookUpService gets all information and prepares MRML schema.
Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from __future__ import division
import os
import datetime
import time
from rdflib import Graph
from rdflib import URIRef
from rdflib.compare import isomorphic
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import createDirs
from SiteRMLibs.MainUtilities import generateHash
from SiteRMLibs.MainUtilities import getCurrentModel
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import getActiveDeltas
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.CustomExceptions import NoSectionError
from SiteRMLibs.Backends.main import Switch
from SiteFE.LookUpService.modules.switchinfo import SwitchInfo
from SiteFE.LookUpService.modules.nodeinfo import NodeInfo
from SiteFE.LookUpService.modules.deltainfo import DeltaInfo
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper
from SiteFE.PolicyService.policyService import PolicyService
from SiteFE.ProvisioningService.provisioningService import ProvisioningService

class LookUpService(SwitchInfo, NodeInfo, DeltaInfo, RDFHelper):
    """Lookup Service prepares MRML model about the system."""
    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='LookUpService')
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        self.newGraph = None
        self.shared = 'notshared'
        self.hosts = {}
        self.switch = Switch(config, sitename)
        self.prefixes = {}
        self.police = PolicyService(self.config, self.sitename)
        self.provision = ProvisioningService(self.config, self.sitename)
        self.tmpout = {}
        self.modelVersion = ""
        self.renewSwitchConfig = False
        self.activeDeltas = {}
        workDir = self.config.get(self.sitename, 'privatedir') + "/LookUpService/"
        createDirs(workDir)

    def refreshthread(self, *args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        self.switch = Switch(self.config, self.sitename)
        self.police.refreshthread(*args)
        self.provision.refreshthread(*args)
        if not args[1]:
            self.__cleanup()

    def __cleanup(self):
        """Clean up process to remove old data"""
        # Clean Up old models (older than 24h.)
        for model in self.dbI.get('models', limit=100, orderby=['insertdate', 'ASC']):
            if model['insertdate'] < int(getUTCnow() - 86400):
                self.logger.debug('delete %s', model['fileloc'])
                try:
                    os.unlink(model['fileloc'])
                except OSError as ex:
                    self.logger.debug(f"Got OS Error removing this model {model['fileloc']}. Exc: {str(ex)}")
                self.dbI.delete('models', [['id', model['id']]])

    def checkForModelDiff(self, saveName):
        """Check if models are different."""
        currentModel, currentGraph = getCurrentModel(self, False)
        newGraph = Graph()
        newGraph.parse(saveName, format='turtle')
        return isomorphic(currentGraph, newGraph), currentModel

    def getModelSavePath(self):
        """Get Model Save Location."""
        now = datetime.datetime.now()
        saveDir = f"{self.config.get(self.sitename, 'privatedir')}/{'LookUpService'}"
        createDirs(saveDir)
        self.modelVersion = f"{now.year}-{now.month}-{now.day}:{now.hour}:{now.minute}:{now.second}"
        return f"{saveDir}/{self.modelVersion}.mrml"

    def saveModel(self, saveName):
        """Save Model."""
        with open(saveName, "w", encoding='utf-8') as fd:
            fd.write(self.newGraph.serialize(format='turtle'))

    def getVersionFromCurrentModel(self):
        """Get Current Version from Model."""
        _, currentGraph = getCurrentModel(self, False)
        out = self.police.queryGraph(currentGraph, URIRef(f"{self.prefixes['site']}:version"))
        if out:
            self.modelVersion = str(out[2])
        else:
            self.getModelSavePath()

    def _addTopTology(self):
        """Add Main Topology definition to Model."""
        out = {'sitename': self.sitename, 'labelswapping': "false",
               "name": self.prefixes['site'], 'version': self.modelVersion}
        if self.config.has_option('general', 'webdomain'):
            out['webdomain'] = self.config.get('general', 'webdomain')
        self._addSite(**out)
        return out

    def defineTopology(self):
        """Defined Topology and Main Services available."""
        # Add main Topology
        out = self._addTopTology()
        # Add Service for each Switch
        for switchName in self.config.get(self.sitename, 'switch'):
            out['hostname'] = switchName
            try:
                out['vsw'] = self.config.get(switchName, 'vsw')
            except (NoOptionError, NoSectionError) as ex:
                self.logger.debug('Warning: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            try:
                out['labelswapping'] = self.config.get(switchName, 'labelswapping')
            except NoOptionError:
                self.logger.debug('Warning. Labelswapping parameter is not defined. Default is False.')
            out['nodeuri'] = self._addNode(**out)
            out['switchingserviceuri'] = self._addSwitchingService(**out)
            self._addLabelSwapping(**out)

    def _setrenewFlag(self, newFlag):
        if not self.renewSwitchConfig:
            self.renewSwitchConfig = newFlag

    def startwork(self):
        """Main start."""
        self.logger.info('Started LookupService work')
        self.activeDeltas = getActiveDeltas(self)
        self.newGraph = Graph()
        # ==================================================================================
        # 1. Define Basic MRML Prefixes
        # ==================================================================================
        self.defineMRMLPrefixes()
        # 2. Get old model and version number
        # ==================================================================================
        self.getVersionFromCurrentModel()
        # ==================================================================================
        # 3. Define Topology Site
        # ==================================================================================
        self.defineTopology()
        self.hosts = {}
        # ==================================================================================
        # 4. Define Node inside yaml
        # ==================================================================================
        self.addNodeInfo()
        # ==================================================================================
        # 5. Define Switch information from Switch Lookup Plugin
        # ==================================================================================
        self.addSwitchInfo(self.renewSwitchConfig)
        self.renewSwitchConfig = False
        # ==================================================================================
        # 6. Add all active running config
        # ==================================================================================
        self.addDeltaInfo()
        changesApplied = self.police.startwork(self.newGraph)
        if changesApplied:
            self.addDeltaInfo()
            self._setrenewFlag(True)

        saveName = self.getModelSavePath()
        self.saveModel(saveName)
        hashNum = generateHash(self.newGraph.serialize(format='turtle'))

        self.logger.info('Checking if new model is different from previous')
        modelsEqual, modelinDB = self.checkForModelDiff(saveName)
        lastKnownModel = {'uid': hashNum, 'insertdate': getUTCnow(),
                          'fileloc': saveName, 'content': str(self.newGraph.serialize(format='turtle'))}
        if modelsEqual:
            if modelinDB[0]['insertdate'] < int(getUTCnow() - 3600):
                # Force to update model every hour, Even there is no update;
                self.logger.info('Forcefully update model in db as it is older than 1h')
                # Force version update
                self._updateVersion(**{'version': self.modelVersion})  # This will force to update Version to new value
                self.saveModel(saveName)
                self.dbI.insert('models', [lastKnownModel])
                # Also next run get new info from switch plugin
                self._setrenewFlag(True)
            else:
                self.logger.info('Models are equal.')
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
        else:
            self.logger.info('Models are different. Update DB')
            self._updateVersion(**{'version': self.modelVersion})  # This will force to update Version to new value
            self.saveModel(saveName)
            self.dbI.insert('models', [lastKnownModel])
            self._setrenewFlag(True)

        # Start Provisioning Service and apply any config changes.
        if self.provision.startwork():
            self._setrenewFlag(True)

        self.logger.debug(f"Last Known Model: {str(lastKnownModel['fileloc'])}")


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for siteName in config.get('general', 'sites'):
        lserv = LookUpService(config, siteName)
        i = 5
        while i > 0:
            lserv.startwork()
            time.sleep(5)
            i -= 1


if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='LookUpService')
    execute()
