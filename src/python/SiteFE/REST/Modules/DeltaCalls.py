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
from tempfile import NamedTemporaryFile
from SiteRMLibs.MainUtilities import httpdate
from SiteRMLibs.MainUtilities import getModTime
from SiteRMLibs.MainUtilities import encodebase64
from SiteRMLibs.MainUtilities import decodebase64
from SiteRMLibs.MainUtilities import convertTSToDatetime
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import jsondumps
from SiteRMLibs.RESTInteractions import get_post_form
from SiteRMLibs.RESTInteractions import get_json_post_form
from SiteRMLibs.RESTInteractions import is_post_request
from SiteRMLibs.RESTInteractions import is_application_json
from SiteRMLibs.CustomExceptions import ConflictEntries, BadRequestError, DeltaNotFound, WrongDeltaStatusTransition
from SiteFE.PolicyService import policyService as polS
from SiteFE.PolicyService import stateMachine as stateM


class DeltaCalls:
    """Delta Calls API Module"""
    # pylint: disable=E1101
    def __init__(self):
        self.stateM = stateM.StateMachine(self.config)
        self.__defineRoutes()
        self.__urlParams()
        self.policer = {}
        for sitename in self.sites:
            if sitename != 'MAIN':
                self.policer[sitename] = polS.PolicyService(self.config, sitename)

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'deltas': {'allowedMethods': ['GET', 'POST'],
                                'urlParams': [{"key": "summary", "default": True, "type": bool},
                                              {"key": "oldview", "default": False, "type": bool},
                                              {"key": "encode", "default": True, "type": bool},
                                              {"key": "model", "default": "turtle", "type": str,
                                               "options": ['turtle']}]},
                     'deltasid': {'allowedMethods': ['GET'],
                                  'urlParams': [{"key": "model", "default": "turtle", "type": str,
                                                 "options": ['turtle']},
                                                {"key": "encode", "default": True, "type": bool},
                                                {"key": "oldview", "default": False, "type": bool},
                                                {"key": "summary", "default": False, "type": bool}]},
                     'deltasaction': {'allowedMethods': ['GET', 'PUT']},
                     'activedeltas': {'allowedMethods': ['GET']},
                     'deltastates': {'allowedMethods': ['GET']},
                     'deltatimestates': {'allowedMethods': ['POST']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("deltas", "/v1/deltas", action="deltas")
        self.routeMap.connect("deltasid", "/v1/deltas/:deltaid", action="deltasid")
        self.routeMap.connect("deltasaction", "/v1/deltas/:deltaid/actions/commit", action="deltasaction")
        self.routeMap.connect("activedeltas", "/v1/activedeltas", action="activedeltas")
        self.routeMap.connect("deltastates", "/v1/deltastates/:deltaid", action="deltastates")
        self.routeMap.connect("deltatimestates", "/v1/deltatimestates", action="deltatimestates")

    @staticmethod
    def __intGetPostData(environ, **kwargs):
        """Parse POST Data"""
        out = {}
        postRequest = False
        if environ['REQUEST_METHOD'].upper() == 'POST':
            postRequest = is_post_request(environ)
        if not postRequest:
            if is_application_json(environ):
                out = get_json_post_form(environ)
            else:
                raise BadRequestError('You did POST method, but provided CONTENT_TYPE is not correct')
        if not out:
            out = get_post_form(environ)
        return out

    def __addNewDeltaINT(self, uploadContent, environ, **kwargs):
        """Add new delta."""
        hashNum = uploadContent['id']
        if self.dbobj.get('deltas', search=[['uid', hashNum]], limit=1):
            # This needs to be supported as it can be re-initiated again. TODO
            msg = 'Something weird has happened... Check server logs; Same ID is already in DB'
            raise ConflictEntries(msg)
        tmpfd = NamedTemporaryFile(delete=False, mode="w+")
        tmpfd.close()
        self.getmodel(environ, uploadContent['modelId'], None, **kwargs)
        outContent = {"ID": hashNum,
                      "InsertTime": getUTCnow(),
                      "UpdateTime": getUTCnow(),
                      "Content": uploadContent,
                      "State": "accepting",
                      "modelId": uploadContent['modelId']}
        self.siteDB.saveContent(tmpfd.name, outContent)
        out = self.policer[kwargs['sitename']].acceptDelta(tmpfd.name)
        outContent['State'] = out['State']
        outContent['id'] = hashNum
        outContent['lastModified'] = convertTSToDatetime(outContent['UpdateTime'])
        outContent['href'] = f"{environ['SCRIPT_URI']}/{hashNum}"
        if outContent['State'] not in ['accepted']:
            if 'Error' not in out:
                outContent['Error'] = f"Unknown Error. Dump all out content {jsondumps(out)}"
            else:
                outContent['Error'] = out['Error']
        return outContent

    def __getdeltaINT(self, deltaID=None, **kwargs):
        """Get delta from database."""
        if not deltaID:
            return self.dbobj.get('deltas')
        out = self.dbobj.get('deltas', search=[['uid', deltaID]], orderby=['insertdate', 'ASC'])
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out[0]

    def __getdeltastatesINT(self, deltaID, **kwargs):
        """Get delta states from database."""
        out = self.dbobj.get('states', search=[['deltaid', deltaID]])
        if not out:
            raise DeltaNotFound(f"Delta with {deltaID} id was not found in the system")
        return out

    def __commitdelta(self, deltaID, environ, newState='UNKNOWN', internal=False, hostname=None, **kwargs):
        """Change delta state."""
        if internal:
            out = self.dbobj.get('hoststates', search=[['deltaid', deltaID], ['hostname', hostname]])
            if not out:
                msg = f'This query did not returned any host states for {deltaID} {hostname}'
                raise WrongDeltaStatusTransition(msg)
            self.stateM.stateChangerHost(self.dbobj, out[0]['id'], **{'deltaid': deltaID,
                                                                      'state': newState,
                                                                      'insertdate': getUTCnow(),
                                                                      'hostname': hostname})
            if newState == 'remove':
                # Remove state comes only from modify
                self.stateM.stateChange(self.dbobj, {'uid': deltaID, 'state': newState})
            return {'status': 'OK', 'msg': 'Internal State change approved'}
        delta = self.__getdeltaINT(deltaID, **kwargs)
        # Now we go directly to commited in case of commit
        if delta['state'] != 'accepted':
            msg = (f"Delta state in the system is not in accepted state."
                   f"State on the system: {delta['state']}. Not allowed to change.")
            raise WrongDeltaStatusTransition(msg)
        self.stateM.commit(self.dbobj, {'uid': deltaID, 'state': 'committing'})
        return {'status': 'OK'}

    def __getActiveDeltas(self, environ, **kwargs):
        """Get all Active Deltas"""
        activeDeltas = self.dbobj.get('activeDeltas')
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            activeDeltas['output'] = evaldict(activeDeltas['output'])
        if not activeDeltas:
            activeDeltas = {'output': {}}
        return activeDeltas

    def __deltas_get(self, environ, **kwargs):
        """Private Function for Delta GET API"""
        modTime = getModTime(kwargs['headers'])
        outdeltas = self.__getdeltaINT(None, **kwargs)
        if kwargs['urlParams']['oldview']:
            self.httpresp.ret_200('application/json', kwargs["start_response"], None)
            return outdeltas
        outM = {"deltas": []}
        if not outdeltas:
            self.httpresp.ret_200('application/json', kwargs["start_response"], [('Last-Modified', httpdate(getUTCnow()))])
            return []
        updateTimestamp = 0
        for delta in outdeltas:
            if modTime > delta['updatedate']:
                continue
            updateTimestamp = updateTimestamp if updateTimestamp > delta['updatedate'] else delta['updatedate']
            current = {"id": delta['uid'],
                       "lastModified": convertTSToDatetime(delta['updatedate']),
                       "state": delta['state'],
                       "href": f"{environ['SCRIPT_URI']}/{delta['uid']}",
                       "modelId": delta['modelid']}
            if not kwargs['urlParams']['summary']:
                # Doing here not encode, because we are decoding. So it is opposite.
                current["addition"] = decodebase64(delta['addition'], not kwargs['urlParams']['encode'])
                current["reduction"] = decodebase64(delta['reduction'], not kwargs['urlParams']['encode'])
            outM["deltas"].append(current)
        if not outM["deltas"]:
            self.httpresp.ret_304('application/json', kwargs["start_response"], [('Last-Modified', httpdate(modTime))])
            return []
        self.httpresp.ret_200('application/json', kwargs["start_response"], [('Last-Modified', httpdate(updateTimestamp))])
        return outM["deltas"]

    def __deltas_post(self, environ, **kwargs):
        """Private Function for Delta POST API"""
        out = self.__intGetPostData(environ, **kwargs)
        newDelta = {}
        for key in list(out.keys()):
            newDelta[key] = out.get(key, "")
        for key in ['modelId', 'id']:
            if not newDelta[key]:
                raise BadRequestError(f'You did POST method, {key} is not specified')
        if not newDelta['reduction'] and not newDelta['addition']:
            raise BadRequestError('You did POST method, but nor reduction, nor addition is present')
        out = self.__addNewDeltaINT(newDelta, environ, **kwargs)
        if out['State'] in ['accepted']:
            self.httpresp.ret_201('application/json', kwargs["start_response"],
                                  [('Last-Modified', httpdate(out['UpdateTime'])), ('Location', out['href'])])
            return out
        raise BadRequestError(f"Failed add new delta. Error Message: {out.get('Error', '')}.")

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
        if environ['REQUEST_METHOD'].upper() == 'GET':
            return self.__deltas_get(environ, **kwargs)
        # ======================================================
        # POST
        if environ['REQUEST_METHOD'].upper() == 'POST':
            return self.__deltas_post(environ, **kwargs)
        raise BadRequestError('Request not in GET/POST METHOD.')

    def deltastates(self, environ, **kwargs):
        """
        API Call for getting specific delta states information;
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltastates/([-_A-Za-z0-9]+)/
        """
        outstates = self.__getdeltastatesINT(kwargs['deltaid'], **kwargs)
        self.responseHeaders(environ, **kwargs)
        return outstates

    def deltasid(self, environ, **kwargs):
        """
        API Call associated with specific delta
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+) # Will return info about specific delta
        """
        modTime = getModTime(kwargs['headers'])
        delta = self.__getdeltaINT(kwargs['deltaid'], **kwargs)
        if not delta:
            self.httpresp.ret_204('application/json', kwargs["start_response"],
                                  [('Last-Modified', httpdate(getUTCnow()))])
            return []
        if modTime > delta['updatedate']:
            self.httpresp.ret_304('application/json', kwargs["start_response"], [('Last-Modified', httpdate(delta['updatedate']))])
            return []
        if kwargs['urlParams']['oldview']:
            self.httpresp.ret_200('application/json', kwargs["start_response"], [('Last-Modified', httpdate(delta['updatedate']))])
            delta['insertdate'] = convertTSToDatetime(delta['insertdate'])
            delta['updatedate'] = convertTSToDatetime(delta['updatedate'])
            return [delta]
        current = {}
        current = {"id": delta['uid'],
                   "lastModified": convertTSToDatetime(delta['updatedate']),
                   "state": delta['state'],
                   "href": f"{environ['SCRIPT_URI']}",
                   "modelId": delta['modelid']}
        if not kwargs['urlParams']['summary']:
            current['addition'] = encodebase64(delta['addition'], kwargs['urlParams']['encode'])
            current['reduction'] = encodebase64(delta['reduction'], kwargs['urlParams']['encode'])
        self.httpresp.ret_200('application/json', kwargs["start_response"], [('Last-Modified', httpdate(delta['updatedate']))])
        return [current]

    def deltasaction(self, environ, **kwargs):
        """
        API Call for commiting delta or tiering down.
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+)/actions/(commit)
                  # Will commit or remove specific delta. remove is allowed only from same host or
                    siterm-site-frontend
        """
        msgOut = self.__commitdelta(kwargs['deltaid'], environ, **kwargs)
        self.httpresp.ret_204('application/json', kwargs["start_response"], None)
        return msgOut

    def activedeltas(self, environ, **kwargs):
        """
        API Call to get all active deltas in the system.
        Method: GET
        Output: application/json
        Examples: https://server-host/sitefe/v1/activedeltas
        """
        self.responseHeaders(environ, **kwargs)
        return self.__getActiveDeltas(environ, **kwargs)

    def deltatimestates(self, environ, **kwargs):
        """
        API Call to set delta timed activation state
        Method: POST
        Output: application/json
        Examples: https://server-host/sitefe/v1/deltatimestates
        """
        # POST
        out = self.__intGetPostData(environ, **kwargs)
        dbout = {'insertdate': out['insertdate'],
                 'uuid': out['uuid'],
                 'uuidtype': out['uuidtype'],
                 'hostname': out['hostname'],
                 'uuidstate': out['uuidstate']}
        self.dbobj.insert('deltatimestates', [dbout])
        self.responseHeaders(environ, **kwargs)
        return {'status': 'Recorded'}
