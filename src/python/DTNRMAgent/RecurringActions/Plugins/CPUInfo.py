#!/usr/bin/env python
"""
Plugin which produces all info from lscpu
It produces:
{'CPU(s)': 2, 'L1d cache': '32K', 'CPU op-mode(s)': '32-bit, 64-bit', 'NUMA node0 CPU(s)': '0,1',
 'Hypervisor vendor': 'VMware', 'L2 cache': '256K', 'L1i cache': '32K', 'CPU MHz': 3392.164,
 'Core(s) per socket': 1, 'Virtualization type': 'full', 'Thread(s) per core': 1, 'On-line CPU(s) list': '0,1',
 'Socket(s)': 2, 'Architecture': 'x86_64', 'Model': 60, 'Vendor ID': 'GenuineIntel', 'CPU family': 6,
 'L3 cache': '8192K', 'BogoMIPS': 6784.32, 'Stepping': 3, 'Byte Order': 'Little Endian', 'NUMA node(s)': 1}

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
from DTNRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric
from DTNRMLibs.MainUtilities import getConfig

NAME = 'CPUInfo'


def get(config):
    """Get lscpu information"""
    cpuInfo = {}
    tmpOut = externalCommand('lscpu')
    for item in tmpOut:
        for desc in item.split('\n'):
            vals = desc.split(':')
            if len(vals) == 2:
                cpuInfo[vals[0].strip()] = tryConvertToNumeric(vals[1].strip())
            else:
                print 'CpuInfo: Skipped this item: ', vals
    cpuInfo['num_cores'] = 1
    if 'Socket(s)' in cpuInfo and 'Core(s) per socket':
        try:
            cpuInfo['num_cores'] = int(cpuInfo['Socket(s)']) * int(cpuInfo['Core(s) per socket'])
        except Exception:
            print 'Failed to calculate num_cores from %s. will set to 1' % cpuInfo
    return cpuInfo

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
