#!/usr/bin/env python3
"""Cancel all deltas in Site Frontend."""
from __future__ import print_function
import sys
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getConfig
from SiteRMLibs.FECalls import getDBConn
from SiteFE.PolicyService.stateMachine import StateMachine


CONFIG = getConfig()
LOGGER = getLoggingObject(config=CONFIG, service='Helpers')
STATEMACHINE = StateMachine(CONFIG)


def deleteAll(sitename, deltaUID=None):
    """delete all deltas."""
    dbI = getDBConn('cancelalldeltas')
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        if deltaUID and delta['uid'] != deltaUID:
            continue
        print('Cancel %s' % delta['uid'])
        STATEMACHINE.stateChangerDelta(dbobj, 'remove', **delta)

if __name__ == "__main__":
    print(len(sys.argv))
    print(sys.argv)
    if len(sys.argv) > 2:
        deleteAll(sys.argv[1], sys.argv[2])
    else:
        deleteAll(sys.argv[1])
