#!/usr/bin/env python3
"""Debugger component pulls all actions from Site-FE and do tests

   Copyright 2021 California Institute of Technology
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
@Copyright              : Copyright (C) 2021 California Institute of Technology
Date                    : 2021/03/12
"""
from __future__ import absolute_import
import json
from DTNRMAgent.Debugger.Actions.arptable import arptable
from DTNRMAgent.Debugger.Actions.iperf import iperf
from DTNRMAgent.Debugger.Actions.rapidping import rapidping
from DTNRMAgent.Debugger.Actions.tcpdump import tcpdump
from DTNRMAgent.Debugger.Actions.iperfserver import iperfserver

from DTNRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from DTNRMLibs.MainUtilities import getFullUrl
from DTNRMLibs.MainUtilities import publishToSiteFE
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.CustomExceptions import FailedGetDataFromFE

COMPONENT = 'Debugger'


class Debugger():
    """Debugger main process"""
    def __init__(self, config, sitename):
        self.config = config if config else getConfig()
        self.logger = getLoggingObject(config=self.config, service='Debugger')
        self.fullURL = getFullUrl(self.config, sitename)
        self.sitename = sitename
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Debugger Start Work. Hostname: %s", self.hostname)

    def getData(self, url):
        """Get data from FE."""
        self.logger.info(f'Query: {self.fullURL}{url}')
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = f'Received a failure getting information from Site Frontend {str(out)}'
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
        return evaldict(out[0])

    def getAllAssignedtoHost(self):
        """Get All Assigned to Host"""
        return self.getData(f"/sitefe/json/frontend/getalldebughostname/{self.hostname}")

    def publishToFE(self, inDic):
        """Publish debug runtime to FE"""
        publishToSiteFE(inDic, self.fullURL, f"/sitefe/json/frontend/updatedebug/{inDic['id']}")

    def startwork(self):
        """Start execution and get new requests from FE"""
        allWork = self.getAllAssignedtoHost()
        out, err, exitCode = "", "", 0
        for item in allWork:
            self.logger.debug(f"Work on: {item}")
            try:
                item['requestdict'] = evaldict(item['requestdict'])
                if item['requestdict']['type'] == 'rapidping':
                    out, err, exitCode = rapidping(item['requestdict'])
                elif item['requestdict']['type'] == 'tcpdump':
                    out, err, exitCode = tcpdump(item['requestdict'])
                elif item['requestdict']['type'] == 'arptable':
                    out, err, exitCode = arptable(item['requestdict'])
                elif item['requestdict']['type'] == 'iperf':
                    out, err, exitCode = iperf(item['requestdict'])
                elif item['requestdict']['type'] == 'iperfserver':
                    out, err, exitCode = iperfserver(item['requestdict'])
                else:
                    err = "Unknown Request"
                    exitCode = 500
            except (ValueError, KeyError, OSError) as ex:
                err = ex
                exitCode = 501
            output = {'out': out, 'err': err, 'exitCode': exitCode}
            item['output'] = json.dumps(output)
            if exitCode != 0:
                item['state'] = 'failed'
            else:
                item['state'] = 'finished'
            self.logger.debug(f"Finish work on: {item}")
            self.publishToFE(item)


def execute(config=None):
    """Execute main script for Debugger execution."""
    debugger = Debugger(config, None)
    debugger.startwork()

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='Debugger')
    execute()
