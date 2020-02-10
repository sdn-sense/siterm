#!/usr/bin/env python
"""
Plugin which produces GridFTPInfo

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
import os.path
import pprint
from DTNRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric, runPipedCmd, getProcInfo
from DTNRMLibs.MainUtilities import getConfig

NAME = 'GridFTPInfo'
IGNORE_USERS = ['root']


def get(config):
    """Get GridFTP information from /etc/gridftp and ps auxf"""
    info = {}
    if not os.path.isfile('/etc/gridftp.conf'):
        info = getCurrentRunningStats(info)
        if info['active_transfers'] == 0:
            return {}
        return info
    info['app'] = "gridftp"
    info['status'] = "running"  # TODO do it automatic
    info['configuration'] = {}
    tmpOut = externalCommand('cat /etc/gridftp.conf')
    for item in tmpOut:
        for desc in item.split('\n'):
            if desc.startswith('#'):
                continue
            if not desc:
                continue
            vals = desc.split(' ', 1)
            if len(vals) == 2:
                value = vals[1].strip().split(' ')
                name = vals[0].strip()
                if name.startswith('log_'):
                    continue
                if len(value) == 2:
                    name += "_%s" % value[1]
                info['configuration'][name] = tryConvertToNumeric(value[0])
            else:
                print 'GridFTP: Skipped this item: ', vals
    info = getCurrentRunningStats(info)
    return info

def getCurrentRunningStats(info):
    """ Get count of currently running transfers and also proc stats """
    # Get current running statistics
    tmpOut = runPipedCmd('ps auxf', 'grep globus-gridftp-server')
    totalTransferCount = 0
    for item in tmpOut:
        if not item:
            continue
        for desc in item.split('\n'):
            if 'grep globus-gridftp-server' in desc:
                continue
            print desc
            if not desc:
                continue
            vals = [val for val in desc.split() if val]
            if vals[0] in IGNORE_USERS:
                info[vals[1]] = getProcInfo(vals[1])
                continue
            totalTransferCount += 1
            if 'UserStats' not in info.keys():
                info['UserStats'] = {}
            if str(vals[0]) not in info['UserStats'].keys():
                info['UserStats'][str(vals[0])] = 0
            info['UserStats'][str(vals[0])] += 1
            # Reuse same logic as in XrootD plugin. Make this process view exported.
    info['active_transfers'] = totalTransferCount
    return info

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
