#!/usr/bin/env python3
"""Clean all database"""
import sys
from DTNRMLibs.MainUtilities import getDBConn
from DTNRMLibs.MainUtilities import getVal

def cleanDB(sitename):
    """Clean All DB"""
    dbI = getVal(getDBConn('Delete'), **{'sitename': sitename})
    dbI._clean('ALL', 'ALL')
    dbI._cleantable('servicestates', '')
    #dbI._clean('ALL', 'ALL')

if __name__ == "__main__":
    cleanDB(sys.argv[1])
