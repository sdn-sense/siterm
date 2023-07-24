#!/usr/bin/env python3
"""Clean all database"""
import sys
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getVal

def cleanDB(sitename):
    """Clean All DB"""
    dbI = getVal(getDBConn('Delete'), **{'sitename': sitename})
    dbI._clean('ALL', 'ALL')
    dbI._cleantable('servicestates', '')

if __name__ == "__main__":
    cleanDB(sys.argv[1])
