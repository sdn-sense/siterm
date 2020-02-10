#!/usr/bin/env python
"""
Plugin which executes df command and prepares output about mounted storages

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
import pprint
from DTNRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric
from DTNRMLibs.MainUtilities import getConfig

NAME = 'StorageInfo'


def parseOut(tmpOut, storageInfo):
    """Parse df stdout and add to storageInfo var"""
    lineNum = 0
    localOut = {"Keys": [], "Values": []}
    for item in tmpOut:
        if not item:
            continue
        for line in item.split('\n'):
            if 'unrecognized option' in line:
                return storageInfo, False
            line = re.sub(" +", " ", line)
            if lineNum == 0:
                lineNum += 1
                line = line.replace("Mounted on", "Mounted_on")
                localOut["Keys"] = line.split()
            else:
                newList = [tryConvertToNumeric(x) for x in line.split()]
                if newList:
                    localOut["Values"].append(newList)
    for oneLine in localOut["Values"]:
        for countNum in range(len(oneLine)):
            if oneLine[0] not in storageInfo["Values"].keys():
                storageInfo["Values"][oneLine[0]] = {}
            key = localOut["Keys"][countNum].replace("%", "Percentage")
            # Append size and also change to underscore
            if key in ['Avail', 'Used', 'Size']:
                key = '%s_gb' % key
                try:
                    storageInfo["Values"][oneLine[0]][key] = oneLine[countNum][:1]
                except TypeError:
                    storageInfo["Values"][oneLine[0]][key] = oneLine[countNum]
                continue
            if key == '1024-blocks':
                key = '1024_blocks'
            storageInfo["Values"][oneLine[0]][key] = oneLine[countNum]
    return storageInfo, True

def get(config):
    """Get storage mount points information"""
    storageInfo = {"Values": {}}
    tmpOut = externalCommand('df -P -h')
    storageInfo, success = parseOut(tmpOut, dict(storageInfo))
    tmpOut = externalCommand('df -i -P')
    storageInfo, success = parseOut(tmpOut, dict(storageInfo))
    outStorage = {"FileSystems": {}, "total_gb": 0, "app": "FileSystem"}

    totalSum = 0
    for mountName, mountVals in storageInfo["Values"].iteritems():
        outStorage["FileSystems"][mountName] = mountVals['Avail_gb']
        totalSum += int(mountVals['Avail_gb'])
    outStorage["total_gb"] = totalSum
    storageInfo["FileSystems"] = outStorage
    return storageInfo

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
