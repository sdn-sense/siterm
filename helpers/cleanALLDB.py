#!/usr/bin/env python3
"""Clean all database"""
import sys
from DTNRMLibs.FECalls import getDBConn
from DTNRMLibs.MainUtilities import getVal

def cleanActive(sitename):
    dbI = getVal(getDBConn('Delete'), **{'sitename': sitename})
    dbI._clean('ALL', 'ALL')

if __name__ == "__main__":
    cleanActive(sys.argv[1])
