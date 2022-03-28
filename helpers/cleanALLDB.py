#!/usr/bin/env python3
"""Clean all database"""
import sys
import pprint
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal, evaldict, getUTCnow

def cleanActive(sitename):
    dbI = getVal(getDBConn('Delete'), **{'sitename': sitename})
    activeDeltas = dbI._clean('ALL', 'ALL')

if __name__ == "__main__":
    cleanActive(sys.argv[1])
