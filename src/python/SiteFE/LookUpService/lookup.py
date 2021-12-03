#!/usr/bin/env python3
"""
    LookUpService gets all information and prepares MRML schema.


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from __future__ import division
import os
import datetime
import configparser
from rdflib import Graph
from rdflib.compare import isomorphic
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import createDirs
from DTNRMLibs.MainUtilities import generateHash
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.Backends.main import Switch
from SiteFE.LookUpService.modules.switchinfo import SwitchInfo
from SiteFE.LookUpService.modules.nodeinfo import NodeInfo
from SiteFE.LookUpService.modules.deltainfo import DeltaInfo
from SiteFE.LookUpService.modules.rdfhelper import RDFHelper


class LookUpService(SwitchInfo, NodeInfo, DeltaInfo, RDFHelper):
    """Lookup Service prepares MRML model about the system."""
    def __init__(self, config, logger, sitename):
        self.sitename = sitename
        self.logger = logger
        self.config = config
        self.dbI = getVal(getDBConn('LookUpService', self), **{'sitename': self.sitename})
        self.newGraph = None
        self.shared = 'notshared'
        self.hosts = {}
        self.renewSwitchConfig = False
        self.switch = Switch(config, logger, sitename)
        self.prefixes = {}
        workDir = self.config.get(self.sitename, 'privatedir') + "/LookUpService/"
        createDirs(workDir)

    def getCurrentModel(self):
        """Get Current Model from DB."""
        currentModel = self.dbI.get('models', orderby=['insertdate', 'DESC'], limit=1)
        currentGraph = Graph()
        if currentModel:
            try:
                currentGraph.parse(currentModel[0]['fileloc'], format='turtle')
            except IOError:
                currentGraph = Graph()
        return currentModel, currentGraph

    def checkForModelDiff(self, saveName):
        """Check if models are different."""
        currentModel, currentGraph = self.getCurrentModel()
        newGraph = Graph()
        newGraph.parse(saveName, format='turtle')
        return isomorphic(currentGraph, newGraph), currentModel

    def getModelSavePath(self):
        """Get Model Save Location."""
        now = datetime.datetime.now()
        saveDir = "%s/%s" % (self.config.get(self.sitename, "privatedir"), "LookUpService")
        createDirs(saveDir)
        return "%s/%s-%s-%s:%s:%s:%s.mrml" % (saveDir, now.year, now.month,
                                              now.day, now.hour, now.minute, now.second)

    def defineTopology(self):
        """Defined Topology and Main Services available."""
        # Add main Topology
        self._addSite()
        # Add Service for each Switch
        for switchName in self.config.get(self.sitename, 'switch').split(','):
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            labelswap = "false"
            try:
                labelswap = self.config.get(switchName, 'labelswapping')
            except configparser.NoOptionError:
                self.logger.debug('Labelswapping parameter is not defined. Default is False.')
            self._addLabelSwapping(switchName, None, vsw, labelswap)

    def startwork(self):
        """Main start."""
        self.logger.info('Started LookupService work')
        self.newGraph = Graph()
        # ==================================================================================
        # 1. Define Basic MRML Prefixes
        # ==================================================================================
        self.defineMRMLPrefixes()
        # ==================================================================================
        # 2. Define Topology Site
        # ==================================================================================
        self.defineTopology()
        self.hosts = {}
        # ==================================================================================
        # 3. Define Node inside yaml
        # ==================================================================================
        self.addNodeInfo()
        # ==================================================================================
        # 4. Define Switch information from Switch Lookup Plugin
        # ==================================================================================
        self.addSwitchInfo()

        saveName = self.getModelSavePath()
        with open(saveName, "w", encoding='utf-8') as fd:
            fd.write(self.newGraph.serialize(format='turtle'))
        hashNum = generateHash(self.newGraph.serialize(format='turtle'))

        # Append all deltas to the model
        # TODO. Append Deltas
        #self.appendDeltas(saveName)
        #if self.dbI.get('models', limit=1, search=[['uid', hashNum]]):
        #    raise Exception('hashNum %s is already in database...' % hashNum)

        self.logger.info('Checking if new model is different from previous')
        modelsEqual, modelinDB = self.checkForModelDiff(saveName)
        lastKnownModel = {'uid': hashNum, 'insertdate': getUTCnow(),
                          'fileloc': saveName, 'content': str(self.newGraph.serialize(format='turtle'))}
        if modelsEqual:
            if modelinDB[0]['insertdate'] < int(getUTCnow() - 3600):
                # Force to update model every hour, Even there is no update;
                self.logger.info('Forcefully update model in db as it is older than 1h')
                self.dbI.insert('models', [lastKnownModel])
                # Also next run get new info from switch plugin
                self.renewSwitchConfig = True
            else:
                self.logger.info('Models are equal.')
                lastKnownModel = modelinDB[0]
                os.unlink(saveName)
        else:
            self.logger.info('Models are different. Update DB')
            self.dbI.insert('models', [lastKnownModel])
            # Also next run get new info from switch plugin
            self.renewSwitchConfig = True

        self.logger.debug('Last Known Model: %s' % str(lastKnownModel['fileloc']))
        # Clean Up old models (older than 24h.)
        for model in self.dbI.get('models', limit=100, orderby=['insertdate', 'ASC']):
            if model['insertdate'] < int(getUTCnow() - 86400):
                self.logger.debug('delete %s', model['fileloc'])
                try:
                    os.unlink(model['fileloc'])
                except OSError as ex:
                    self.logger.debug('Got OS Error removing this model %s. Exc: %s' % (model, str(ex)))
                self.dbI.delete('models', [['id', model['id']]])


def execute(config=None, logger=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if not logger:
        component = 'LookUpService'
        logger = getLogger("%s/%s/" % (config.get('general', 'logDir'), component), config.get(component, 'logLevel'))
    for siteName in config.get('general', 'sites').split(','):
        policer = LookUpService(config, logger, siteName)
        policer.startwork()


if __name__ == '__main__':
    execute(logger=getStreamLogger())
