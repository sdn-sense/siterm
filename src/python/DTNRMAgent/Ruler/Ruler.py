#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/20
"""
from __future__ import absolute_import
import os
from DTNRMAgent.Ruler.Components.QOS import QOS
from DTNRMAgent.Ruler.Components.VInterfaces import VInterfaces
from DTNRMAgent.Ruler.Components.Routing import Routing
from DTNRMAgent.Ruler.OverlapLib import getAllOverlaps
from DTNRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from DTNRMLibs.MainUtilities import createDirs, getFullUrl, contentDB, getFileContentAsJson
from DTNRMLibs.MainUtilities import getGitConfig
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.CustomExceptions import FailedGetDataFromFE

COMPONENT = 'Ruler'


class Ruler(contentDB):
    """Ruler class to create interfaces on the system."""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service='Ruler')
        self.workDir = self.config.get('general', 'private_dir') + "/DTNRM/RulerAgent/"
        createDirs(self.workDir)
        self.fullURL = getFullUrl(self.config, sitename)
        self.sitename = sitename
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Ruler Start Work. Hostname: %s", self.hostname)
        self.layer2 = VInterfaces(self.config)
        self.layer3 = Routing(self.config)
        self.qos = QOS(self.config)


    def getData(self, url):
        """Get data from FE."""
        self.logger.info(f'Query: {self.fullURL}{url}')
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = f'Received a failure getting information from Site Frontend {str(out)}'
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
        self.logger.info('End function checkdeltas')
        return evaldict(out[0])

    def getActiveDeltas(self):
        """Get Delta information."""
        return self.getData("/sitefe/v1/activedeltas/")

    @staticmethod
    def _started(inConf):
        """Check if service started"""
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return True
        if 'start' in timings and getUTCnow() < timings['start']:
            return False
        return True

    @staticmethod
    def _ended(inConf):
        """Check if service ended"""
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return False
        if 'end' in timings and getUTCnow() > timings['end']:
            return True
        return False

    def activeComparison(self, activeFile, activeFE, actKey, actCall):
        """Compare active vs file on node config"""
        self.logger.info(f'Active Comparison for {actKey}')
        if actKey == 'vsw':
            for key, vals in activeFile.get('output', {}).get(actKey, {}).items():
                if self.hostname in vals:
                    if not self._started(vals):
                        # This resource has not started yet. Continue.
                        continue
                    if key in activeFE.get('output', {}).get(actKey, {}).keys():
                        if self.hostname in activeFE['output'][actKey][key].keys():
                            if vals[self.hostname] == activeFE['output'][actKey][key][self.hostname]:
                                continue
                            actCall.modify(vals[self.hostname], activeFE['output'][actKey][key][self.hostname])
                        else:
                            actCall.terminate(vals[self.hostname])
                    else:
                        actCall.terminate(vals[self.hostname])
        if actKey == 'rst':
            activeNew = getAllOverlaps(activeFE)
            activeNow = getAllOverlaps(activeFile)
            for key, val in getAllOverlaps(activeNow).items():
                if key not in activeNew:
                    actCall.terminate(val)
                    continue
                if val != activeNew[key]:
                    actCall.terminate(val)
            return

    def activeEnsure(self, activeConf, actKey, actCall):
        """Ensure all active resources are enabled, configured"""
        self.logger.info(f'Active Ensure for {actKey}')
        if actKey == 'vsw':
            for _key, vals in activeConf.get('output', {}).get(actKey, {}).items():
                if self.hostname in vals:
                    if self._started(vals) and not self._ended(vals):
                        # Means resource is active at given time.
                        actCall.activate(vals[self.hostname])
                    else:
                        # Termination. Here is a bit of an issue
                        # if FE is down or broken - and we have multiple deltas
                        # for same vlan, but different times.
                        # So we are not doing anything to terminate it and termination
                        # will happen at activeComparison - once delta is removed in FE.
                        continue
        if actKey == 'rst':
            for _, val in getAllOverlaps(activeConf).items():
                actCall.activate(val)
            return

    def startwork(self):
        """Start execution and get new requests from FE."""
        # if activeDeltas did not change - do not do any comparison
        # Comparison is needed to identify if any param has changed.
        # Otherwise - do precheck if all resources are active
        # And start QOS Ruler if it is configured so.
        activeDeltas = {}
        activeDeltasFile = f"{self.workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            activeDeltas = getFileContentAsJson(activeDeltasFile)
        activeFromFE = self.getActiveDeltas()
        updated = False
        if activeDeltas != activeFromFE:
            updated = True
            self.dumpFileContentAsJson(activeDeltasFile, activeFromFE)

        if not self.config.getboolean('agent', 'norules'):
            self.logger.info('Agent is configured to apply rules')
            for actKey, actCall in {'vsw': self.layer2, 'rst': self.layer3}.items():
                if updated:
                    self.activeComparison(activeDeltas, activeFromFE, actKey, actCall)
                self.activeEnsure(activeFromFE, actKey,actCall)
            self.qos.startqos()
        else:
            self.logger.info('Agent is not configured to apply rules')
        self.logger.info('Ended function start')

def execute(config=None):
    """Execute main script for DTN-RM Agent output preparation."""
    ruler = Ruler(config, None)
    ruler.startwork()

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='Ruler')
    execute()
