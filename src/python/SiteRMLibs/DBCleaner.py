#!/usr/bin/env python3
"""Database cleaner"""

import os
import traceback
from datetime import timedelta

import pymysql
from SiteRMLibs.DefaultParams import (
    DB_OPTIMIZE_INTERVAL,
    DB_OPTIMIZE_TABLES,
    DB_RETENTION,
    FE_SHARDED_COMPONENTS,
    MODEL_MAX_COUNT,
)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
)

# Tables cleaned by a plain update/insert timestamp cut (retention from DB_RETENTION)
TIMESTAMP_TABLES = [
    "debugrequests",
    "deltas",
    "deltatimestates",
    "hosts",
    "services",
    "servicestates",
    "states",
    "hoststates",
    "hoststateshistory",
    "switch",
    "snmpmon",
    "bgpmon",
    "serviceaction",
    "bgpforcerescan",
    "activeDeltas",
    "instancestartend",
    "deltasusertracking",
    "deltaidempotency",
    "debugworkers",
    "deltarequests",
]


class DBCleaner:
    """Delete rows past their retention so the database stays bounded."""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="DBCleaner")
        self.dbI = getVal(getDBConn("DBWorker", self), **{"sitename": self.sitename})
        self.nextRun = int(getUTCnow() - 1)  # Make sure runs first time
        self.nextOptimize = int(getUTCnow() + DB_OPTIMIZE_INTERVAL)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        # Just a place holder (no need to change anything for DBCleaner)
        return

    def retention(self, key):
        """Return retention seconds for a table or kv namespace (config overrides defaults)."""
        override = self.config.get("daemoncontrols", "DBCleaner", {}).get("retention", {}) if self.config else {}
        return int(override.get(key, DB_RETENTION[key]))

    def cleanAuth(self):
        """Clean refresh_tokens"""
        olderthan = timedelta(hours=int(os.environ.get("REFRESH_TOKEN_TTL_HOURS", "12"))).total_seconds()
        timestamp = int(getUTCnow() - olderthan)
        self.logger.info(f"Cleaning refresh_tokens older than {timestamp}")
        try:
            self.dbI.delete_comp("refresh_tokens", "expires_at", "<", timestamp)
        except pymysql.OperationalError as ex:
            self.logger.error(f"Operational error while cleaning refresh_tokens: {ex}")
            return

    def clean(self, dbtable, olderthan):
        """Delete rows of a table older than olderthan seconds (by update/insert timestamp)."""
        time_collumn = self.dbI.get_timestamp_column(dbtable)
        if not time_collumn:
            self.logger.info(f"No timestamp column found for {dbtable}. Skipping.")
            return
        deleted = self.dbI.delete_comp(dbtable, time_collumn, "<", int(getUTCnow() - olderthan))
        if deleted:
            self.logger.info(f"Deleted {deleted} rows from {dbtable}")

    def cleanSpecial(self):
        """Clean tables whose retention is not a plain timestamp cut."""
        now = getUTCnow()
        out = {}
        # Models: time window and count cap (latest always kept), then content nobody refers to.
        out["models"] = self.dbI.modeltrim(self.retention("models"), MODEL_MAX_COUNT)
        out["modelcontent"] = self.dbI.modelcontentcleanup()
        out["leases"] = self.dbI.deletesearch("leases", [["expires_at", "<", now - self.retention("leases")]])
        # Scaled FE replicas report under their own instance name; drop the ones that went away.
        out["servicestates_instance"] = self.dbI.deletesearch(
            "servicestates",
            [["hostname", "!=", "default"], ["servicename", "in", FE_SHARDED_COMPONENTS + ["SwitchWorker"]], ["updatedate", "<", now - self.retention("servicestates_instance")]],
        )
        for key in DB_RETENTION:
            if key.startswith("kv:"):
                out[key] = self.dbI.deletesearch("kvstore", [["namespace", key[3:]], ["updatedate", "<", now - self.retention(key)]])
        for key, deleted in out.items():
            if deleted:
                self.logger.info(f"Deleted {deleted} rows from {key}")

    def optimize(self):
        """Rebuild large-row tables once a day so freed space goes back to the filesystem."""
        if self.nextOptimize > getUTCnow():
            return
        self.nextOptimize = int(getUTCnow() + DB_OPTIMIZE_INTERVAL)
        try:
            done = self.dbI.optimizetables(DB_OPTIMIZE_TABLES)
            if done:
                self.logger.info(f"Optimized tables: {done}")
        except Exception as ex:  # pylint: disable=broad-except
            self.logger.error(f"Error optimizing tables: {ex}")

    def startwork(self):
        """Start the cleaner"""
        if self.nextRun > getUTCnow():
            return
        self.nextRun = int(getUTCnow() + 300)  # Run every 5 minutes
        self.logger.info("Starting cleaner")
        for table in TIMESTAMP_TABLES:
            try:
                self.clean(table, self.retention(table))
            except Exception as e:  # pylint: disable=broad-except
                self.logger.error(f"Error cleaning {table}: {e}")
                self.logger.error(f"Full traceback: {traceback.format_exc()}")
        try:
            self.cleanSpecial()
        except Exception as e:  # pylint: disable=broad-except
            self.logger.error(f"Error in special cleanup: {e}")
            self.logger.error(f"Full traceback: {traceback.format_exc()}")
        self.cleanAuth()
        self.optimize()
        self.logger.info("Cleaner finished")


if __name__ == "__main__":
    logObj = getLoggingObject(logType="StreamLogger", service="DBCleaner")
    gconfig = getGitConfig()
    siteName = getSiteNameFromConfig(gconfig)
    dbworker = DBCleaner(gconfig, siteName)
    dbworker.startwork()
