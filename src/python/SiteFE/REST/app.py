#!/usr/bin/env python3
# pylint: disable=line-too-long
"""All APIS and regural expresions for url requests. Code style example:

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
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
"""
from __future__ import print_function
import re
import importlib
import collections
import simplejson as json
from SiteFE.REST.FEApis import FrontendRM
from SiteFE.REST.prometheus_exporter import PrometheusAPI
import SiteFE.REST.AppCalls as AllCalls
from DTNRMLibs.x509 import CertHandler
from DTNRMLibs.RESTInteractions import get_match_regex
from DTNRMLibs.MainUtilities import getGitConfig
from DTNRMLibs.MainUtilities import getHeaders
from DTNRMLibs.MainUtilities import getUrlParams
from DTNRMLibs.MainUtilities import read_input_data
from DTNRMLibs.MainUtilities import getCustomOutMsg
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.CustomExceptions import HTTPResponses
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.CustomExceptions import NotSupportedArgument
from DTNRMLibs.CustomExceptions import TooManyArgumentalValues
from DTNRMLibs.CustomExceptions import DeltaNotFound
from DTNRMLibs.CustomExceptions import ModelNotFound

# Initialization is done only 1 time
_INITIALIZED = None
# Configuration global variable
_CP = None
# Frontend Resource manager
_FRONTEND_RM = FrontendRM()
_PROMETHEUS = PrometheusAPI()
_SITES = ["MAIN"]
# TODO: This is just a hack for now until we rewrite all
# httpd application. We should have a separate API for normal calls
# which do not require site name
_HTTPRESPONDER = HTTPResponses()
_CERTHANDLER = CertHandler()

LOGGER = getLoggingObject(logFile='/var/log/dtnrm-site-fe/http-api/')


# This would also allow to move all catches to here... and get all errors in one place
# ==============================================
#              DEFAULT Functions
# ==============================================
def check_initialized(environ):
    """Env and configuration initialization."""
    global _INITIALIZED
    global _CP
    global _SITES
    if not _INITIALIZED:
        _CP = getGitConfig()
        _SITES += _CP['MAIN']['general']['sites']
        _INITIALIZED = True

# =====================================================================================================================
# =====================================================================================================================
_FECONFIG_RE = re.compile(r'^/*json/frontend/configuration$')


def feconfig(environ, **kwargs):
    """Returns Frontend configuration"""
    global _CP
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    return _CP['MAIN']


_FRONTEND_RE = re.compile(r'^/*json/frontend/(addhost|updatehost|getdata|servicestate)$')
_FRONTEND_ACTIONS = {'GET': {'getdata': _FRONTEND_RM.getdata},
                     'PUT': {'addhost': _FRONTEND_RM.addhost,
                             'updatehost': _FRONTEND_RM.updatehost,
                             'servicestate': _FRONTEND_RM.servicestate}}


def frontend(environ, **kwargs):
    """Frontend information.
    Method: GET
    Calls: ips | actions | getdata
    Output: application/json
    Examples: https://server-host/json/frontend/getdata # Will return info about all hosts hosts
    Method: PUT
    Calls: addhost | updatehost | servicestate
    Output: application/json
    Examples: https://server-host/json/frontend/addhost # Will add new host. Raises error if it is already there
    """
    methodType = environ['REQUEST_METHOD'].upper()
    command = _FRONTEND_ACTIONS[methodType][kwargs['mReg'][0]]
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    if methodType == 'GET':
        return command(**kwargs)
    # Get input data and pass it to function.
    inputDict = read_input_data(environ)
    command(inputDict, **kwargs)
    return {"Status": 'OK'}


_DEBUG_RE = re.compile(r'^/*json/frontend/(submitdebug|updatedebug|getdebug|getalldebughostname)/([-_\.A-Za-z0-9]+)$')
_DEBUG_ACTIONS = {'GET': {'getdebug': _FRONTEND_RM.getdebug,
                          'getalldebughostname': _FRONTEND_RM.getalldebughostname},
                  'POST': {'submitdebug': _FRONTEND_RM.submitdebug},
                  'PUT':  {'updatedebug': _FRONTEND_RM.updatedebug}}


def debug(environ, **kwargs):
    """Debug ations
    Method: GET; Calls: getdebug
    Output: application/json
    Method: PUT; Calls: submitdebug | updatedebug
    Output: application/json
    """
    methodType = environ['REQUEST_METHOD'].upper()
    command = _DEBUG_ACTIONS[methodType][kwargs['mReg'][0]]
    kwargs['http_respond'].ret_200('application/json', kwargs['start_response'], None)
    if methodType == 'GET':
        return command(**kwargs)
    # Get input data and pass it to function.
    inputDict = read_input_data(environ)
    out = command(inputDict, **kwargs)
    return {"Status": out[0], 'ID': out[2]}

_PROMETHEUS_RE = re.compile(r'^/*json/frontend/metrics$')


def prometheus(environ, **kwargs):
    """Return prometheus stats."""
    return _PROMETHEUS.metrics(**kwargs)


