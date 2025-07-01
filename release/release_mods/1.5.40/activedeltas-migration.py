#!/usr/bin/env python3
"""Database upgrade to use new activeDeltas table format."""
# This script migrates the old activeDeltas table to a new format.
# Requirements before running:
# 1. Ensure the database is running and accessible and lock it for new writes, reads.
#    touch /tmp/siterm-mariadb-init
# 2. Ensure the old activeDeltas table exists.
#   mysql -u root
# 3. Inside mysql shell:
#   USE siterm;
#   CREATE TABLE activeDeltas_old1540 AS SELECT * FROM activeDeltas;
#   DROP TABLE IF EXISTS activeDeltas;
#   CREATE TABLE activeDeltas (id INT AUTO_INCREMENT, insertdate INT NOT NULL, updatedate INT NOT NULL, output JSON NOT NULL, PRIMARY KEY (id));
#   commit;
#   exit;
# Run this script to migrate the data:

from time import sleep
import json
import re
import pymysql
from SiteRMLibs.DBBackend import dbinterface
from SiteRMLibs import __version__ as runningVersion

def evaldict(inputDict):
    """Eval dict of old format"""
    if not inputDict:
        return {}
    if isinstance(inputDict, (list, dict)):
        return inputDict
    if isinstance(inputDict, bytes):
        inputDict = inputDict.decode("utf-8", errors="replace")
    if not isinstance(inputDict, str):
        raise ValueError("Input must be a string")
    try:
        return json.loads(inputDict)
    except Exception:
        inputDict = re.sub(r"'", '"', inputDict)
        inputDict = re.sub(r",(\s*[}\]])", r"\1", inputDict)
        return json.loads(inputDict)


class DBStarter:
    """Database starter class"""
    def __init__(self):
        self.db = dbinterface('DBINIT', None, "MAIN")

    def dbready(self):
        """Check if the database is ready"""
        try:
            self.db.db.execute("SELECT 1")
        except pymysql.OperationalError as ex:
            print(f"Error executing SQL: {ex}")
            return False
        return True

    def start(self):
        """Start the database creation"""
        while not self.dbready():
            print("Database not ready, waiting for 1 second. See error above. If continous, check the mariadb process.")
            sleep(1)
        # Get all from backup
        out = self.db.db.execute_get("SELECT insertdate, updatedate, output FROM activeDeltas_old1540")

        for insertdate, updatedate, output in out:
            try:
                parsed_output = evaldict(output)
                cleaned_output = json.dumps(parsed_output)
                self.db.db.execute(
                    f"INSERT INTO activeDeltas_new (insertdate, updatedate, output) VALUES ({insertdate}, {updatedate}, '{cleaned_output}')"
                )
            except Exception as ex:
                print(f"Skipping row due to parse error: {ex}")
                continue
        print("Migration complete.")

if __name__ == "__main__":
    dbclass = DBStarter()
    dbclass.start()
