#!/usr/bin/env python
import sys
from DTNRMLibs.MainUtilities import getVal
from SiteFE.PolicyService.stateMachine import StateMachine
from DTNRMLibs.MainUtilities import getConfig, getLogger, getStreamLogger
from DTNRMLibs.FECalls import getDBConn

LOGGER = getStreamLogger()
config = getConfig(["/etc/dtnrm-site-fe.conf"])
stateMachine = StateMachine(LOGGER)

def deleteAll(sitename, deltaUID=None):
    dbI = getDBConn()
    dbobj = getVal(dbI, sitename=sitename)
    for delta in dbobj.get('deltas'):
        if deltaUID:
            if delta['uid'] != deltaUID:
                continue
        print 'Cancel %s' % delta['uid']
        stateMachine._stateChangerDelta(dbobj, 'remove', **delta)

if __name__ == "__main__":
    print len(sys.argv)
    print sys.argv
    if len(sys.argv) > 2:
        deleteAll(sys.argv[1], sys.argv[2])
    else:
        deleteAll(sys.argv[1])
