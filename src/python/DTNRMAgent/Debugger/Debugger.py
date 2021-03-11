#!/usr/bin/env python3
"""Debugger component pulls all actions from Site-FE and do tests
"""
from __future__ import absolute_import
import os
import json
import traceback
import glob
import pprint
from DTNRMAgent.Debugger.Actions.arptable import arptable
from DTNRMAgent.Debugger.Actions.iperf import iperf
from DTNRMAgent.Debugger.Actions.rapidping import rapidping
from DTNRMAgent.Debugger.Actions.tcpdump import tcpdump

from DTNRMLibs.MainUtilities import getDataFromSiteFE, evaldict, getStreamLogger
from DTNRMLibs.MainUtilities import createDirs, getFullUrl, contentDB, getFileContentAsJson
from DTNRMLibs.MainUtilities import publishToSiteFE
from DTNRMLibs.MainUtilities import getLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand


COMPONENT = 'Debugger'


class Debugger():
    def __init__(self, config, logger):
        self.config = config if config else getConfig()
        self.logger = logger if logger else getLogger("%s/%s/" % (self.config.get('general', 'logDir'), COMPONENT),
                                                      self.config.get('general', 'logLevel'))
        self.fullURL = getFullUrl(self.config, self.config.get('general', 'siteName'))
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Debugger Start Work. Hostname: %s", self.hostname)

    def getData(self, url):
        """Get data from FE."""
        self.logger.info('Query: %s%s' % (self.fullURL, url))
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = 'Received a failure getting information from Site Frontend %s' % str(out)
            self.logger.critical(msg)
            return {}
        if self.config.getboolean('general', "debug"):
            pretty = pprint.PrettyPrinter(indent=4)
            pretty.pprint(evaldict(out[0]))
        self.logger.info('End function checkdeltas')
        return evaldict(out[0])

    def getAllAssignedtoHost(self):
        """Get All Assigned to Host"""
        return self.getData("/sitefe/json/frontend/getalldebughostname/%s" % self.hostname)

    def publishToFE(self, inDic):
        outVals = publishToSiteFE(inDic, self.fullURL, '/sitefe/json/frontend/updatedebug/%s' % inDic['id'])

    def start(self):
        """Start execution and get new requests from FE."""
        allWork = self.getAllAssignedtoHost()
        out, err, exitCode = "", "", 0
        for item in allWork:
            print(item)
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
                else:
                    err = "Unknown Request"
                    exitCode = 500
            except:
                err = traceback.format_exc()
                exitCode = 501
            output = {'out': out, 'err': err, 'exitCode': exitCode}
            item['output'] = json.dumps(output)
            if exitCode != 0:
                item['state'] = 'failed'
            else:
                item['state'] = 'finished'
            self.publishToFE(item)


def execute(config=None, logger=None):
    """Execute main script for Debugger execution."""
    debugger = Debugger(config, logger)
    debugger.start()

if __name__ == '__main__':
    execute(logger=getStreamLogger())
