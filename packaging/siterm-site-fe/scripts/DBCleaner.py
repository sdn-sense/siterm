#!/usr/bin/env python3
"""Database cleaner"""
import time
import mariadb
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.GitConfig import getGitConfig

class DBCleaner:
    """DBCleaner class"""
    def __init__(self):
        self.config = getGitConfig()
        self.sites = self.config.get('general', 'sites')
        for site in self.sites:
            self.dbI = {}
            self.dbI[site] = getVal(getDBConn('List', self), **{'sitename': site})

    def clean(self, dbtable, olderthan):
        """Clean the database"""
        for site in self.sites:
            print(f"Cleaning {dbtable} for {site}")
            try:
                data = self.dbI[site].get(dbtable, limit=100, orderby=["insertdate", "ASC"])
            except mariadb.OperationalError:
                data = self.dbI[site].get(dbtable, limit=100, orderby=["updatedate", "ASC"])
            for item in data:
                if 'updatedate' in item:
                    if item['updatedate'] < int(getUTCnow() - olderthan):
                        print(f"Deleting {item['id']} from {dbtable}")
                        self.dbI[site].delete(dbtable, [["id", item["id"]]])
                elif 'insertdate' in item:
                    if item['insertdate'] < int(getUTCnow() - olderthan):
                        print(f"Deleting {item['id']} from {dbtable}")
                        self.dbI[site].delete(dbtable, [["id", item["id"]]])
                else:
                    print(f"Item {item['id']} from {dbtable} does not have timestamp. Ignoring")


    def start(self):
        """Start the cleaner"""
        print('Starting cleaner')
        for table in ['debugrequests', 'deltas', 'deltatimestates', 'hosts', 'models', 'servicestates']:
            self.clean(table, 86400*7)
        print('Cleaner finished')

if __name__ == "__main__":
    dbcleaner = DBCleaner()
    while True:
        try:
            dbcleaner.start()
        except Exception as err:
            print(f"Error in DB Cleaner: {err}")
        print('Sleeping for 24 hour before next cleaning cycle')
        time.sleep(86400)
