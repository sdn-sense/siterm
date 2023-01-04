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
from rdflib import Graph
from rdflib import URIRef
from rdflib.compare import isomorphic
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getGitConfig
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import generateHash
from DTNRMLibs.MainUtilities import getCurrentModel
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import NoOptionError
from DTNRMLibs.CustomExceptions import NoSectionError
from DTNRMLibs.Backends.main import Switch
from SiteFE.LookUpService.modules.switchinfo import SwitchInfo
from SiteFE.LookUpService.modules.nodeinfo import NodeInfo
from SiteFE.LookUpService.modules.deltainfo import DeltaInfo
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper
from SiteFE.PolicyService.policyService import PolicyService

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
        self.renewSwitchConfig = False
        self.switch = Switch(config, sitename)
        self.prefixes = {}
        self.police = PolicyService(self.config, self.sitename)
        self.tmpout = {}
        self.modelVersion = ""
        workDir = self.config.get(self.sitename, 'privatedir') + "/LookUpService/"
        createDirs(workDir)

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

    def startwork(self):
        """Main start."""
        self.logger.info('Started LookupService work')
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
        # ==================================================================================
        # 6. Add all active running config
        # ==================================================================================
        self.addDeltaInfo()
        changesApplied = self.police.startwork(self.newGraph)
        if changesApplied:
            self.addDeltaInfo()

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
                self.renewSwitchConfig = True
            else:
                self.logger.info('Models are equal.')
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
        else:
            self.logger.info('Models are different. Update DB')
            self._updateVersion(**{'version': self.modelVersion})  # This will force to update Version to new value
            self.saveModel(saveName)
            self.dbI.insert('models', [lastKnownModel])
            # Also next run get new info from switch plugin
            self.renewSwitchConfig = True

        self.logger.debug(f"Last Known Model: {str(lastKnownModel['fileloc'])}")
        # Clean Up old models (older than 24h.)
        for model in self.dbI.get('models', limit=100, orderby=['insertdate', 'ASC']):
            if model['insertdate'] < int(getUTCnow() - 86400):
                self.logger.debug('delete %s', model['fileloc'])
                try:
                    os.unlink(model['fileloc'])
                except OSError as ex:
                    self.logger.debug(f'Got OS Error removing this model {model}. Exc: {str(ex)}')
                self.dbI.delete('models', [['id', model['id']]])


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for siteName in config.get('general', 'sites'):
        policer = LookUpService(config, siteName)
        policer.startwork()


if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='LookUpService')
    execute()
