#!/usr/bin/env python3
"""Database cleaner"""

import os
import traceback
from datetime import timedelta

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

    def cleanAuth(self):
        """Clean refresh_tokens"""
        olderthan = timedelta(days=int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "7"))).total_seconds()
        timestamp = int(getUTCnow() - olderthan)
        self.logger.info(f"Cleaning refresh_tokens older than {timestamp}")
        try:
            self.dbI.delete_comp("refresh_tokens", "expires_at", "<", timestamp)
        except pymysql.OperationalError as ex:
            self.logger.error(f"Operational error while cleaning refresh_tokens: {ex}")
            return

    def clean(self, dbtable, olderthan):
        """Clean the database"""
        self.logger.info(f"Cleaning {dbtable} for {self.sitename}")
        time_collumn = self.dbI.get_timestamp_column(dbtable)
        if not time_collumn:
            self.logger.info(f"No timestamp column found for {dbtable}. Skipping.")
            return

        deleted = self.dbI.delete_comp(dbtable, time_collumn, "<", int(getUTCnow() - olderthan))

        if deleted:
            self.logger.info(f"Deleted {deleted} rows from {dbtable}")

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
            "debugworkers",
        ]:
            self.logger.info(f"Cleaning {table}")
            try:
                self.clean(table, 7 * 86400)
            except Exception as e:
                self.logger.error(f"Error cleaning {table}: {e}")
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
        self.cleanAuth()
        self.logger.info("Cleaner finished")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="DBCleaner")
    gconfig = getGitConfig()
    siteName = getSiteNameFromConfig(gconfig)
    dbworker = DBCleaner(gconfig, siteName)
    dbworker.startwork()
