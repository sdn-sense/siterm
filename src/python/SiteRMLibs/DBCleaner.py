#!/usr/bin/env python3
"""Database cleaner"""
import mariadb
from SiteRMLibs.MainUtilities import (getDBConn, getLoggingObject, getVal, getUTCnow)
from SiteRMLibs.GitConfig import getGitConfig


class DBCleaner:
    """DBCleaner class"""
    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="DBCleaner")
        self.dbI = getVal(getDBConn("DBWorker", self), **{"sitename": self.sitename})
        self.nextRun = int(getUTCnow() - 1) # Make sure runs first time

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        # Just a place holder (no need to change anything for DBCleaner)
        return

    def clean(self, dbtable, olderthan):
        """Clean the database"""
        print(f"Cleaning {dbtable} for {self.sitename}")
        try:
            data = self.dbI.get(dbtable, limit=100, orderby=["insertdate", "ASC"])
        except mariadb.OperationalError:
            data = self.dbI.get(dbtable, limit=100, orderby=["updatedate", "ASC"])
        for item in data:
            if 'updatedate' in item:
                if item['updatedate'] < int(getUTCnow() - olderthan):
                    print(f"Deleting {item['id']} from {dbtable}")
                    self.dbI.delete(dbtable, [["id", item["id"]]])
            elif 'insertdate' in item:
                if item['insertdate'] < int(getUTCnow() - olderthan):
                    print(f"Deleting {item['id']} from {dbtable}")
                    self.dbI.delete(dbtable, [["id", item["id"]]])
            else:
                print(f"Item {item['id']} from {dbtable} does not have timestamp. Ignoring")

    def startwork(self):
        """Start the cleaner"""
        if self.nextRun > getUTCnow():
            return
        self.nextRun = int(getUTCnow() + 7200) # Run every 2 hours
        print('Starting cleaner')
        for table in ['debugrequests', 'deltas', 'deltatimestates', 'hosts', 'models', 'servicestates', 'states',
                      'hoststates', 'hoststateshistory', 'parsed', 'switch', 'snmpmon', 'serviceaction', 'activeDeltas',
                      'instancestartend', 'deltasusertracking']:
            print(f"Cleaning {table}")
            self.clean(table, 7*86400)
        print('Cleaner finished')


if __name__ == "__main__":
    logObj = getLoggingObject(logType='StreamLogger', service='DBCleaner')
    gconfig = getGitConfig()
    for siteName in gconfig.get("general", "sites"):
        dbworker = DBCleaner(gconfig, siteName)
        dbworker.startwork()
