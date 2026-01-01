#!/usr/bin/env python3
"""Database cleaner"""

import traceback

import pymysql
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
)


class DBCleaner:
    """DBCleaner class"""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="DBCleaner")
        self.dbI = getVal(getDBConn("DBWorker", self), **{"sitename": self.sitename})
        self.nextRun = int(getUTCnow() - 1)  # Make sure runs first time

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        # Just a place holder (no need to change anything for DBCleaner)
        return

    def clean(self, dbtable, olderthan):
        """Clean the database"""
        self.logger.info(f"Cleaning {dbtable} for {self.sitename}")
        try:
            data = self.dbI.get(dbtable, limit=10, orderby=["insertdate", "ASC"])
        except pymysql.OperationalError:
            data = self.dbI.get(dbtable, limit=10, orderby=["updatedate", "ASC"])
        for item in data:
            if "updatedate" in item:
                if item["updatedate"] < int(getUTCnow() - olderthan):
                    self.logger.info(f"Deleting {item['id']} from {dbtable}")
                    self.dbI.delete(dbtable, [["id", item["id"]]])
            elif "insertdate" in item:
                if item["insertdate"] < int(getUTCnow() - olderthan):
                    self.logger.info(f"Deleting {item['id']} from {dbtable}")
                    self.dbI.delete(dbtable, [["id", item["id"]]])
            else:
                self.logger.info(f"Item {item['id']} from {dbtable} does not have timestamp. Ignoring")

    def startwork(self):
        """Start the cleaner"""
        if self.nextRun > getUTCnow():
            return
        self.nextRun = int(getUTCnow() + 360)  # Run every 5 minutes
        self.logger.info("Starting cleaner")
        for table in [
            "debugrequests",
            "deltas",
            "deltatimestates",
            "hosts",
            "models",
            "servicestates",
            "states",
            "hoststates",
            "hoststateshistory",
            "switch",
            "snmpmon",
            "serviceaction",
            "activeDeltas",
            "instancestartend",
            "deltasusertracking",
        ]:
            self.logger.info(f"Cleaning {table}")
            try:
                self.clean(table, 7 * 86400)
            except Exception as e:
                self.logger.error(f"Error cleaning {table}: {e}")
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
        self.logger.info("Cleaner finished")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="DBCleaner")
    gconfig = getGitConfig()
    siteName = getSiteNameFromConfig(gconfig)
    dbworker = DBCleaner(gconfig, siteName)
    dbworker.startwork()
