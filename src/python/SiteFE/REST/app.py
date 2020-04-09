#! /usr/bin/env python
# pylint: disable=line-too-long
"""
All APIS and regural expresions for url requests.
Code style example:
===== Function
_request_re = re.compile(r'^/*([-_A-Za-z0-9]+)/?$')
def request(environ, start_response):
    status = '200 OK' # HTTP Status
    headers = [('Content-type', 'text/html'),
              ('Cache-Control', 'max-age=60, public')]
    start_response(status, headers)

    path = environ.get('PATH_INFO', '')
    m = _request_re.match(path)
    request = m.groups()[0]

    tmpl = request

    return [ tmpl ]
===== CODE Style
Please follow PEP8 Rules and Pylint.
Each API has to have detailed description

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
import json
import importlib
from SiteFE.REST.FEApis import FrontendRM
import SiteFE.REST.AppCalls as AllCalls
from DTNRMLibs.x509 import CertHandler
from DTNRMLibs.RESTInteractions import getContent
from DTNRMLibs.RESTInteractions import get_match_regex
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getHeaders
from DTNRMLibs.MainUtilities import getUrlParams
from DTNRMLibs.MainUtilities import read_input_data
from DTNRMLibs.MainUtilities import getCustomOutMsg
from DTNRMLibs.CustomExceptions import NotFoundError
from DTNRMLibs.CustomExceptions import HTTPResponses
from DTNRMLibs.CustomExceptions import WrongInputError
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.CustomExceptions import NotSupportedArgument
from DTNRMLibs.CustomExceptions import TooManyArgumentalValues
from DTNRMLibs.CustomExceptions import DeltaNotFound
from DTNRMLibs.CustomExceptions import ModelNotFound
from DTNRMLibs.CustomExceptions import WrongDeltaStatusTransition

# Initialization is done only 1 time
_INITIALIZED = None
# Configuration global variable
_CP = None
# Frontend Resource manager
_FRONTEND_RM = FrontendRM()

# TODO Separate app and put to correct locations AppCalls and Models.
# TODO Return should check what is return type so that it returns json dump or text.
# This would also allow to move all catches to here... and get all errors in one place
# ==============================================
#              DEFAULT Functions
# ==============================================
def check_initialized(environ):
    """Env and configuration initialization"""
    global _INITIALIZED
    global _CP
    if not _INITIALIZED:
        _CP = getConfig()
        _INITIALIZED = True

_FRONTEND_RE = re.compile(r'^/*json/frontend/(addhost|updatehost|getdata)$')
_FRONTEND_ACTIONS = {'GET': {'getdata': _FRONTEND_RM.getdata},
                     'PUT': {'addhost': _FRONTEND_RM.addhost,
                             'updatehost': _FRONTEND_RM.updatehost}}
def frontend(environ, **kwargs):
    """Frontend information. Information which is stored in the frontend for
       backend communications.
       Method: GET
       Calls: ips | actions | getdata
       Output: application/json
       Examples: https://server-host/json/frontend/getdata # Will return info about all hosts hosts
       Method: PUT
       Calls: addhost | removehost | updatehost | addaction | updateaction | removeaction
       Output: application/json
       Examples: https://server-host/json/frontend/addhost # Will add new host. Raises error if it is already there"""
    query = None
    if kwargs['mReg'].groups()[0]:
        query = kwargs['mReg'].groups()[0]
    methodType = environ['REQUEST_METHOD'].upper()
    command = None
    command = _FRONTEND_ACTIONS[methodType][query]
    if methodType == 'GET':
        kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
        return command(**kwargs)
    # Get input data and pass it to function.
    inputDict = read_input_data(environ)
    command(inputDict, **kwargs)
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    return {"Status": 'OK'}

URLS = [(_FRONTEND_RE, frontend, ['GET', 'PUT'], [], [])]

if '__all__' in dir(AllCalls):
    for callableF in AllCalls.__all__:
        name = "SiteFE.REST.AppCalls.%s" % callableF
        method = importlib.import_module(name)
        if hasattr(method, 'CALLS'):
            for item in method.CALLS:
                URLS.append(item)
            tmpCalls = method.CALLS
        else:
            continue

