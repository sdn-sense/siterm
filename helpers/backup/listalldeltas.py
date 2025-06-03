#!/usr/bin/env python3
"""List all deltas inFrontend."""
from __future__ import print_function
import sys
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.GitConfig import getGitConfig
from SiteFE.PolicyService.stateMachine import StateMachine


CONFIG = getGitConfig()
LOGGER = getLoggingObject(config=CONFIG, service="Helpers")
STATEMACHINE = StateMachine(CONFIG)


def getdeltaAll(sitename):
    """Get Deltas from Database and dump to stdout"""
    dbI = getDBConn("listalldeltas")
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get("deltas"):
        delta["addition"] = evaldict(delta["addition"])
        delta["reduction"] = evaldict(delta["reduction"])
        print("=" * 80)
        print("Delta UID  :  ", delta["uid"])
        print("Delta RedID:  ", delta["reductionid"])
        print("Delta State:  ", delta["state"])
        print("Delta ModAdd: ", delta["modadd"])
        print("Delta InsDate:", delta["insertdate"])
        print("Delta Update: ", delta["updatedate"])
        print("Delta Model:  ", delta["modelid"])
        print("Delta connID: ", delta["connectionid"])
        print("Delta Deltatype: ", delta["deltat"])
        print("-" * 20)
        print("Delta times")
        for deltatimes in dbobj.get("states", search=[["deltaid", delta["uid"]]]):
            print(
                "State: %s Date: %s" % (deltatimes["state"], deltatimes["insertdate"])
            )


if __name__ == "__main__":
    getdeltaAll(sys.argv[1])
