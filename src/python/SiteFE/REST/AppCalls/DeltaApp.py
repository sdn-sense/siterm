#! /usr/bin/env python
# pylint: disable=line-too-long, bad-whitespace
"""
All Deltas and models APIS

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
import re
import time
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import httpdate
from DTNRMLibs.MainUtilities import getModTime
from DTNRMLibs.MainUtilities import encodebase64
from DTNRMLibs.MainUtilities import decodebase64
from DTNRMLibs.MainUtilities import getCustomOutMsg
from DTNRMLibs.MainUtilities import convertTSToDatetime
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.RESTInteractions import get_post_form
from DTNRMLibs.RESTInteractions import get_json_post_form
from DTNRMLibs.RESTInteractions import is_post_request
from DTNRMLibs.RESTInteractions import is_application_json
from SiteFE.REST.Models.DeltaModels import frontendDeltaModels


CONFIG = getConfig()
LOGGER = getStreamLogger(CONFIG.get('general', 'logLevel'))

DELTABACKEND = frontendDeltaModels(logger=LOGGER, config=CONFIG)

# =====================================================================================================================
# =====================================================================================================================
_DELTAS_RE = re.compile(r'^/*v1/deltas/?$')
def deltas(environ, **kwargs):
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
        modTime = getModTime(kwargs['headers'])
        outdeltas = DELTABACKEND.getdelta(None, **kwargs)
        if kwargs['urlParams']['oldview']:
            print 'Return All deltas. 200 OK'
            kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
            return outdeltas
        outM = {"deltas": []}
        if not outdeltas:
            kwargs['http_respond'].ret_204('application/json', kwargs['start_response'],
                                           [('Last-Modified', httpdate(getUTCnow()))])
            print 'Return empty list. There are no deltas on the system'
            return []
        updateTimestamp = 0
        for delta in outdeltas:
            if modTime > delta['updatedate']:
                continue
            updateTimestamp = updateTimestamp if updateTimestamp > delta['updatedate'] else delta['updatedate']
            current = {"id": delta['uid'],
                       "lastModified": convertTSToDatetime(delta['updatedate']),
                       "state": delta['state'],
                       "href": "%s/%s" % (environ['SCRIPT_URI'], delta['uid']),
                       "modelId": delta['modelid']}
            if not kwargs['urlParams']['summary']:
                # Doing here not encode, because we are decoding. So it is opposite.
                current["addition"] = decodebase64(delta['addition'], not kwargs['urlParams']['encode'])
                current["reduction"] = decodebase64(delta['reduction'], not kwargs['urlParams']['encode'])
            outM["deltas"].append(current)
        if not outM["deltas"]:
            kwargs['http_respond'].ret_304('application/json', kwargs['start_response'], ('Last-Modified', httpdate(modTime)))
            return []
        kwargs['http_respond'].ret_200('application/json', kwargs['start_response'],
                                       [('Last-Modified', httpdate(updateTimestamp))])
        print 'Return Last Delta. 200 OK'
        return outM["deltas"]
    # ======================================================
    # POST
    out = {}
    post_request = False
    if environ['REQUEST_METHOD'].upper() == 'POST':
        post_request = is_post_request(environ)
    if not post_request:
        if is_application_json(environ):
            out = get_json_post_form(environ)
        else:
            kwargs['http_respond'].ret_400('application/json', kwargs['start_response'], None)
            customErr = getCustomOutMsg(errMsg='You did POST method, but provided CONTENT_TYPE is not correct', errCode=400)
            print 'Return 400. More details: %s' % customErr
            return customErr
    if not out:
        out = get_post_form(environ)
    newDelta = {}
    for key in out.keys():
        newDelta[key] = out.get(key, "")
    for key in ['modelId', 'id']:
        if not newDelta[key]:
            customErr = getCustomOutMsg(errMsg='You did POST method, %s is not specified' % key, errCode=400)
            print 'Wrong delta: %s. Parsed:%s Error: %s' % (out, newDelta, customErr)
            kwargs['http_respond'].ret_400('application/json', kwargs['start_response'], None)
            return customErr
    if not newDelta['reduction'] and not newDelta['addition']:
        customErr = getCustomOutMsg(errMsg='You did POST method, but nor reduction, nor addition is present', errCode=400)
        print 'Wrong delta: %s. Parsed:%s Error: %s' % (out, newDelta, customErr)
        kwargs['http_respond'].ret_400('application/json', kwargs['start_response'], None)
        return customErr
    return DELTABACKEND.addNewDelta(newDelta, environ, **kwargs)

# =====================================================================================================================
# =====================================================================================================================

_DELTAS_ID_RE = re.compile(r'^/*v1/deltas/([-_A-Za-z0-9]+)/?$')
def deltas_id(environ, **kwargs):
    """
    API Call associated with specific delta
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+) # Will return info about specific delta
    """
    # METHOD DELETE!!!!! TODO
    if environ['REQUEST_METHOD'].upper() == 'DELETE':
        kwargs['http_respond'].ret_405('application/json', kwargs['start_response'], ('Location', '/'))
        print 'DELETE Method is not supported yet. Return 405'
        return [getCustomOutMsg(errMsg="Method %s is not supported in %s" % environ['REQUEST_METHOD'].upper(), errCode=405)]
    modTime = getModTime(kwargs['headers'])
    print 'Delta Status query for %s' % kwargs['mReg'].groups()[0]
    delta = DELTABACKEND.getdelta(kwargs['mReg'].groups()[0], **kwargs)
    if not delta:
        kwargs['http_respond'].ret_204('application/json', kwargs['start_response'],
                                       [('Last-Modified', httpdate(getUTCnow()))])
        print 'Return empty list. There are no deltas on the system'
        return []
    if modTime > delta['updatedate']:
        print 'Delta with ID %s was not updated so far. Time request comparison requested' % kwargs['mReg'].groups()[0]
        kwargs['http_respond'].ret_304('application/json', kwargs['start_response'], ('Last-Modified', httpdate(delta['updatedate'])))
        return []
    if kwargs['urlParams']['oldview']:
        kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], [('Last-Modified', httpdate(delta['updatedate']))])
        return [delta]
    current = {}
    current = {"id": delta['uid'],
               "lastModified": convertTSToDatetime(delta['updatedate']),
               "state": delta['state'],
               "href": "%s" % environ['SCRIPT_URI'],
               "modelId": delta['modelid']}
    if not kwargs['urlParams']['summary']:
        current['addition'] = encodebase64(delta['addition'], kwargs['urlParams']['encode'])
        current['reduction'] = encodebase64(delta['reduction'], kwargs['urlParams']['encode'])
    print 'Returning delta %s information. Few details: ModelID: %s, State: %s, LastModified: %s' % \
          (current["id"], current["modelId"], current["state"], current["lastModified"])
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], [('Last-Modified', httpdate(delta['updatedate']))])
    return [current]

_DELTAS_ID_ACTION_RE = re.compile(r'^/*v1/deltas/([-_A-Za-z0-9]+)/actions/commit/?$')
def deltas_action(environ, **kwargs):
    """
    API Call for commiting delta or tiering down.
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+)/actions/(commit)
              # Will commit or remove specific delta. remove is allowed only from same host or
                dtnrm-site-frontend
    """
    del environ
    msgOut = DELTABACKEND.commitdelta(kwargs['mReg'].groups()[0], **kwargs)
    kwargs['http_respond'].ret_204('application/json', kwargs['start_response'], None)
    print 'Delta %s commited. Return 204' % kwargs['mReg'].groups()[0]
    return msgOut

# =====================================================================================================================
# =====================================================================================================================

_MODELS_RE = re.compile(r'^/*v1/models/?$')
def models(environ, **kwargs):
    """
    Returns a collection of available model resources within the Resource Manager
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/models/ # Returns list of all models;
    """
    # Get IF_MODIFIED_SINCE modification time in timestamp
    modTime = getModTime(kwargs['headers'])
    outmodels = DELTABACKEND.getmodel(**kwargs)
    if not outmodels:
        kwargs['http_respond'].ret_500('application/json', kwargs['start_response'], None)
        print 'LastModel does not exist in dictionary. First time run? See documentation'
        return getCustomOutMsg(errMsg="No models are available...", errCode=500)
    outmodels = [outmodels] if isinstance(outmodels, dict) else outmodels
    outM = {"models": []}
    current = {"id": outmodels[0]['uid'],
               "creationTime": convertTSToDatetime(outmodels[0]['insertdate']),
               "href": "%s/%s" % (environ['SCRIPT_URI'], outmodels[0]['uid'])}
    print outmodels[0]['insertdate'], modTime, getUTCnow()
    if outmodels[0]['insertdate'] < modTime:
        print '%s and %s' % (outmodels[0]['insertdate'], modTime)
        kwargs['http_respond'].ret_304('application/json', kwargs['start_response'], ('Last-Modified', httpdate(outmodels[0]['insertdate'])))
        return []
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], [('Last-Modified', httpdate(outmodels[0]['insertdate']))])
    if kwargs['urlParams']['oldview']:
        print 'Requested oldview model output. Return 200'
        return outmodels
    elif kwargs['urlParams']['current']:
        if not kwargs['urlParams']['summary']:
            current['model'] = encodebase64(DELTABACKEND.getmodel(outmodels[0]['uid'], content=True, **kwargs), kwargs['urlParams']['encode'])
        outM['models'].append(current)
        print 'Requested only current model. Return 200. Last Model %s' % outmodels[0]
        return [current]
    elif not kwargs['urlParams']['current']:
        for model in outmodels:
            tmpDict = {"id": model['uid'],
                       "creationTime": convertTSToDatetime(model['insertdate']),
                       "href": "%s/%s" % (environ['SCRIPT_URI'], model['uid'])}
            if not kwargs['urlParams']['summary']:
                tmpDict['model'] = encodebase64(DELTABACKEND.getmodel(model['uid'], content=True, **kwargs), kwargs['urlParams']['encode'])
            outM['models'].append(tmpDict)
        print 'Returning all models known to the system. Return 200'
        return outM['models']

# =====================================================================================================================
# =====================================================================================================================

_MODELS_ID_RE = re.compile(r'^/*v1/models/([-_A-Za-z0-9]+)/?$')
def models_id(environ, **kwargs):
    """
    API Call for getting specific model and associated deltas;
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/models/([-_A-Za-z0-9]+)/ # Returns list of all models;
    """
    modTime = getModTime(kwargs['headers'])
    modelID = kwargs['mReg'].groups()[0]
    outmodels = DELTABACKEND.getmodel(modelID, **kwargs)
    model = outmodels if isinstance(outmodels, dict) else outmodels[0]
    if modTime > model['insertdate']:
        print 'Model with ID %s was not updated so far. Time request comparison requested' % modelID
        kwargs['http_respond'].ret_304('application/json', kwargs['start_response'], ('Last-Modified', httpdate(model['insertdate'])))
        return []
    current = {"id": model['uid'],
               "creationTime": convertTSToDatetime(model['insertdate']),
               "href": "%s/%s" % (environ['SCRIPT_URI'], model['uid'])}
    if not kwargs['urlParams']['summary']:
        current['model'] = encodebase64(DELTABACKEND.getmodel(model['uid'], content=True, **kwargs), kwargs['urlParams']['encode'])
    print 'Requested a specific model with id %s' % modelID
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], [('Last-Modified', httpdate(model['insertdate']))])
    return current
    # Deltas are not associated with model. Not clear use case. If deltas is there Return all deltas.

# =====================================================================================================================
# =====================================================================================================================

_DELTA_INTERNAL_ACTION_RE = re.compile(r'^/*v1/deltas/([-_A-Za-z0-9]+)/internalaction/([-_\.A-Za-z0-9]+)/(cancel|active|failed)/?$')
def delta_internal_actions(environ, **kwargs):
    """
    API Call for internalactions. This is only allowed from same host or dtnrm-site-fe.
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/deltas/([-_A-Za-z0-9]+)/internalaction/(cancel|active|failed)
    """
    del environ
    deltaID = kwargs['mReg'].groups()[0]
    hostname = kwargs['mReg'].groups()[1]
    newState = kwargs['mReg'].groups()[2]
    print 'Internal action. For %s and %s to %s' % (deltaID, hostname, newState)
    msgOut = DELTABACKEND.commitdelta(deltaID, newState, internal=True, hostname=hostname, **kwargs)
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    return msgOut

_DELTA_HOSTNAME_IDS_RE = re.compile(r'^/*v1/hostnameids/([-_\.A-Za-z0-9]+)/(activating|active)/?$')
def delta_hostname_ids(environ, **kwargs):
    """
    API Call for returning all Hostname IDs states; This is needed for internal action check
    Method: GET
    Output: application/json
    Examples: https://server-host/sitefe/v1/hostnameids/hostname.us.gov/(activating|active)
    """
    del environ
    hostname = ""
    hostname = kwargs['mReg'].groups()[0]
    state = kwargs['mReg'].groups()[1]
    print 'Called to get all ids assigned to %s hostname' % hostname
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    return DELTABACKEND.getHostNameIDs(hostname, state, **kwargs)

# =====================================================================================================================
# =====================================================================================================================

CALLS = [(_DELTA_INTERNAL_ACTION_RE, delta_internal_actions, ['GET'], [], []),
         (_MODELS_ID_RE, models_id, ['GET'], [{"key": "encode", "default": False, "type": bool},
                                              {"key": "summary", "default": False, "type": bool}], []),
         (_MODELS_RE, models, ['GET'], [{"key": "current", "default": False, "type": bool},
                                        {"key": "summary", "default": True, "type": bool},
                                        {"key": "oldview", "default": False, "type": bool},
                                        {"key": "encode", "default": True, "type": bool},
                                        {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}], []),
         (_DELTAS_ID_ACTION_RE, deltas_action, ['PUT', 'GET'], [], []),
         (_DELTAS_ID_RE, deltas_id, ['GET', 'DELETE'], [{"key": "model", "default": "turtle", "type": str, "options": ['turtle']},
                                                        {"key": "encode", "default": True, "type": bool},
                                                        {"key": "oldview", "default": False, "type": bool},
                                                        {"key": "summary", "default": False, "type": bool}], []),
         (_DELTAS_RE, deltas, ['GET', 'POST'], [{"key": "summary", "default": True, "type": bool},
                                                {"key": "oldview", "default": False, "type": bool},
                                                {"key": "encode", "default": True, "type": bool},
                                                {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}], []),
         (_DELTA_HOSTNAME_IDS_RE, delta_hostname_ids, ['GET'], [], [])]