# TODO
# Remove headers from a call;
# Remove GET/POST/DELETE Methods and they have to be in function.
def internallCall(caller, environ, **kwargs):
    """ Delta internal call which catches all exception """
    returnDict = {}
    exception = ""
    try:
        return caller(environ, **kwargs)
    #except (WrongDeltaStatusTransition, NotFoundError, WrongInputError) as ex:
    #    exception = '%s: Received Exception: %s' % (caller, ex)
    #    kwargs['http_respond'].ret_400('application/json', kwargs['start_response'], None)
    #    returnDict = getCustomOutMsg(errMsg=ex.__str__(), errCode=400)
    except (ModelNotFound, DeltaNotFound) as ex:
        exception = '%s: Received Exception: %s' % (caller, ex)
        kwargs['http_respond'].ret_404('application/json', kwargs['start_response'], None)
        returnDict = getCustomOutMsg(errMsg=ex.__str__(), errCode=404)
    except (ValueError, BadRequestError, IOError) as ex:
        exception = '%s: Received Exception: %s' % (caller, ex)
        kwargs['http_respond'].ret_500('application/json', kwargs['start_response'], None)
        returnDict = getCustomOutMsg(errMsg=ex.__str__(), errCode=500)
    if exception:
        print exception
    return returnDict


def application(environ, start_response):
    """
    Main start. WSGI will always call this function,
    which will check if call is allowed.
    """
    # HTTP responses var
    _HTTP_RESPOND = HTTPResponses()
    check_initialized(environ)
    certHandler = CertHandler()
    try:
        environ['CERTINFO'] = certHandler.getCertInfo(environ)
        print environ['CERTINFO']
        certHandler.validateCertificate(environ)
    except Exception as ex:
        _HTTP_RESPOND.ret_401('application/json', start_response, None)
        return [json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=401))]
    path = environ.get('PATH_INFO', '').lstrip('/')
    sitename = environ.get('REQUEST_URI', '').split('/')[1]  # TODO. DO Check for SiteName in conf
    for regex, callback, methods, params, acceptheader in URLS:
        match = regex.match(path)
        if match:
            regMatch = get_match_regex(environ, regex)
            if environ['REQUEST_METHOD'].upper() not in methods:
                _HTTP_RESPOND.ret_405('application/json', start_response, [('Location', '/')])
                return [json.dumps(getCustomOutMsg(errMsg="Method %s is not supported in %s" % (environ['REQUEST_METHOD'].upper(),
                                                                                                callback), errCode=405))]
            environ['jobview.url_args'] = match.groups()
            try:
                headers = getHeaders(environ)
                # by default only 'application/json' is accepted. It can be overwritten for each API inside
                # definition of URLs or headers are passed to the API call and can be checked there.
                # Preference is to keep them inside URL definitions.
                if 'ACCEPT' not in headers:
                    headers['ACCEPT'] = 'application/json'
                    # Even it is not specified, we work only with application/json.
                    # Any others have option to overwrite it.
                if acceptheader:
                    if headers['ACCEPT'] not in acceptheader:
                        _HTTP_RESPOND.ret_406('application/json', start_response, None)
                        return [json.dumps(getCustomOutMsg(errMsg="Not Acceptable Header. Provided: %s, Acceptable: %s" % (headers['ACCEPT'], acceptheader), errCode=406))]
                # TODO. Find better way for browser check
                # elif headers['ACCEPT'] != 'application/json':
                #    _HTTP_RESPOND.ret_406('application/json', start_response, None)
                #    return [json.dumps(getCustomOutMsg(errMsg="Header was not accepted. Provided: %s, Acceptable: %s" % (headers['ACCEPT'], 'application/json'), errCode=406))]
                return [json.dumps(internallCall(caller=callback, environ=environ, start_response=start_response,
                                                 mReg=regMatch, http_respond=_HTTP_RESPOND,
                                                 urlParams=getUrlParams(environ, params),
                                                 headers=headers, sitename=sitename))]
            except (NotSupportedArgument, TooManyArgumentalValues) as ex:
                print 'Send 400 error. More details: %s' % json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=400))
                _HTTP_RESPOND.ret_400('application/json', start_response, None)
                return [json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=400))]
    print 'Send 501 error. More details: %s' % json.dumps(getCustomOutMsg(errMsg="Such API does not exist. Not Implemented", errCode=501))
    _HTTP_RESPOND.ret_501('application/json', start_response, [('Location', '/')])
    return [json.dumps(getCustomOutMsg(errMsg="Such API does not exist. Not Implemented", errCode=501))]
