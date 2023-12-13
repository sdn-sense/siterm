#!/usr/bin/env python3
"""Plugins which gathers all information from /proc/meminfo.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import pprint

from SiteRMAgent.RecurringActions.Utilities import tryConvertToNumeric
from SiteRMLibs.MainUtilities import externalCommand, getLoggingObject

NAME = "MemInfo"


def get(**_):
    """Get memory info from /proc/meminfo"""
    memInfo = {}
    tmpOut = externalCommand("cat /proc/meminfo")
    for item in tmpOut:
        for desc in item.decode("UTF-8").split("\n"):
            vals = desc.split(":")
            if len(vals) == 2:
                value = vals[1].strip().split(" ")
                # We strip it to remove white spaces and split to remove kb in the end
                name = vals[0].strip()
                if len(value) == 2:
                    name += f"_{value[1]}"
                memInfo[name] = tryConvertToNumeric(value[0])
    memInfo["memory_mb"] = int(memInfo["MemTotal_kB"] // 1000)
    return memInfo


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="Agent")
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get())
