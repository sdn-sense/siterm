#!/usr/bin/env python3
"""Plugin which produces all info from lscpu It produces:

{'CPU(s)': 2, 'L1d cache': '32K', 'CPU op-mode(s)': '32-bit, 64-bit', 'NUMA node0 CPU(s)': '0,1',
 'Hypervisor vendor': 'VMware', 'L2 cache': '256K', 'L1i cache': '32K', 'CPU MHz': 3392.164,
 'Core(s) per socket': 1, 'Virtualization type': 'full', 'Thread(s) per core': 1, 'On-line CPU(s) list': '0,1',
 'Socket(s)': 2, 'Architecture': 'x86_64', 'Model': 60, 'Vendor ID': 'GenuineIntel', 'CPU family': 6,
 'L3 cache': '8192K', 'BogoMIPS': 6784.32, 'Stepping': 3, 'Byte Order': 'Little Endian', 'NUMA node(s)': 1}

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import pprint
from SiteRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric
from SiteRMLibs.MainUtilities import getLoggingObject

NAME = 'CPUInfo'


def get(**_):
    """Get lscpu information"""
    cpuInfo = {}
    tmpOut = externalCommand('lscpu')
    for item in tmpOut:
        for desc in item.decode('UTF-8').split('\n'):
            vals = desc.split(':')
            if len(vals) == 2:
                cpuInfo[vals[0].strip()] = tryConvertToNumeric(vals[1].strip())
            else:
                print('CpuInfo: Skipped this item: ', vals)
    try:
        cpuInfo['num_cores'] = int(cpuInfo['Socket(s)']) * int(cpuInfo['Core(s) per socket'])
    except (ValueError, KeyError):
        print(f'Failed to calculate num_cores from {cpuInfo}. will set to 1')
        cpuInfo['num_cores'] = 1
    return cpuInfo

if __name__ == "__main__":
    getLoggingObject(logType='StreamLogger', service='Agent')
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get())
