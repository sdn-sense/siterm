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
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
from SiteRMLibs.MainUtilities import getModTime
from SiteRMLibs.MainUtilities import httpdate
from SiteRMLibs.MainUtilities import encodebase64
from SiteRMLibs.MainUtilities import convertTSToDatetime
from SiteRMLibs.MainUtilities import firstRunFinished
from SiteRMLibs.MainUtilities import getAllFileContent
from SiteRMLibs.CustomExceptions import ModelNotFound
from SiteRMLibs.CustomExceptions import ServiceNotReady


class ModelCalls:
    """Model Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "models": {
                "allowedMethods": ["GET"],
                "urlParams": [
                    {"key": "current", "default": False, "type": bool},
                    {"key": "summary", "default": True, "type": bool},
                    {"key": "encode", "default": True, "type": bool},
                    {"key": "checkignore", "default": False, "type": bool},
                    {"key": "limit", "default": 10, "type": int},
                    {
                        "key": "model",
                        "default": "turtle",
                        "type": str,
                        "options": ["turtle", "json-ld", "ntriples"],
                    },
                ],
            },
            "modelsid": {
                "allowedMethods": ["GET"],
                "urlParams": [
                    {"key": "encode", "default": False, "type": bool},
                    {"key": "summary", "default": False, "type": bool},
                    {
                        "key": "model",
                        "default": "turtle",
                        "type": str,
                        "options": ["turtle", "json-ld", "ntriples"],
                    },
                ],
            },
        }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("models", "/v1/models", action="models")
        self.routeMap.connect("modelsid", "/v1/models/:modelid", action="modelsid")

    def getmodelcontent(self, dbentry, **kwargs):
        """Get model content based on db entry."""
        rettype = kwargs.get("urlParams", {}).get("model", "turtle")
        if rettype not in ["json-ld", "ntriples", "turtle"]:
            raise ModelNotFound(f"Model type {rettype} is not supported. Supported: json-ld, ntriples, turtle")
        return getAllFileContent(f'{dbentry["fileloc"]}.{rettype}')

    def getmodel(self, modelID=None, **kwargs):
        """Get all models."""
        if not modelID:
            models = self.dbI.get("models", limit=kwargs.get("urlParams", {}).get("limit", 10), orderby=["insertdate", "DESC"])
            if not models:
                raise ModelNotFound("No models in database. First time run?")
            return models
        model = self.dbI.get("models", limit=1, search=[["uid", modelID]])
        if not model:
            raise ModelNotFound(f"Model with {modelID} id was not found in the system")
        return model[0]

    def models(self, environ, **kwargs):
        """
        Returns a collection of available model resources within the Resource Manager
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/models/ # Returns list of all models;
        """
        # Check if checkignore is set, if so, check if first run is finished
        if not kwargs.get("urlParams", {}).get("checkignore", False):
            if not (firstRunFinished("LookUpService") or firstRunFinished("ProvisioningService")):
                raise ServiceNotReady(
                    "You cannot request model information yet, because LookUpService or ProvisioningService is not finished with first run (Server restart?). Retry later."
                )
        # Check if current is set, if so, it only asks for current model
        if kwargs["urlParams"]["current"]:
            kwargs["urlParams"]["limit"] = 1
            outmodels = self.getmodel(None, **kwargs)[0]
            if outmodels["insertdate"] < getModTime(kwargs["headers"]):
                self.httpresp.ret_304("application/json",
                                      kwargs["start_response"],
                                      [("Last-Modified", httpdate(outmodels["insertdate"]))])
                return []
            self.httpresp.ret_200("application/json",
                                  kwargs["start_response"],
                                  [("Last-Modified", httpdate(outmodels[0]["insertdate"]))])

            if not kwargs["urlParams"]["summary"]:
                return [{"id": outmodels["uid"],
                         "creationTime": convertTSToDatetime(outmodels["insertdate"]),
                         "href": f"{environ['APP_CALLBACK']}/{outmodels['uid']}",
                         "model": encodebase64(self.getmodelcontent(outmodels, **kwargs), kwargs["urlParams"]["encode"])
                       }]
            return [{"id": outmodels["uid"],
                     "creationTime": convertTSToDatetime(outmodels["insertdate"]),
                     "href": f"{environ['APP_CALLBACK']}/{outmodels['uid']}"}]
        # If current is not set, return all models (based on limit)
        outmodels = self.getmodel(None, **kwargs)
        models = []
        for model in outmodels:
            tmpDict = {"id": model["uid"],
                       "creationTime": convertTSToDatetime(model["insertdate"]),
                       "href": f"{environ['APP_CALLBACK']}/{model['uid']}"}
            if not kwargs["urlParams"]["summary"]:
                tmpDict["model"] = encodebase64(
                    self.getmodelcontent(model, **kwargs),
                    kwargs["urlParams"]["encode"])
            models.append(tmpDict)
        return models

    def modelsid(self, environ, **kwargs):
        """
        API Call for getting specific model and associated deltas;
        Method: GET
        Output: application/json
        """
        modTime = getModTime(kwargs["headers"])
        model = self.getmodel(kwargs["modelid"], content=False, **kwargs)
        if modTime > model["insertdate"]:
            self.httpresp.ret_304("application/json",
                                  kwargs["start_response"],
                                  [("Last-Modified", httpdate(model["insertdate"]))])
            return []
        current = {
            "id": model["uid"],
            "creationTime": convertTSToDatetime(model["insertdate"]),
            "href": f"{environ['APP_CALLBACK']}/{model['uid']}",
        }
        if not kwargs["urlParams"]["summary"]:
            current["model"] = encodebase64(self.getmodelcontent(model, **kwargs), kwargs["urlParams"]["encode"])
        self.httpresp.ret_200(
            "application/json",
            kwargs["start_response"],
            [("Last-Modified", httpdate(model["insertdate"]))],
        )
        return current
