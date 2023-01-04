#!/usr/bin/env python3
"""DTN Main Agent code, which executes all Plugins and publishes values to FE.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
from __future__ import absolute_import
import sys
import importlib
from DTNRMAgent.RecurringActions import Plugins
from DTNRMLibs.MainUtilities import publishToSiteFE, createDirs
from DTNRMLibs.MainUtilities import getFullUrl
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import getGitConfig
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.CustomExceptions import PluginException

COMPONENT = 'RecurringAction'

class RecurringAction():
    """Provisioning service communicates with Local controllers and applies
    network changes."""
    def __init__(self, config, sitename):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='Agent')
        self.sitename = sitename

    def prepareJsonOut(self):
        """Executes all plugins and prepares json output to FE."""
        excMsg = ""
        outputDict = {'Summary': {}}
        tmpName = None
        if '__all__' in dir(Plugins):
            for callableF in Plugins.__all__:
                try:
                    method = importlib.import_module(f"DTNRMAgent.RecurringActions.Plugins.{callableF}")
                    if hasattr(method, 'NAME'):
                        tmpName = method.NAME
                    else:
                        tmpName = callableF
                    if method.NAME in list(outputDict.keys()):
                        msg = f'{method.NAME} name is already defined in output dictionary'
                        self.logger.error(msg)
                        raise KeyError(msg)
                    tmp = method.get(config=self.config)
                    if not isinstance(tmp, dict):
                        msg = f'Returned output from {method.Name} method is not a dictionary. Type: {type(tmp)}'
                        self.logger.error(msg)
                        raise ValueError(msg)
                    if tmp:  # Do not add empty stuff inside....
                        outputDict[method.NAME] = tmp
                    else:
                        continue
                    # Here wer check if there is any CUSTOM_FUNCTIONS
                    if hasattr(method, 'CUSTOM_FUNCTIONS'):
                        for funcOutName, funcCallable in list(method.CUSTOM_FUNCTIONS.items()):
                            outputDict['Summary'][method.NAME] = {}
                            tmpOut = funcCallable(self.config)
                            outputDict['Summary'][method.NAME][funcOutName] = tmpOut
                except Exception as ex:
                    excType, excValue = sys.exc_info()[:2]
                    outputDict[tmpName] = {"errorType": str(excType.__name__),
                                           "errorNo": -100,  # TODO Use exception definition from utilities
                                           "errMsg": str(excValue),
                                           "exception": str(ex)}
                    excMsg += f" {str(excType.__name__)}: {str(excValue)}"
                if 'errorType' in list(outputDict[tmpName].keys()):
                    self.logger.critical("%s received %s. Exception details: %s", tmpName,
                                    outputDict[tmpName]['errorType'], outputDict[tmpName])
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
        """Execute main script for DTN-RM Agent output preparation."""

        workDir = self.config.get('general', 'private_dir') + "/DTNRM/"
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
            self.logger.debug('Update Host result %s', outVals)
        if excMsg:
            raise PluginException(excMsg)


def execute(config):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    rec = RecurringAction(config, None)
    rec.startwork()


if __name__ == '__main__':
    CONFIG = getGitConfig()
    getLoggingObject(logType='StreamLogger', service='Agent')
    execute(CONFIG)
