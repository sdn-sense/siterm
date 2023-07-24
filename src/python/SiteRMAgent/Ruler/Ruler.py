#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/20
"""
import os
from SiteRMAgent.Ruler.Components.QOS import QOS
from SiteRMAgent.Ruler.Components.VInterfaces import VInterfaces
from SiteRMAgent.Ruler.Components.Routing import Routing
from SiteRMAgent.Ruler.OverlapLib import OverlapLib
from SiteRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from SiteRMLibs.MainUtilities import createDirs, getFullUrl, contentDB, getFileContentAsJson
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.CustomExceptions import FailedGetDataFromFE

COMPONENT = 'Ruler'


class Ruler(contentDB, QOS, OverlapLib):
    """Ruler class to create interfaces on the system."""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service='Ruler')
        self.workDir = self.config.get('general', 'private_dir') + "/SiteRM/RulerAgent/"
        createDirs(self.workDir)
        self.fullURL = getFullUrl(self.config, sitename)
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Ruler Start Work. Hostname: %s", self.hostname)
        # L2,L3 move it to Class Imports at top.
        self.layer2 = VInterfaces(self.config)
        self.layer3 = Routing(self.config)
        self.activeDeltas = {}
        self.activeFromFE = {}
        self.activeNew = {}
        self.activeNow = {}
        QOS.__init__(self)
        OverlapLib.__init__(self)


    def getData(self, url):
        """Get data from FE."""
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = f'Received a failure getting information from Site Frontend {str(out)}'
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
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

    def activeComparison(self, actKey, actCall):
        """Compare active vs file on node config"""
        self.logger.info(f'Active Comparison for {actKey}')
        if actKey == 'vsw':
            for key, vals in self.activeDeltas.get('output', {}).get(actKey, {}).items():
                if self.hostname in vals:
                    if not self._started(vals):
                        # This resource has not started yet. Continue.
                        continue
                    if key in self.activeFromFE.get('output', {}).get(actKey, {}).keys() and \
                    self.hostname in self.activeFromFE['output'][actKey][key].keys():
                        if vals[self.hostname] == self.activeFromFE['output'][actKey][key][self.hostname]:
                            continue
                        actCall.modify(vals[self.hostname], self.activeFromFE['output'][actKey][key][self.hostname])
                    else:
                        actCall.terminate(vals[self.hostname])
        if actKey == 'rst' and self.qosPolicy == 'hostlevel':
            for key, val in self.activeNow.items():
                if key not in self.activeNew:
                    actCall.terminate(val)
                    continue
                if val != self.activeNew[key]:
                    actCall.terminate(val)
            return

    def activeEnsure(self, actKey, actCall):
        """Ensure all active resources are enabled, configured"""
        self.logger.info(f'Active Ensure for {actKey}')
        if actKey == 'vsw':
            for _key, vals in self.activeFromFE.get('output', {}).get(actKey, {}).items():
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
        if actKey == 'rst' and self.qosPolicy == 'hostlevel':
            for _, val in self.activeNew.items():
                actCall.activate(val)
            return

    def startwork(self):
        """Start execution and get new requests from FE."""
        # if activeDeltas did not change - do not do any comparison
        # Comparison is needed to identify if any param has changed.
        # Otherwise - do precheck if all resources are active
        # And start QOS Ruler if it is configured so.
        activeDeltasFile = f"{self.workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)
        self.activeNow = self.getAllOverlaps(self.activeDeltas)

        self.activeFromFE = self.getActiveDeltas()
        self.activeNew = self.getAllOverlaps(self.activeFromFE)
        if self.activeDeltas != self.activeFromFE:
            self.dumpFileContentAsJson(activeDeltasFile, self.activeFromFE)

        import pprint
        pprint.pprint(self.activeNow)

        if not self.config.getboolean('agent', 'norules'):
            self.logger.info('Agent is configured to apply rules')
            for actKey, actCall in {'vsw': self.layer2, 'rst': self.layer3}.items():
                if self.activeDeltas != self.activeFromFE:
                    self.activeComparison(actKey, actCall)
                self.activeEnsure(actKey, actCall)
            # QoS Can be modified and depends only on Active
            self.activeNow = self.activeNew
            self.startqos()
        else:
            self.logger.info('Agent is not configured to apply rules')
        self.logger.info('Ended function start')

def execute(config=None):
    """Execute main script for SiteRM Agent output preparation."""
    if not config:
        config = getGitConfig()
    for sitename in config.get('general', 'sitename'):
        ruler = Ruler(config, sitename)
        ruler.startwork()

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='Ruler')
    execute()
