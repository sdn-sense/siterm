#!/usr/bin/python
"""
DTN Main Agent code, which executes all Plugins and publishes values to FE

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
import sys
import pprint
import importlib
import Plugins
from DTNRMLibs.MainUtilities import publishToSiteFE, createDirs
from DTNRMLibs.MainUtilities import getDefaultConfigAgent, getFullUrl
from DTNRMLibs.MainUtilities import contentDB
from DTNRMLibs.MainUtilities import getUTCnow

COMPONENT = 'RecurringAction'

def prepareJsonOut(config, logger):
    """ Executes all plugins and prepares json output to FE """
    outputDict = {'Summary': {}}
    tmpName = None
    if '__all__' in dir(Plugins):
        for callableF in Plugins.__all__:
            try:
                method = importlib.import_module("DTNRMAgent.RecurringActions.Plugins.%s" % callableF)
                if hasattr(method, 'NAME'):
                    tmpName = method.NAME
                else:
                    tmpName = callableF
                if method.NAME in outputDict.keys():
                    msg = '%s name is already defined in output dictionary' % method.NAME
                    logger.error(msg)
                    raise KeyError(msg)
                tmp = method.get(config)
                if not isinstance(tmp, dict):
                    msg = 'Returned output from %s method is not a dictionary. Type: %s' % (method.Name, type(tmp))
                    logger.error(msg)
                    raise ValueError(msg)
                if tmp:  # Do not add empty stuff inside....
                    outputDict[method.NAME] = tmp
                else:
                    continue
                # Here wer check if there is any CUSTOM_FUNCTIONS
                if hasattr(method, 'CUSTOM_FUNCTIONS'):
                    for funcOutName, funcCallable in method.CUSTOM_FUNCTIONS.items():
                        outputDict['Summary'][method.NAME] = {}
                        tmpOut = funcCallable(config)
                        outputDict['Summary'][method.NAME][funcOutName] = tmpOut
            except Exception as ex:
                excType, excValue = sys.exc_info()[:2]
                outputDict[tmpName] = {"errorType": str(excType.__name__),
                                       "errorNo": -100,  # TODO Use exception definition from utilities
                                       "errMsg": str(excValue),
                                       "exception": str(ex)}
            if 'errorType' in outputDict[tmpName].keys():
                logger.critical("%s received %s. Exception details: %s", tmpName,
                                outputDict[tmpName]['errorType'], outputDict[tmpName])
    return outputDict


def appendConfig(config, dic):
    """Append to dic values from config and also dates"""
    dic['hostname'] = config.get('agent', 'hostname')
    dic['ip'] = config.get('general', 'ip')
    dic['insertTime'] = getUTCnow()
    dic['updateTime'] = getUTCnow()
    return dic


def startWork(config=None, logger=None):
    """ Execute main script for DTN-RM Agent output preparation """

    workDir = config.get('general', 'private_dir') + "/DTNRM/"
    createDirs(workDir)
    dic = prepareJsonOut(config, logger)
    fullUrl = getFullUrl(config)
    dic = appendConfig(config, dic)

    if config.getboolean('general', "debug"):
        pretty = pprint.PrettyPrinter(indent=4)
        logger.debug(pretty.pformat(dic))
    agent = contentDB(logger=logger, config=config)
    agent.dumpFileContentAsJson(workDir + "/latest-out.json", dic)

    logger.info('Will try to publish information to SiteFE')
    fullUrl += '/sitefe'
    outVals = publishToSiteFE(dic, fullUrl, '/json/frontend/updatehost')
    if outVals[2] != 'OK' or outVals[1] != 200:
        if outVals[3]:
            publishToSiteFE(dic, fullUrl, '/json/frontend/addhost')

def execute(config, logger):
    startWork(config, logger)

if __name__ == '__main__':
    CONFIG, LOGGER = getDefaultConfigAgent('agent')
    execute(CONFIG, LOGGER)
