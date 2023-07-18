#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Debug API Calls

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
import re
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.MainUtilities import jsondumps
from DTNRMLibs.CustomExceptions import BadRequestError
from DTNRMLibs.MainUtilities import read_input_data


class CallValidator():
    """Validator class for Debug Actions"""
    def __init__(self, config):
        self.supportedActions = ['arp-push', 'prometheus-push', 'rapidping',
                                 'tcpdump', 'arptable', 'iperf', 'iperfserver']
        self.functions = {'arptable': self.__validateArp,
                          'iperf': self.__validateIperf,
                          'iperfserver': self.__validateIperfserver,
                          'rapidping': self.__validateRapidping,
                          'tcpdump': self.__validateTcpdump,
                          'prometheus-push': self.__validatePrompush,
                          'arp-push': self.__validateArppush}
        self.config = config

    @staticmethod
    def __validateArp(inputDict):
        """Validate aprdump debug request."""
        if 'interface' not in inputDict:
            raise BadRequestError('Key interface not specified in debug request.')

    @staticmethod
    def __validateIperf(inputDict):
        """Validate iperfclient debug request."""
        for key in ['interface', 'ip', 'time']:
            if key not in inputDict:
                raise BadRequestError(f'Key {key} not specified in debug request.')
            # Do not allow time to be more than 10mins
            if int(inputDict['time']) > 600:
                raise BadRequestError('Requested Runtime for debug request is more than 10mins.')

    @staticmethod
    def __validateIperfserver(inputDict):
        """Validate iperf server debug request."""
        for key in ['port', 'ip', 'time', 'onetime']:
            if key not in inputDict:
                raise BadRequestError(f'Key {key} not specified in debug request.')

    @staticmethod
    def __validateRapidping(inputDict):
        """Validate rapid ping debug request."""
        for key in ['ip', 'time', 'packetsize', 'interface']:
            if key not in inputDict:
                raise BadRequestError(f'Key {key} not specified in debug request.')
        # interval is optional - not allow more than 1 minute
        if 'interval' in inputDict and int(inputDict['interval']) > 60:
            raise BadRequestError('Requested Runtime for debug request is more than 1mins.')

    @staticmethod
    def __validateTcpdump(inputDict):
        """Validate tcpdump debug request."""
        if 'interface' not in inputDict:
            raise BadRequestError('Key interface not specified in debug request.')

    def __validatePrompush(self, inputDict):
        """Validate prometheus push debug request."""
        for key in ['hosttype', 'metadata', 'gateway', 'runtime', 'resolution']:
            if key not in inputDict:
                raise BadRequestError(f'Key {key} not specified in debug request.')
        if inputDict['hosttype'] not in ['host', 'switch']:
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
        totalRuntime = int(int(inputDict['runtime']) - getUTCnow())
        if totalRuntime < 600 or totalRuntime > 3600:
            raise BadRequestError("Total Runtime must be within range of 600 > x > 3600 seconds since epoch.")
        # Check all metadata label parameters
        if 'metadata' in inputDict:
            # Instance must be dictionary
            if not isinstance(inputDict['metadata'], dict):
                raise BadRequestError("Requested dictionary metadata is not dictionary")
            for key, val in inputDict['metadata'].items():
                if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
                    raise BadRequestError(f"Metadata Key {key} does not match prometheus label format")
                if not isinstance(val, str):
                    raise BadRequestError(f"Metadata Key {key} value is not str. Only str supported")
        # Check all filter parameters
        if 'filter' in inputDict:
            if not isinstance(inputDict['filter'], dict):
                raise BadRequestError("Requested filter must be dictionary type")
            for filterKey, filterVals in inputDict['filter'].items():
                if filterKey not in ["mac", "snmp"]:
                    raise BadRequestError(f"Requested filter {filterKey} not supported.")
                if 'operator' not in filterVals:
                    raise BadRequestError(f"Requested filter: {filterVals}, does not have operator key")
                if filterVals['operator'] not in ["and", "or"]:
                    raise BadRequestError("Only 'and' or 'or' are supported filter operators")
                if 'queries' not in filterVals:
                    raise BadRequestError("Requested filter does not have queries key")

    @staticmethod
    def __validateArppush(inputDict):
        """Validate arp push debug request."""
        for key in ['hosttype', 'metadata', 'gateway', 'runtime', 'resolution']:
            if key not in inputDict:
                raise BadRequestError(f'Key {key} not specified in debug request.')
        if inputDict['hosttype'] != 'host':
            raise BadRequestError(f"Host Type {inputDict['hosttype']} not supported.")
        totalRuntime = int(inputDict['runtime']) - getUTCnow()
        if totalRuntime < 600 or totalRuntime > 3600:
            raise BadRequestError("Total Runtime must be within range of 600 > x > 3600 seconds since epoch.")

    def validate(self, inputDict):
        """Validate wrapper for debug action."""
        if 'hostname' not in inputDict:
            raise BadRequestError('Hostname not specified in debug request.')
        if 'type' in inputDict and inputDict['type'] not in self.supportedActions:
            raise BadRequestError(f"Action {inputDict['type']} not supported. Supported actions: {self.supportedActions}")
        self.functions[inputDict['type']](inputDict)


