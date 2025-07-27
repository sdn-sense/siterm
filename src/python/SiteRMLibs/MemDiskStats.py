#!/usr/bin/env python3
"""
Memory and Disk Statistics Stats for container services.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""
import re
import psutil
from SiteRMLibs.MainUtilities import externalCommand, tryConvertToNumeric


def parseStorageInfo(tmpOut, storageInfo):
    """Parse df stdout and add to storageInfo var."""
    lineNum = 0
    localOut = {"Keys": [], "Values": []}
    for item in tmpOut:
        if not item:
            continue
        for line in item.decode("UTF-8").split("\n"):
            if "unrecognized option" in line:
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
        storageInfo["Values"].setdefault(oneLine[0], {})
        for index, elem in enumerate(oneLine):
            key = localOut["Keys"][index].replace("%", "Percentage")
            # Append size and also change to underscore
            if key in ["Avail", "Used", "Size"]:
                key = f"{key}_gb"
                try:
                    storageInfo["Values"][oneLine[0]][key] = elem[:1]
                except TypeError:
                    storageInfo["Values"][oneLine[0]][key] = elem
                continue
            if key == "1024-blocks":
                key = "1024_blocks"
            storageInfo["Values"][oneLine[0]][key] = elem
    return storageInfo, True


class MemDiskStats:
    """Class to handle Memory and Disk Statistics."""

    def __init__(self):
        self.memMonitor = {}
        self.storageInfo = {}

    def reset(self):
        """Reset memory monitor statistics."""
        self.memMonitor = {}
        self.storageInfo = {}

    def getMemMonitor(self):
        """Get memory monitor statistics."""
        return self.memMonitor

    def getStorageInfo(self):
        """Get storage information."""
        return self.storageInfo

    def updateStorageInfo(self):
        """Get storage mount points information."""
        storageInfo = {"Values": {}}
        tmpOut = externalCommand("df -P -h")
        storageInfo, _ = parseStorageInfo(tmpOut, dict(storageInfo))
        tmpOut = externalCommand("df -i -P")
        storageInfo, _ = parseStorageInfo(tmpOut, dict(storageInfo))
        outStorage = {"FileSystems": {}, "total_gb": 0, "app": "FileSystem"}
        totalSum = 0
        for mountName, mountVals in storageInfo["Values"].items():
            outStorage["FileSystems"][mountName] = mountVals["Avail_gb"]
            totalSum += int(mountVals["Avail_gb"])
        outStorage["total_gb"] = totalSum
        storageInfo["FileSystems"] = outStorage
        self.storageInfo = storageInfo

    def _processStats(self, proc, services, lookupid):
        """Get Process Stats - memory"""
        procList = proc.cmdline()
        if len(procList) > lookupid:
            for serviceName in services:
                if procList[lookupid].endswith(serviceName):
                    self.memMonitor.setdefault(
                        serviceName,
                        {
                            "rss": 0,
                            "vms": 0,
                            "shared": 0,
                            "text": 0,
                            "lib": 0,
                            "data": 0,
                            "dirty": 0,
                        },
                    )
                    for key in self.memMonitor[serviceName].keys():
                        if hasattr(proc.memory_info(), key):
                            self.memMonitor[serviceName][key] += getattr(
                                proc.memory_info(), key
                            )

    def updateMemStats(self, services, lookupid):
        """Refresh all Memory Statistics in FE"""

        def procWrapper(proc, services, lookupid):
            """Process Wrapper to catch exited process or zombie process"""
            try:
                self._processStats(proc, services, lookupid)
            except psutil.NoSuchProcess:
                pass
            except psutil.ZombieProcess:
                pass
        for proc in psutil.process_iter(attrs=None, ad_value=None):
            procWrapper(proc, services, lookupid)