URLS = [(_FECONFIG_RE, feconfig, ['GET'], [], []),
        (_FRONTEND_RE, frontend, ['GET', 'PUT'], [], []),
        (_DEBUG_RE, debug, ['GET', 'POST', 'PUT'], [], []),
        (_PROMETHEUS_RE, prometheus, ['GET'], [], [])]

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


def internallCall(caller, environ, **kwargs):
    """Delta internal call which catches all exception."""
    returnDict = {}
    exception = ""
    try:
        return caller(environ, **kwargs)
    except (ModelNotFound, DeltaNotFound) as ex:
        exception = '%s: Received Exception: %s' % (caller, ex)
        kwargs['http_respond'].ret_404('application/json', kwargs['start_response'], None)
        returnDict = getCustomOutMsg(errMsg=ex.__str__(), errCode=404)
    except (ValueError, BadRequestError, IOError) as ex:
        exception = '%s: Received Exception: %s' % (caller, ex)
        kwargs['http_respond'].ret_500('application/json', kwargs['start_response'], None)
        returnDict = getCustomOutMsg(errMsg=ex.__str__(), errCode=500)
    if exception:
        print(exception)
    return returnDict


def isiterable(inVal):
    """Check if inVal is iterable"""
    return not isinstance(inVal, str) and isinstance(inVal, collections.Iterable)


def returnDump(out):
    """Return output based on it's type."""
    if isinstance(out, (list, dict)):
        out = [json.dumps(out).encode('UTF-8')]
    elif not isiterable(out):
        out = [out.encode('UTF-8')]
    return out


def application(environ, start_response):
    """Main start.

    WSGI will always call this function, which will check if call is
    allowed.
    """
    # HTTP responses var
    check_initialized(environ)
    global _SITES
    try:
        environ['CERTINFO'] = _CERTHANDLER.getCertInfo(environ)
        _CERTHANDLER.validateCertificate(environ)
    except Exception as ex:
        _HTTPRESPONDER.ret_401('application/json', start_response, None)
        return [bytes(json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=401)), 'UTF-8')]
    path = environ.get('PATH_INFO', '').lstrip('/')
    sitename = environ.get('REQUEST_URI', '').split('/')[1]
    if sitename not in _SITES:
        _HTTPRESPONDER.ret_404('application/json', start_response, None)
        return [bytes(json.dumps(getCustomOutMsg(errMsg="Sitename %s is not configured. Contact Support."
                                           % sitename, errCode=404)), 'UTF-8')]
    for regex, callback, methods, params, acceptheader in URLS:
        match = regex.match(path)
        if match:
            regMatch = get_match_regex(environ, regex)
            if environ['REQUEST_METHOD'].upper() not in methods:
                _HTTPRESPONDER.ret_405('application/json', start_response, [('Location', '/')])
                return [bytes(json.dumps(getCustomOutMsg(errMsg="Method %s is not supported in %s"
                                                   % (environ['REQUEST_METHOD'].upper(),
                                                      callback), errCode=405)), 'UTF-8')]
            environ['jobview.url_args'] = match.groups()
            try:
                headers = getHeaders(environ)
                # by default only 'application/json' is accepted. It can be overwritten for each API inside
                # definition of URLs or headers are passed to the API call and can be checked there.
                # Preference is to keep them inside URL definitions.
                if 'ACCEPT' not in headers:
                    headers['ACCEPT'] = 'application/json'
                if acceptheader and headers['ACCEPT'] not in acceptheader:
                    _HTTPRESPONDER.ret_406('application/json', start_response, None)
                    return [bytes(json.dumps(getCustomOutMsg(errMsg="Not Acceptable Header. Provided: %s, Acceptable: %s"
                                                       % (headers['ACCEPT'], acceptheader), errCode=406)), 'UTF-8')]
                out = internallCall(caller=callback, environ=environ, start_response=start_response,
                                    mReg=regMatch.groups(), http_respond=_HTTPRESPONDER,
                                    urlParams=getUrlParams(environ, params),
                                    headers=headers, sitename=sitename)
                return returnDump(out)
            except (NotSupportedArgument, TooManyArgumentalValues) as ex:
                print('Send 400 error. More details: %s' % json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=400)))
                _HTTPRESPONDER.ret_400('application/json', start_response, None)
                return [bytes(json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=400)), 'UTF-8')]
            except IOError as ex: # Exception as ex:
                print('Send 500 error. More details: %s' % json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=500)))
                _HTTPRESPONDER.ret_500('application/json', start_response, None)
                return [bytes(json.dumps(getCustomOutMsg(errMsg=ex.__str__(), errCode=500)), 'UTF-8')]
    errMsg = "Such API does not exist. Not Implemented"
    print('Send 501 error. More details: %s' % json.dumps(getCustomOutMsg(errMsg=errMsg, errCode=501)))
    _HTTPRESPONDER.ret_501('application/json', start_response, [('Location', '/')])
    return [bytes(json.dumps(getCustomOutMsg(errMsg=errMsg, errCode=501)), 'UTF-8')]
