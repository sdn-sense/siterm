#!/usr/bin/env python3
"""
    Push local prometheus stats to a remote gateway.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/22
"""
from DTNRMLibs.MainUtilities import externalCommand
from DTNRMLibs.MainUtilities import getUTCnow


def PromPushService(inputDict):
    """Run a prometheus push thread"""
    command = f"dtnrm-prompush --action status --runnum {inputDict['id']}"
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    retOut = []
    # Check if return 0, allow to run up to 1 min longer.
    # If keeps running after 1min, stop process.
    if cmdOut.returncode == 0 and int(inputDict['requestdict']['runtime'])+60 <= int(getUTCnow()):
        command = f"dtnrm-prompush --action stop --runnum {inputDict['id']}"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        for line in out.decode("utf-8").split('\n'):
            retOut.append(line)
        return retOut, err.decode("utf-8"), 3
    if cmdOut.returncode != 0 and int(inputDict['requestdict']['runtime'])+60 >= int(getUTCnow()):
        command = f"dtnrm-prompush --action restart --foreground --runnum {inputDict['id']}"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        for line in out.decode("utf-8").split('\n'):
            retOut.append(line)
    return retOut, err.decode("utf-8"), cmdOut.returncode
