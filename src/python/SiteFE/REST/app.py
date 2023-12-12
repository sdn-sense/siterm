#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
WSGI Application main class.

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
import traceback

from routes import Mapper
from SiteFE.REST.Modules.DebugCalls import DebugCalls
from SiteFE.REST.Modules.DeltaCalls import DeltaCalls
from SiteFE.REST.Modules.FrontendCalls import FrontendCalls
from SiteFE.REST.Modules.HostCalls import HostCalls
from SiteFE.REST.Modules.ModelCalls import ModelCalls
from SiteFE.REST.Modules.PrometheusCalls import PrometheusCalls
from SiteFE.REST.Modules.TopoCalls import TopoCalls
from SiteRMLibs.CustomExceptions import (BadRequestError, DeltaNotFound,
                                         HTTPResponses, MethodNotSupported,
                                         ModelNotFound, NotAcceptedHeader,
                                         NotFoundError, NotSupportedArgument,
                                         OverlapException,
                                         TooManyArgumentalValues)
from SiteRMLibs.MainUtilities import (contentDB, getCustomOutMsg, getDBConn,
                                      getGitConfig, getHeaders, getUrlParams,
                                      getVal, jsondumps)
from SiteRMLibs.x509 import CertHandler


def isiterable(inVal):
    """Check if inVal is not str"""
    return not isinstance(inVal, str)


def returnDump(out):
    """Return output based on it's type."""
    if isinstance(out, (list, dict)):
        out = [jsondumps(out).encode("UTF-8")]
    elif not isiterable(out):
        out = [out.encode("UTF-8")]
    return out


class Frontend(
    CertHandler,
    FrontendCalls,
    PrometheusCalls,
    HostCalls,
    DebugCalls,
    DeltaCalls,
    ModelCalls,
    TopoCalls,
):
    """Main WSGI Frontend for accepting and authorizing calls to backend"""

    def __init__(self):
        self.config = getGitConfig()
        self.sites = ["MAIN"] + self.config["MAIN"]["general"]["sites"]
        self.httpresp = HTTPResponses()
        self.siteDB = contentDB()
        self.dbobj = getDBConn("REST-Frontend", self)
        self.dbI = None
        self.urlParams = {}
        self.routeMap = Mapper()
        CertHandler.__init__(self)
        FrontendCalls.__init__(self)
        PrometheusCalls.__init__(self)
        HostCalls.__init__(self)
        DebugCalls.__init__(self)
        DeltaCalls.__init__(self)
        ModelCalls.__init__(self)
        TopoCalls.__init__(self)

    def checkIfMethodAllowed(self, environ, actionName):
        """Check if Method (GET/PUT/POST/HEAD) is allowed"""
        if not self.urlParams.get(actionName, {}).get("allowedMethods", []):
            print(
                f"Warning. Undefined behavior. Allowed Methods not defined for {actionName}"
            )
            return
        if environ["REQUEST_METHOD"].upper() not in self.urlParams[actionName].get(
            "allowedMethods", []
        ):
            raise MethodNotSupported(
                f"Method {environ['REQUEST_METHOD'].upper()} not supported. Allowed methods {self.urlParams[actionName].get('allowedMethods', [])}"
            )
        return

    def responseHeaders(self, environ, **kwargs):
        """Response with 200 Header. OK"""
        self.httpresp.ret_200("application/json", kwargs["start_response"], None)

    def internallCall(self, environ, **kwargs):
        """Delta internal call which catches all exception."""
        returnDict = {}
        exception = ""
        try:
            routeMatch = self.routeMap.match(environ.get("PATH_INFO", "").rstrip("/"))
            if routeMatch and hasattr(self, routeMatch.get("action", "")):
                self.checkIfMethodAllowed(environ, routeMatch["action"])
                kwargs.update(routeMatch)
                if self.urlParams.get(routeMatch["action"], {}).get("urlParams", []):
                    kwargs.update(
                        {
                            "urlParams": getUrlParams(
                                environ,
                                self.urlParams[routeMatch["action"]]["urlParams"],
                            )
                        }
                    )
                kwargs.update({"headers": getHeaders(environ)})
                returnDict = getattr(self, routeMatch["action"])(environ, **kwargs)
            if not routeMatch:
                self.httpresp.ret_501(
                    "application/json", kwargs["start_response"], None
                )
                exception = (
                    f"No such API. {environ.get('PATH_INFO', '').rstrip('/')} call."
                )
                returnDict = getCustomOutMsg(errMsg=str(exception), errCode=501)
        except (ModelNotFound, DeltaNotFound) as ex:
            exception = f"Received Exception: {ex}"
            self.httpresp.ret_404("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=404)
        except (ValueError, IOError, NotFoundError) as ex:
            exception = (
                f"Received Exception: {ex}. Full traceback {traceback.print_exc()}"
            )
            self.httpresp.ret_500("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=500)
        except BadRequestError as ex:
            exception = f"Received BadRequestError: {ex}"
            self.httpresp.ret_400("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=400)
        except (NotSupportedArgument, TooManyArgumentalValues, OverlapException) as ex:
            exception = f"Send 400 error. More details: {jsondumps(getCustomOutMsg(errMsg=str(ex), errCode=400))}"
            self.httpresp.ret_400("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=400)
        except MethodNotSupported as ex:
            exception = f"Received BadRequestError: {ex}"
            self.httpresp.ret_405("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=405)
        except NotAcceptedHeader as ex:
            exception = f"Received BadRequestError: {ex}"
            self.httpresp.ret_406("application/json", kwargs["start_response"], None)
            returnDict = getCustomOutMsg(errMsg=str(ex), errCode=406)
        if exception:
            print(exception)
        return returnDump(returnDict)

    def mainCall(self, environ, start_response):
        """Main start.

        WSGI will always call this function, which will check if call is
        allowed.
        """
        # Certificate must be valid
        try:
            environ["CERTINFO"] = self.getCertInfo(environ)
            self.validateCertificate(environ)
        except Exception as ex:
            self.httpresp.ret_401("application/json", start_response, None)
            return [
                bytes(jsondumps(getCustomOutMsg(errMsg=str(ex), errCode=401)), "UTF-8")
            ]
        # Sitename must be configured on FE
        sitename = environ.get("REQUEST_URI", "").split("/")[1]
        if sitename not in self.sites:
            self.httpresp.ret_404("application/json", start_response, None)
            return [
                bytes(
                    jsondumps(
                        getCustomOutMsg(
                            errMsg=f"Sitename {sitename} is not configured. Contact Support.",
                            errCode=404,
                        )
                    ),
                    "UTF-8",
                )
            ]
        self.dbI = getVal(self.dbobj, **{"sitename": sitename})
        return self.internallCall(
            environ=environ, start_response=start_response, sitename=sitename
        )
