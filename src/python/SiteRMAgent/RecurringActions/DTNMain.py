#!/usr/bin/env python3
"""DTN Main Agent code, which executes all Plugins and publishes values to FE.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import sys
from SiteRMLibs.MainUtilities import publishToSiteFE, createDirs
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.CustomExceptions import PluginException
from SiteRMAgent.RecurringActions.Plugins.CertInfo import CertInfo
from SiteRMAgent.RecurringActions.Plugins.CPUInfo import CPUInfo
from SiteRMAgent.RecurringActions.Plugins.MemInfo import MemInfo
from SiteRMAgent.RecurringActions.Plugins.KubeInfo import KubeInfo
from SiteRMAgent.RecurringActions.Plugins.NetInfo import NetInfo
from SiteRMAgent.RecurringActions.Plugins.StorageInfo import StorageInfo

COMPONENT = 'RecurringAction'

class RecurringAction():
    """Provisioning service communicates with Local controllers and applies
    network changes."""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service='Agent')
        self.sitename = sitename
        self.classes = {}
        self._loadClasses()

    def _loadClasses(self):
        """Load all classes"""
        for name, plugin in {'CertInfo': CertInfo, 'CPUInfo': CPUInfo, 'MemInfo': MemInfo,
                             'KubeInfo': KubeInfo, 'NetInfo': NetInfo, 'StorageInfo': StorageInfo}.items():
            self.classes[name] = plugin(self.config, self.logger)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self._loadClasses()

    def prepareJsonOut(self):
        """Executes all plugins and prepares json output to FE."""
        excMsg = ""
        outputDict = {'Summary': {}}
        tmpName = None
        for tmpName, method in self.classes.items():
            try:
                tmp = method.get()
                if not isinstance(tmp, dict):
                    msg = f'Returned output from {tmpName} method is not a dictionary. Type: {type(tmp)}'
                    self.logger.error(msg)
                    raise ValueError(msg)
                outputDict[tmpName] = tmp
            except Exception as ex:
                excType, excValue = sys.exc_info()[:2]
                outputDict[tmpName] = {"errorType": str(excType.__name__),
                                        "errorNo": -6,
                                        "errMsg": str(excValue),
                                        "exception": str(ex)}
                excMsg += f" {str(excType.__name__)}: {str(excValue)}"
                self.logger.critical("%s received %s. Exception details: %s", tmpName,
                                     outputDict[tmpName]['errorType'], outputDict[tmpName])
        # Post processing of output (allows any class to modify output based on other Plugins output)
        for tmpName, method in self.classes.items():
            postMethod = getattr(method, 'postProcess', None)
            if postMethod:
                outputDict = postMethod(outputDict)
        return outputDict, excMsg

    def appendConfig(self, dic):
        """Append to dic values from config and also dates."""
        dic['hostname'] = self.config.get('agent', 'hostname')
        dic['ip'] = self.config.get('general', 'ip')
        dic['insertTime'] = getUTCnow()
        dic['updateTime'] = getUTCnow()
        dic['Summary'].setdefault('config', {})
        dic['Summary']['config'] = self.config.getraw('MAIN')
        return dic

    def startwork(self):
        """Execute main script for SiteRM Agent output preparation."""
        workDir = self.config.get('general', 'privatedir') + "/SiteRM/"
        createDirs(workDir)
        dic, excMsg = self.prepareJsonOut()
        fullUrl = getFullUrl(self.config, self.sitename)
        dic = self.appendConfig(dic)

        agent = contentDB()
        agent.dumpFileContentAsJson(workDir + "/latest-out.json", dic)

        self.logger.info('Will try to publish information to SiteFE')
        fullUrl += '/sitefe'
        outVals = publishToSiteFE(dic, fullUrl, '/json/frontend/updatehost')
        self.logger.debug('Update Host result %s', outVals)
        if outVals[2] != 'OK' or outVals[1] != 200 and outVals[3]:
            outVals = publishToSiteFE(dic, fullUrl, '/json/frontend/addhost')
            self.logger.debug('Insert Host result %s', outVals)
        if excMsg:
            raise PluginException(excMsg)


def execute(config):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for sitename in config.get('general', 'sitename'):
        rec = RecurringAction(config, sitename)
        rec.startwork()


if __name__ == '__main__':
    CONFIG = getGitConfig()
    getLoggingObject(logType='StreamLogger', service='Agent')
    execute(CONFIG)
