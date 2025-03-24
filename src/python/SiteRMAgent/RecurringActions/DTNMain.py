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
from SiteRMLibs.CustomExceptions import PluginException, NotFoundError, PluginFatalException, ServiceWarning
from SiteRMAgent.RecurringActions.Plugins.CertInfo import CertInfo
from SiteRMAgent.RecurringActions.Plugins.CPUInfo import CPUInfo
from SiteRMAgent.RecurringActions.Plugins.MemInfo import MemInfo
from SiteRMAgent.RecurringActions.Plugins.KubeInfo import KubeInfo
from SiteRMAgent.RecurringActions.Plugins.NetInfo import NetInfo
from SiteRMAgent.RecurringActions.Plugins.StorageInfo import StorageInfo
from SiteRMAgent.RecurringActions.Plugins.ArpInfo import ArpInfo

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
        self.agent = contentDB()

    def _loadClasses(self):
        """Load all classes"""
        for name, plugin in {'CertInfo': CertInfo, 'CPUInfo': CPUInfo, 'MemInfo': MemInfo,
                             'KubeInfo': KubeInfo, 'NetInfo': NetInfo, 'StorageInfo': StorageInfo,
                             'ArpInfo': ArpInfo}.items():
            self.classes[name] = plugin(self.config, self.logger)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self._loadClasses()

    def prepareJsonOut(self):
        """Executes all plugins and prepares json output to FE."""
        excMsg = ""
        outputDict = {'Summary': {}}
        tmpName = None
        raiseError = False
        for tmpName, method in self.classes.items():
            try:
                tmp = method.get()
                if not isinstance(tmp, dict):
                    msg = f'Returned output from {tmpName} method is not a dictionary. Type: {type(tmp)}'
                    self.logger.error(msg)
                    raise ValueError(msg)
                outputDict[tmpName] = tmp
            except NotFoundError as ex:
                outputDict[tmpName] = {"errorType": "NotFoundError",
                                       "errorNo": -5,
                                       "errMsg": str(ex),
                                       "exception": str(ex)}
                excMsg += f" {str(ex)}"
                self.logger.error("%s received %s. Exception details: %s", tmpName,
                                  outputDict[tmpName]['errorType'], outputDict[tmpName])
                self.logger.error("This error is fatal. Will not continue to report back to FE.")
                raiseError = True
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
            warnings = ""
            try:
                postMethod = getattr(method, 'postProcess', None)
                if postMethod:
                    outputDict, warnings = postMethod(outputDict)
            except PluginFatalException as ex:
                self.logger.error(f"Plugin {tmpName} raised fatal exception. Will not continue to report back to FE.")
                self.logger.error(f"Exception details: {str(ex)}")
                excMsg += f" {str(ex)}"
                raiseError = True
            if warnings:
                self.logger.warning(f"Plugin {tmpName} raised warning. Will continue to report back to FE.")
                self.logger.warning(f"Exception details: {str(warnings)}")
                excMsg += f" {str(warnings)}"
                warnings = ""
        if raiseError:
            raise PluginException(excMsg)
        return outputDict, excMsg, raiseError

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
        dic, excMsg, raiseError = self.prepareJsonOut()
        fullUrl = getFullUrl(self.config, self.sitename)
        dic = self.appendConfig(dic)

        self.agent.dumpFileContentAsJson(workDir + "/latest-out.json", dic)

        self.logger.info('Will try to publish information to SiteFE')
        fullUrl += '/sitefe'
        outVals = publishToSiteFE(dic, fullUrl, '/json/frontend/updatehost')
        self.logger.info('Update Host result %s', outVals)
        if outVals[2] != 'OK' or outVals[1] != 200 and outVals[3]:
            outValsAdd = publishToSiteFE(dic, fullUrl, '/json/frontend/addhost')
            self.logger.info('Insert Host result %s', outVals)
            if outValsAdd[2] != 'OK' or outValsAdd[1] != 200:
                excMsg += " Could not publish to SiteFE Frontend."
                excMsg += f"Update to FE: Error: {outVals[2]} HTTP Code: {outVals[1]}"
                excMsg += f"Add tp FE: Error: {outValsAdd[2]} HTTP Code: {outValsAdd[1]}"
                self.logger.error(excMsg)
        if excMsg and raiseError:
            raise PluginException(excMsg)
        if excMsg:
            raise ServiceWarning(excMsg)

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
