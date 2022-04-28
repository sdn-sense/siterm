#!/usr/bin/env python3
"""Cancel all deltas in Site Frontend."""
from __future__ import print_function
import sys
from DTNRMLibs.MainUtilities import getVal
from DTNRMLibs.MainUtilities import getStreamLogger
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.FECalls import getDBConn
from SiteFE.PolicyService.stateMachine import StateMachine


LOGGER = getStreamLogger()
CONFIG = getConfig()
STATEMACHINE = StateMachine(LOGGER, CONFIG)


def deleteAll(sitename, deltaUID=None):
    """delete all deltas."""
    dbI = getDBConn('cancelalldeltas')
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        if deltaUID and delta['uid'] != deltaUID:
            continue
        print('Cancel %s' % delta['uid'])
        STATEMACHINE._stateChangerDelta(dbobj, 'remove', **delta)

if __name__ == "__main__":
    print(len(sys.argv))
    print(sys.argv)
    if len(sys.argv) > 2:
        deleteAll(sys.argv[1], sys.argv[2])
    else:
        deleteAll(sys.argv[1])
