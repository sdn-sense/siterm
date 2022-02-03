#!/usr/bin/env python3
"""Plugins which gathers all information from /proc/meminfo.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
from __future__ import print_function
from __future__ import division
from past.utils import old_div
import pprint
from DTNRMAgent.RecurringActions.Utilities import externalCommand, tryConvertToNumeric
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger

NAME = 'MemInfo'


def get(config, logger):
    """Get memory info from /proc/meminfo."""
    memInfo = {}
    tmpOut = externalCommand('cat /proc/meminfo')
    for item in tmpOut:
        for desc in item.decode('UTF-8').split('\n'):
            vals = desc.split(':')
            if len(vals) == 2:
                value = vals[1].strip().split(' ')
                # We strip it to remove white spaces and split to remove kb in the end
                name = vals[0].strip()
                if len(value) == 2:
                    name += "_%s" % value[1]
                memInfo[name] = tryConvertToNumeric(value[0])
            else:
                print('MemInfo: Skipped this item: ', vals)
    memInfo['memory_mb'] = int(old_div(memInfo['MemTotal_kB'], 1000))
    return memInfo

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(), getStreamLogger()))
