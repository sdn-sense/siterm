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
import os
from SiteRMAgent.Debugger.Actions.arptable import arptable
from SiteRMAgent.Debugger.Actions.iperf import iperf
from SiteRMAgent.Debugger.Actions.rapidping import rapidping
from SiteRMAgent.Debugger.Actions.tcpdump import tcpdump
from SiteRMAgent.Debugger.Actions.iperfserver import iperfserver
from SiteRMAgent.Debugger.Actions.prometheuspush import prometheuspush

from SiteRMLibs.MainUtilities import createDirs
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.MainUtilities import publishToSiteFE
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import jsondumps
from SiteRMLibs.CustomExceptions import FailedGetDataFromFE

COMPONENT = 'Debugger'


class Debugger():
    """Debugger main process"""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service='Debugger')
        self.fullURL = getFullUrl(self.config, sitename)
        self.sitename = sitename
        self.hostname = self.config.get('agent', 'hostname')
        self.diragent = contentDB()
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
        """Get All Assigned/Active to Host"""
        allAssigned = []
        for call in [f"/sitefe/json/frontend/getalldebughostname/{self.hostname}",
                     f"/sitefe/json/frontend/getalldebughostnameactive/{self.hostname}"]:
            data = self.getData(call)
            if data:
                allAssigned += data
        return allAssigned

    def publishToFE(self, inDic):
        """Publish debug runtime to FE"""
        publishToSiteFE(inDic, self.fullURL, f"/sitefe/json/frontend/updatedebug/{inDic['id']}")

    def _startbackgroundwork(self, item):
        """Start Background work, like prometheus push, arppush"""
        workDir = self.config.get('general', 'private_dir') + "/SiteRM/background/"
        createDirs(workDir)
        fname = workDir + f"/background-process-{item['id']}.json"
        if not os.path.isfile(fname):
            self.diragent.dumpFileContentAsJson(fname, item)
        newstate = ""
        try:
            out, err, exitCode = prometheuspush(item)
        except (ValueError, KeyError, OSError) as ex:
            out = ""
            err = ex
            exitCode = 501
        output = {'out': out, 'err': str(err), 'exitCode': exitCode}
        self.logger.info(f"Finish work on: {output}")
        # 501, 1 - error - set to failed
        # 2 - active
        # 3 - finished
        if exitCode in [501, 1]:
            newstate = 'failed'
        elif exitCode in [0]:
            newstate = 'active'
        elif exitCode in [3]:
            self.diragent.removeFile(fname)
            newstate = 'finished'
        else:
            newstate = 'unknown'
        if item['state'] != newstate:
            item['state'] = newstate
            self.publishToFE(item)

    def startwork(self):
        """Start execution and get new requests from FE"""
        allWork = self.getAllAssignedtoHost()
        out, err, exitCode = "", "", 0
        for item in allWork:
            self.logger.info(f"Work on: {item}")
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
                elif item['requestdict']['type'] in ['prometheus-push', 'arp-push']:
                    self._startbackgroundwork(item)
                    continue
                else:
                    err = "Unknown Request"
                    exitCode = 500
            except (ValueError, KeyError, OSError) as ex:
                err = ex
                exitCode = 501
            output = {'out': out, 'err': str(err), 'exitCode': exitCode}
            item['output'] = jsondumps(output)
            if exitCode != 0:
                item['state'] = 'failed'
            else:
                item['state'] = 'finished'
            self.logger.debug(f"Finish work on: {item}")
            self.publishToFE(item)


def execute(config=None):
    """Execute main script for Debugger execution."""
    debugger = Debugger(config, 'T2_US_Caltech_Test')
    debugger.startwork()

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='Debugger')
    execute()