class DebugCalls():
    """Site Frontend calls."""
    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()
        self.validator = CallValidator(self.config)

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {'getdebug': {'allowedMethods': ['GET']},
                     'getalldebughostname': {'allowedMethods': ['GET']},
                     'getalldebughostnameactive': {'allowedMethods': ['GET']},
                     'submitdebug': {'allowedMethods': ['PUT', 'POST']},
                     'updatedebug': {'allowedMethods': ['PUT', 'POST']}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect("getdebug", "/json/frontend/getdebug/:debugvar", action="getdebug")
        self.routeMap.connect("getalldebughostname", "/json/frontend/getalldebughostname/:debugvar", action="getalldebughostname")
        self.routeMap.connect("getalldebughostnameactive", "/json/frontend/getalldebughostnameactive/:debugvar", action="getalldebughostnameactive")
        self.routeMap.connect("submitdebug", "/json/frontend/submitdebug/:debugvar", action="submitdebug")
        self.routeMap.connect("updatedebug", "/json/frontend/updatedebug/:debugvar", action="updatedebug")

    def getdebug(self, environ, **kwargs):
        """Get Debug action for specific ID."""
        search = None
        if kwargs['debugvar'] != 'ALL':
            search = [['id', kwargs['debugvar']]]
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequests', orderby=['insertdate', 'DESC'],
                              search=search, limit=1000)

    def getalldebugids(self, environ, **kwargs):
        """Get All Debug IDs."""
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequestsids', orderby=['updatedate', 'DESC'], limit=1000)

    def getalldebughostname(self, environ, **kwargs):
        """Get all Debug Requests for hostname"""
        search = [['hostname', kwargs['debugvar']], ['state', 'new']]
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequests', orderby=['updatedate', 'DESC'],
                              search=search, limit=1000)

    def getalldebughostnameactive(self, environ, **kwargs):
        """Get all Debug Requests for hostname"""
        search = [['hostname', kwargs['debugvar']], ['state', 'active']]
        self.responseHeaders(environ, **kwargs)
        return self.dbobj.get('debugrequests', orderby=['updatedate', 'DESC'],
                              search=search, limit=1000)

    def submitdebug(self, environ, **kwargs):
        """Submit new debug action request."""
        inputDict = read_input_data(environ)
        jsondump = jsondumps(inputDict)
        for symbol in [";", "&"]:
            if symbol in jsondump:
                raise BadRequestError('Unsupported symbol in input request. Contact Support')
        self.validator.validate(inputDict)
        out = {'hostname': inputDict['hostname'],
               'state': 'new',
               'requestdict': jsondump,
               'output': '',
               'insertdate': getUTCnow(),
               'updatedate': getUTCnow()}
        insOut = self.dbobj.insert('debugrequests', [out])
        self.responseHeaders(environ, **kwargs)
        return {'Status': insOut[0], 'ID': insOut[2]}

    def updatedebug(self, environ, **kwargs):
        """Update debug action information."""
        inputDict = read_input_data(environ)
        out = {'id': kwargs['debugvar'],
               'state': inputDict['state'],
               'output': inputDict['output'],
               'updatedate': getUTCnow()}
        updOut = self.dbobj.update('debugrequests', [out])
        self.responseHeaders(environ, **kwargs)
        return {'Status': updOut[0], 'ID': updOut[2]}
