#!/usr/bin/python
"""
Plugin to get XrootD server information

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
import pprint
from DTNRMAgent.RecurringActions.Utilities import externalCommand, runPipedCmd, getProcInfo
from DTNRMLibs.MainUtilities import getConfig

NAME = 'XrootDInfo'


def getItemPos(item, inList):
    """ get item position from the list """
    for i, j in enumerate(inList):
        if j == item:
            return i
    return -1


def get(config):
    """Get memory info from /proc/meminfo"""
    itemOut = {}
    tmpOut = runPipedCmd('ps auxf', 'grep xrootd')  # TODO if nothing running. return empty
    configFiles = []
    pids = []
    itemOut['app'] = "xrootd"
    itemOut['status'] = "running"  # TODO do it automatic
    for item in tmpOut:
        if not item:
            continue
        for desc in item.split('\n'):
            if not desc:
                continue
            vals = [val for val in desc.split() if val]
            configPos = getItemPos('-c', vals)
            if configPos == -1:
                continue
            if vals[configPos + 1] not in configFiles:
                configFiles.append(vals[configPos + 1])
                pids.append(vals[1])
    counter = -1
    itemOut['configuration'] = {}
    for fileName in configFiles:
        counter += 1
        tmpOut = externalCommand('cat %s' % fileName)
        itemOut[pids[counter]] = {}
        itemOut[pids[counter]]['Config'] = {}
        for item in tmpOut:
            for desc in item.split('\n'):
                if desc.startswith('#'):
                    continue
                if not desc:
                    continue
                vals = desc.split(' ', 1)
                if len(vals) == 1:
                    vals.append(True)
                if vals[0] == 'sec.protocol':
                    tmpvals = [val for val in vals[1].split() if val]
                    for item1 in tmpvals:
                        tmpkeyVal = [val for val in item1.split(":") if val]
                        if tmpkeyVal[0] != '-cert':
                            continue
                itemOut['configuration'][pids[counter]]['Config'][vals[0]] = vals[1]
        itemOut['configuration'][pids[counter]]['UsageInfo'] = getProcInfo(pids[counter])
    return itemOut

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
