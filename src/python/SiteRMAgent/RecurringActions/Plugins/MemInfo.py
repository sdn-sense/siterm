#!/usr/bin/env python3
"""Plugins which gathers all information from /proc/meminfo.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import pprint

from SiteRMAgent.RecurringActions.Utilities import tryConvertToNumeric
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject

class MemInfo:
    """MemInfo Plugin"""
    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service="Agent")

    def get(self, **_kwargs):
        """Get memory info from /proc/meminfo"""
        memInfo = {}
        with open("/proc/meminfo", "r", encoding="utf-8") as memFile:
            for desc in memFile:
                vals = desc.split(":")
                if len(vals) == 2:
                    value = vals[1].strip().split(" ")
                    # We strip it to remove white spaces and split to remove kb in the end
                    name = vals[0].strip()
                    if len(value) == 2:
                        name += f"_{value[1]}"
                    memInfo[name] = tryConvertToNumeric(value[0])
        if "MemTotal_kB" in memInfo:
            memInfo["memory_mb"] = int(memInfo["MemTotal_kB"] // 1000)
        else:
            memInfo["memory_mb"] = 0
            self.logger.warning("Failed to get MemTotal_kB from /proc/meminfo")
        return memInfo


if __name__ == "__main__":
    obj = MemInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
