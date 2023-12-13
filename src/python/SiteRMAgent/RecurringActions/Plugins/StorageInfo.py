#!/usr/bin/env python3
"""Plugin which executes df command and prepares output about mounted storages.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import pprint
import re

from SiteRMAgent.RecurringActions.Utilities import tryConvertToNumeric
from SiteRMLibs.MainUtilities import externalCommand, getLoggingObject

NAME = "StorageInfo"


def parseOut(tmpOut, storageInfo):
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


def get(**_):
    """Get storage mount points information."""
    storageInfo = {"Values": {}}
    tmpOut = externalCommand("df -P -h")
    storageInfo, _ = parseOut(tmpOut, dict(storageInfo))
    tmpOut = externalCommand("df -i -P")
    storageInfo, _ = parseOut(tmpOut, dict(storageInfo))
    outStorage = {"FileSystems": {}, "total_gb": 0, "app": "FileSystem"}

    totalSum = 0
    for mountName, mountVals in storageInfo["Values"].items():
        outStorage["FileSystems"][mountName] = mountVals["Avail_gb"]
        totalSum += int(mountVals["Avail_gb"])
    outStorage["total_gb"] = totalSum
    storageInfo["FileSystems"] = outStorage
    return storageInfo


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="Agent")
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get())
