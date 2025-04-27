#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Delta API Calls

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
import os
import time
from SiteFE.PolicyService import stateMachine as stateM
from SiteRMLibs.CustomExceptions import (BadRequestError, DeltaNotFound,
                                         WrongDeltaStatusTransition)
from SiteRMLibs.MainUtilities import (convertTSToDatetime, decodebase64,
                                      encodebase64, evaldict, getModTime,
                                      getUTCnow, httpdate, jsondumps)
from SiteRMLibs.RESTInteractions import (get_json_post_form, get_post_form,
                                         is_application_json, is_post_request)


class DeltaCalls:
    """Delta Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.stateM = stateM.StateMachine(self.config)
        self.__defineRoutes()
        self.__urlParams()
        self.policerdirs = {}
        for sitename in self.sites:
            if sitename != "MAIN":
                self.policerdirs.setdefault(sitename, {'new': {}, 'finished': {}})
                self.policerdirs[sitename]['new'] = os.path.join(self.config.get(sitename, "privatedir"), "PolicyService", "httpnew")
                self.policerdirs[sitename]['finished'] = os.path.join(self.config.get(sitename, "privatedir"), "PolicyService", "httpfinished")

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "deltas": {
                "allowedMethods": ["GET", "POST"],
                "urlParams": [
                    {"key": "summary", "default": True, "type": bool},
                    {"key": "oldview", "default": False, "type": bool},
                    {"key": "encode", "default": True, "type": bool},
                    {
                        "key": "model",
                        "default": "turtle",
                        "type": str,
                        "options": ["turtle"],
                    },
                ],
            },
            "deltasid": {
                "allowedMethods": ["GET"],
                "urlParams": [
                    {
                        "key": "model",
                        "default": "turtle",
                        "type": str,
                        "options": ["turtle"],
                    },
                    {"key": "encode", "default": True, "type": bool},
                    {"key": "oldview", "default": False, "type": bool},
                    {"key": "summary", "default": False, "type": bool},
                ],
            },
            "deltasaction": {"allowedMethods": ["GET", "PUT"]},
            "activedeltas": {"allowedMethods": ["GET"]},
            "deltastates": {"allowedMethods": ["GET"]},
            "deltatimestates": {"allowedMethods": ["POST"]},
            "deltaforceapply": {"allowedMethods": ["POST"]},
        }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("deltas", "/v1/deltas", action="deltas")
        self.routeMap.connect("deltasid", "/v1/deltas/:deltaid", action="deltasid")
        self.routeMap.connect("deltasaction", "/v1/deltas/:deltaid/actions/:newaction", action="deltasaction")
        self.routeMap.connect("activedeltas", "/v1/activedeltas", action="activedeltas")
        self.routeMap.connect("deltastates", "/v1/deltastates/:deltaid", action="deltastates")
        self.routeMap.connect("deltatimestates", "/v1/deltatimestates", action="deltatimestates")
        self.routeMap.connect("deltaforceapply", "/v1/deltaforceapply", action="deltaforceapply")

    def _logDeltaUserAction(self, deltaInfo, userAction, otherInfo, environ):
        """Log Delta User Action"""
        username = environ.get("USERINFO", {}).get("username", "UNKNOWN") + "-"
        username += environ.get("CERTINFO", {}).get("fullDN", "UNKNOWN") + "-"
        username += environ.get('REMOTE_ADDR', 'UNKNOWN')
        otherInfo = str({'otherInfo': otherInfo, 'deltaInfo': deltaInfo})
        print([{"username": username, "insertdate": getUTCnow(), "deltaid": deltaInfo.get("uuid", "UNKNOWN"), "useraction": userAction, "otherinfo": otherInfo}])
        # TODO: Review user tracking as it gets many updates from agenst to do set state.
        # Which is correct as agents keep informing FE that resource is activated and did not drift anyhow.
        # This can easily explode and grow database quickly. For now we save it in the log, and not inside database;
        #self.dbI.insert("deltasusertracking", [{"username": username, "insertdate": getUTCnow(), "deltaid": deltaInfo.get("uuid", "UNKNOWN"), "useraction": userAction, "otherinfo": otherInfo}])

    @staticmethod
    def __intGetPostData(environ, **_kwargs):
        """Parse POST Data"""
        out = {}
        postRequest = False
        if environ["REQUEST_METHOD"].upper() == "POST":
            postRequest = is_post_request(environ)
        if not postRequest:
            if is_application_json(environ):
                out = get_json_post_form(environ)
            else:
                raise BadRequestError(
                    "You did POST method, but provided CONTENT_TYPE is not correct"
                )
        if not out:
            out = get_post_form(environ)
        return out

    def __addNewDeltaINT(self, uploadContent, environ, **kwargs):
        """Add new delta."""
        hashNum = uploadContent["id"]
        delta = self.dbI.get("deltas", search=[["uid", hashNum]], limit=1)
        if delta:
            # If delta is not in a final state, we delete it from db, and will add new one.
            if delta[0]["state"] not in ["activated", "failed", "removed", "accepted", "accepting"]:
                self.dbI.delete("deltas", [["uid", delta[0]["uid"]]])
        self.getmodel(environ, uploadContent["modelId"], None, **kwargs)
        outContent = {
            "ID": hashNum,
            "InsertTime": getUTCnow(),
            "UpdateTime": getUTCnow(),
            "Content": uploadContent,
            "State": "accepting",
            "modelId": uploadContent["modelId"],
        }
        fname = os.path.join(self.policerdirs[kwargs["sitename"]]['new'], f"{hashNum}.json")
        self.siteDB.saveContent(fname, outContent)
        finishedName = os.path.join(self.policerdirs[kwargs["sitename"]]['finished'], f"{hashNum}.json")
        out = {}
        # Loop for max 110seconds and check if we have file in finished directory.
        timer = 110
        while timer > 0:
            if os.path.isfile(finishedName):
                out = self.siteDB.getFileContentAsJson(finishedName)
                self.siteDB.removeFile(finishedName)
                break
            timer -= 1
            time.sleep(1)
        if not out:
            print(f"Failed to accept delta. Timeout reached. {hashNum}")
            outContent["State"] = "failed"
            outContent["Error"] = "Failed to accept delta. Timeout reached."
            return outContent
        outContent["State"] = out["State"]
        outContent["id"] = hashNum
        outContent["lastModified"] = convertTSToDatetime(outContent["UpdateTime"])
        outContent["href"] = f"{environ['APP_CALLBACK']}/{hashNum}"
        if outContent["State"] not in ["accepted"]:
            if "Error" not in out:
                outContent["Error"] = f"Unknown Error. Dump all out content {jsondumps(out)}"
            else:
                outContent["Error"] = out["Error"]

        return outContent

    def __getdeltaINT(self, deltaID=None, **_kwargs):
        """Get delta from database."""
        if not deltaID:
            return self.dbI.get("deltas", orderby=['insertdate', 'DESC'])
        out = self.dbI.get(
            "deltas", search=[["uid", deltaID]], orderby=["insertdate", "DESC"]
        )
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out[0]

    def __getdeltastatesINT(self, deltaID, **_kwargs):
        """Get delta states from database."""
        out = self.dbI.get("states", search=[["deltaid", deltaID]], orderby=['insertdate', 'DESC'])
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out

    def __commitdelta(self, deltaID, _environ, **kwargs):
        """Change delta state."""
        delta = self.__getdeltaINT(deltaID, **kwargs)
        if kwargs['newaction'] == "commit" and delta["state"] == "accepted":
            self.stateM.commit(self.dbI, {"uid": deltaID, "state": "committing"})
        elif kwargs['newaction'] == "forcecommit" and delta["state"] in ["activated", "failed"]:
            self.stateM.stateChangerDelta(self.dbI, 'committed', **delta)
            self.stateM.modelstatechanger(self.dbI, 'add', **delta)
        else:
            msg = f"Delta state in the system is not in final state. State on the system: {delta['state']}. commit allows only for accepted state. forcecommit allows only for activated or failed states."
            raise WrongDeltaStatusTransition(msg)
        return {"status": "OK"}

    def getActiveDeltas(self, _environ, **_kwargs):
        """Get all Active Deltas"""
        activeDeltas = self.dbI.get("activeDeltas", orderby=['insertdate', 'DESC'])
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            activeDeltas["output"] = evaldict(activeDeltas["output"])
        if not activeDeltas:
            activeDeltas = {"output": {}}
        return activeDeltas

    def __deltas_get(self, environ, **kwargs):
        """Private Function for Delta GET API"""
        modTime = getModTime(kwargs["headers"])
        outdeltas = self.__getdeltaINT(None, **kwargs)
        if kwargs["urlParams"]["oldview"]:
            self.httpresp.ret_200("application/json", kwargs["start_response"], None)
            return outdeltas
        outM = {"deltas": []}
        if not outdeltas:
            self.httpresp.ret_200(
                "application/json",
                kwargs["start_response"],
                [("Last-Modified", httpdate(getUTCnow()))],
            )
            return []
        updateTimestamp = 0
        for delta in outdeltas:
            if modTime > delta["updatedate"]:
                continue
            updateTimestamp = (
                updateTimestamp
                if updateTimestamp > delta["updatedate"]
                else delta["updatedate"]
            )
            current = {
                "id": delta["uid"],
                "lastModified": convertTSToDatetime(delta["updatedate"]),
                "state": delta["state"],
                "href": f"{environ['APP_CALLBACK']}/{delta['uid']}",
                "modelId": delta["modelid"],
            }
            if not kwargs["urlParams"]["summary"]:
                # Doing here not encode, because we are decoding. So it is opposite.
                current["addition"] = decodebase64(
                    delta["addition"], not kwargs["urlParams"]["encode"]
                )
                current["reduction"] = decodebase64(
                    delta["reduction"], not kwargs["urlParams"]["encode"]
                )
            outM["deltas"].append(current)
        if not outM["deltas"]:
            self.httpresp.ret_304(
                "application/json",
                kwargs["start_response"],
                [("Last-Modified", httpdate(modTime))],
            )
            return []
        self.httpresp.ret_200(
            "application/json",
            kwargs["start_response"],
            [("Last-Modified", httpdate(updateTimestamp))],
        )
        return outM["deltas"]

    def __deltas_post(self, environ, **kwargs):
        """Private Function for Delta POST API"""
        out = self.__intGetPostData(environ, **kwargs)
        newDelta = {}
        for key in list(out.keys()):
            newDelta[key] = out.get(key, "")
        for key in ["modelId", "id"]:
            if not newDelta[key]:
                raise BadRequestError(f"You did POST method, {key} is not specified")
        if not newDelta["reduction"] and not newDelta["addition"]:
            raise BadRequestError(
                "You did POST method, but nor reduction, nor addition is present"
            )
        out = self.__addNewDeltaINT(newDelta, environ, **kwargs)
        self._logDeltaUserAction(newDelta, 'add', out, environ)
        if out["State"] in ["accepted"]:
            self.httpresp.ret_201(
                "application/json",
                kwargs["start_response"],
                [
                    ("Last-Modified", httpdate(out["UpdateTime"])),
                    ("Location", out["href"]),
                ],
            )
            return out
        raise BadRequestError(
            f"Failed add new delta. Error Message: {out.get('Error', '')}."
        )

    def deltas(self, environ, **kwargs):
        """
        API Call associated with deltas
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/ # Will return info about all deltas
        Method: POST
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/ # Will add new delta and returns it's ID
        """
        # ======================================================
        # GET
        if environ["REQUEST_METHOD"].upper() == "GET":
            return self.__deltas_get(environ, **kwargs)
        # ======================================================
        # POST
        if environ["REQUEST_METHOD"].upper() == "POST":
            return self.__deltas_post(environ, **kwargs)
        raise BadRequestError("Request not in GET/POST METHOD.")

    def deltastates(self, environ, **kwargs):
        """
        API Call for getting specific delta states information;
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltastates/([-_A-Za-z0-9]+)/
        """
        outstates = self.__getdeltastatesINT(kwargs["deltaid"], **kwargs)
        self.responseHeaders(environ, **kwargs)
        return outstates

    def deltasid(self, environ, **kwargs):
        """
        API Call associated with specific delta
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+) # Will return info about specific delta
        """
        modTime = getModTime(kwargs["headers"])
        delta = self.__getdeltaINT(kwargs["deltaid"], **kwargs)
        if not delta:
            self.httpresp.ret_204(
                "application/json",
                kwargs["start_response"],
                [("Last-Modified", httpdate(getUTCnow()))],
            )
            return []
        if modTime > delta["updatedate"]:
            self.httpresp.ret_304(
                "application/json",
                kwargs["start_response"],
                [("Last-Modified", httpdate(delta["updatedate"]))],
            )
            return []
        if kwargs["urlParams"]["oldview"]:
            self.httpresp.ret_200(
                "application/json",
                kwargs["start_response"],
                [("Last-Modified", httpdate(delta["updatedate"]))],
            )
            delta["insertdate"] = convertTSToDatetime(delta["insertdate"])
            delta["updatedate"] = convertTSToDatetime(delta["updatedate"])
            return [delta]
        current = {
            "id": delta["uid"],
            "lastModified": convertTSToDatetime(delta["updatedate"]),
            "state": delta["state"],
            "href": f"{environ['APP_CALLBACK']}",
            "modelId": delta["modelid"],
        }
        if not kwargs["urlParams"]["summary"]:
            current["addition"] = encodebase64(
                delta["addition"], kwargs["urlParams"]["encode"]
            )
            current["reduction"] = encodebase64(
                delta["reduction"], kwargs["urlParams"]["encode"]
            )
        self.httpresp.ret_200(
            "application/json",
            kwargs["start_response"],
            [("Last-Modified", httpdate(delta["updatedate"]))],
        )
        return [current]

    def deltasaction(self, environ, **kwargs):
        """
        API Call for commiting delta or tiering down.
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+)/actions/(commit)
        """
        msgOut = self.__commitdelta(kwargs["deltaid"], environ, **kwargs)
        self._logDeltaUserAction(kwargs, 'commit', msgOut, environ)
        self.httpresp.ret_204("application/json", kwargs["start_response"], None)
        return []

    def activedeltas(self, environ, **kwargs):
        """
        API Call to get all active deltas in the system.
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/activedeltas
        """
        self.responseHeaders(environ, **kwargs)
        return self.getActiveDeltas(environ, **kwargs)

    def deltatimestates(self, environ, **kwargs):
        """
        API Call to set delta timed activation state
        Method: POST
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltatimestates
        """
        # POST
        out = self.__intGetPostData(environ, **kwargs)
        dbout = {
            "insertdate": getUTCnow(),
            "uuid": out["uuid"],
            "uuidtype": out["uuidtype"],
            "hostname": out["hostname"],
            "hostport": out["hostport"],
            "uuidstate": out["uuidstate"],
        }
        dbansw = self.dbI.insert("deltatimestates", [dbout])
        self._logDeltaUserAction(out, 'setstate', dbansw, environ)
        self.responseHeaders(environ, **kwargs)
        return {"status": "Recorded"}

    def deltaforceapply(self, environ, **kwargs):
        """Force apply based on delta UUID"""
        out = self.__intGetPostData(environ, **kwargs)
        dbansw = self.dbI.insert("forceapplyuuid", [{"uuid": out["uuid"]}])
        self._logDeltaUserAction({"uuid": out["uuid"]}, 'setstate', dbansw, environ)
        self.responseHeaders(environ, **kwargs)
        return {"status": "OK"}
