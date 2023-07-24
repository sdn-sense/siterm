#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Model API Calls.

Copyright 2023 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
from SiteFE.PolicyService import stateMachine as stateM
from SiteRMLibs.MainUtilities import getAllFileContent
from SiteRMLibs.MainUtilities import getModTime
from SiteRMLibs.MainUtilities import httpdate
from SiteRMLibs.MainUtilities import encodebase64
from SiteRMLibs.MainUtilities import convertTSToDatetime
from SiteRMLibs.CustomExceptions import ModelNotFound


class ModelCalls():
    """Model Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.stateM = stateM.StateMachine(self.config)
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'models': {'allowedMethods': ['GET'],
                                'urlParams': [{"key": "current", "default": False, "type": bool},
                                              {"key": "summary", "default": True, "type": bool},
                                              {"key": "oldview", "default": False, "type": bool},
                                              {"key": "encode", "default": True, "type": bool},
                                              {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}]},
                     'modelsid': {'allowedMethods': ['GET'],
                                  'urlParams': [{"key": "encode", "default": False, "type": bool},
                                                {"key": "summary", "default": False, "type": bool}]}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("models", "/v1/models", action="models")
        self.routeMap.connect("modelsid", "/v1/models/:modelid", action="modelsid")

    def getmodel(self, environ, modelID=None, content=False, **kwargs):
        """Get all models."""
        if not modelID:
            return self.dbobj.get('models', orderby=['insertdate', 'DESC'])
        model = self.dbobj.get('models', limit=1, search=[['uid', modelID]])
        if not model:
            raise ModelNotFound(f"Model with {modelID} id was not found in the system")
        if content:
            return getAllFileContent(model[0]['fileloc'])
        return model[0]

    def models(self, environ, **kwargs):
        """
        Returns a collection of available model resources within the Resource Manager
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/models/ # Returns list of all models;
        """
        modTime = getModTime(kwargs['headers'])
        outmodels = self.getmodel(environ, None, False, **kwargs)
        if not outmodels:
            raise ModelNotFound('LastModel does not exist in dictionary. First time run? See documentation')
        outmodels = [outmodels] if isinstance(outmodels, dict) else outmodels
        current = {"id": outmodels[0]['uid'],
                   "creationTime": convertTSToDatetime(outmodels[0]['insertdate']),
                   "href": f"{environ['SCRIPT_URI']}/{outmodels[0]['uid']}"}
        if outmodels[0]['insertdate'] < modTime:
            self.httpresp.ret_304('application/json', kwargs["start_response"],
                                  [('Last-Modified', httpdate(outmodels[0]['insertdate']))])
            return []
        self.httpresp.ret_200('application/json', kwargs["start_response"],
                              [('Last-Modified', httpdate(outmodels[0]['insertdate']))])
        if kwargs['urlParams']['oldview']:
            return outmodels
        outM = {"models": []}
        if kwargs['urlParams']['current']:
            if not kwargs['urlParams']['summary']:
                current['model'] = encodebase64(self.getmodel(environ,
                                                                outmodels[0]['uid'],
                                                                content=True, **kwargs),
                                                kwargs['urlParams']['encode'])
            outM['models'].append(current)
            return [current]
        if not kwargs['urlParams']['current']:
            for model in outmodels:
                tmpDict = {"id": model['uid'],
                           "creationTime": convertTSToDatetime(model['insertdate']),
                           "href": f"{environ['SCRIPT_URI']}/{model['uid']}"}
                if not kwargs['urlParams']['summary']:
                    tmpDict['model'] = encodebase64(self.getmodel(environ,
                                                                    model['uid'],
                                                                    content=True, **kwargs),
                                                    kwargs['urlParams']['encode'])
                outM['models'].append(tmpDict)
            return outM['models']
        return []

    def modelsid(self, environ, **kwargs):
        """
        API Call for getting specific model and associated deltas;
        Method: GET
        Output: application/json
        """
        modTime = getModTime(kwargs['headers'])
        outmodels = self.getmodel(kwargs['modelid'], **kwargs)
        model = outmodels if isinstance(outmodels, dict) else outmodels[0]
        if modTime > model['insertdate']:
            self.httpresp.ret_304('application/json', kwargs["start_response"],
                                  [('Last-Modified', httpdate(model['insertdate']))])
            return []
        current = {"id": model['uid'],
                   "creationTime": convertTSToDatetime(model['insertdate']),
                   "href": f"{environ['SCRIPT_URI']}/{model['uid']}"}
        if not kwargs['urlParams']['summary']:
            current['model'] = encodebase64(self.getmodel(environ,
                                                            model['uid'],
                                                            content=True, **kwargs),
                                            kwargs['urlParams']['encode'])
        self.httpresp.ret_200('application/json', kwargs["start_response"],
                              [('Last-Modified', httpdate(model['insertdate']))])
        return current
