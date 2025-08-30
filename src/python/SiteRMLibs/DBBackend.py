#!/usr/bin/env python3
"""DB Backend for communication with database. Mainly we use MySQL, but in
near future can be any other database.

Copyright 2019 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2019 California Institute of Technology
Date                    : 2019/05/01
"""
import os
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone

import pymysql
from SiteRMLibs import dbcalls


def getUTCnow():
    """Get UTC Time."""
    return int(datetime.now(timezone.utc).timestamp())


def loadEnvFile(filepath="/etc/environment"):
    """Loads environment variables from a file if"""
    if not os.path.isfile(filepath):
        return
    try:
        with open(filepath, "r", encoding="utf-8") as fd:
            for line in fd:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("export "):
                    line = line[len("export ") :]
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()
    except Exception as ex:
        exc = traceback.format_exc()
        print(f"Exception loading environment file {filepath}. Trace: {exc}, Error: {ex}")


class DBBackend:
    """Database Backend class."""

    def __init__(self):
        loadEnvFile()
        self.mpass = os.getenv("MARIA_DB_PASSWORD")
        self.muser = os.getenv("MARIA_DB_USER", "root")
        self.mhost = os.getenv("MARIA_DB_HOST", "localhost")
        self.mport = int(os.getenv("MARIA_DB_PORT", "3306"))
        self.mdb = os.getenv("MARIA_DB_DATABASE", "sitefe")
        self.charset = os.getenv("MARIA_DB_CHARSET", "utf8mb4")
        self.autocommit = os.getenv("MARIA_DB_AUTOCOMMIT", "True") in [
            "True",
            "true",
            "1",
        ]

    @staticmethod
    def checkConnection(cursor):
        """Check if connection is available."""
        # Check that the connection was successful
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if not result or result[0] != 1:
            raise pymysql.MySQLError("Failed to establish a connection to the database.")

    @contextmanager
    def get_connection(self):
        """Open connection and cursor."""
        conn = None
        cursor = None
        try:
            conn = pymysql.connect(
                user=self.muser,
                password=self.mpass,
                host=self.mhost,
                port=self.mport,
                database=self.mdb,
                autocommit=self.autocommit,
                charset=self.charset,
                cursorclass=pymysql.cursors.Cursor,
            )
            cursor = conn.cursor()
            self.checkConnection(cursor)
            try:
                yield conn, cursor
            finally:
                if cursor:
                    try:
                        cursor.close()
                    except Exception:
                        pass
                if conn:
                    try:
                        conn.close()
                    except Exception:
                        pass
        except Exception as ex:
            exc = traceback.format_exc()
            print(f"Error establishing database connection: {ex}. Trace: {exc}")
            raise ex

    def createdb(self):
        """Create database."""
        for argname in dir(dbcalls):
            if argname.startswith("create_"):
                print(f"Call to create {argname}")
                with self.get_connection() as (_conn, cursor):
                    cursor.execute(getattr(dbcalls, argname))

    def cleandbtable(self, dbtable):
        """Clean only specific table if available"""
        for argname in dir(dbcalls):
            if argname == f"delete_{dbtable}":
                print(f"Call to clean from {argname}")
                with self.get_connection() as (_conn, cursor):
                    cursor.execute(getattr(dbcalls, argname))

    def cleandb(self):
        """Clean database."""
        for argname in dir(dbcalls):
            if argname.startswith("delete_"):
                print(f"Call to clean from {argname}")
                with self.get_connection() as (_conn, cursor):
                    cursor.execute(getattr(dbcalls, argname))

    def execute_get(self, query):
        """GET Execution."""
        alldata = []
        colname = []
        with self.get_connection() as (_conn, cursor):
            try:
                cursor.execute(query)
                colname = [tup[0] for tup in cursor.description]
                alldata = cursor.fetchall()
            except pymysql.InterfaceError as ex:
                exc = traceback.format_exc()
                err = f"[GET]MySQLInterfaceError. Ex: {ex}. Trace: {exc}"
                raise pymysql.InterfaceError(err) from ex
            except pymysql.Error as ex:
                exc = traceback.format_exc()
                err = f"[GET]MySQLError. Ex: {ex}. Trace: {exc}"
                raise pymysql.Error(err) from ex
            except Exception as ex:
                exc = traceback.format_exc()
                err = f"[GET]MySQL Exception. Ex: {ex}. Trace: {exc}"
                raise Exception(err) from ex
        return "OK", colname, alldata

    def execute_ins(self, query, values):
        """INSERT Execute."""
        lastID = -1
        with self.get_connection() as (conn, cursor):
            try:
                for idx, val in enumerate(values):
                    cursor.execute(query, val)
                    lastID = cursor.lastrowid
                    if idx > 0 and idx % 100 == 0:
                        conn.commit()
                conn.commit()
            except pymysql.InterfaceError as ex:
                exc = traceback.format_exc()
                err = f"[INS]MySQLInterfaceError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.InterfaceError(err) from ex
            except pymysql.Error as ex:
                exc = traceback.format_exc()
                err = f"[INS]MySQLError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.Error(err) from ex
            except Exception as ex:
                exc = traceback.format_exc()
                err = f"[INS]MySQL Exception. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise Exception(err) from ex
        return "OK", "", lastID

    def execute_del(self, query, _values):
        """DELETE Execute."""
        with self.get_connection() as (conn, cursor):
            try:
                cursor.execute(query)
            except pymysql.InterfaceError as ex:
                exc = traceback.format_exc()
                err = f"[DEL]MySQLInterfaceError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.InterfaceError(err) from ex
            except pymysql.Error as ex:
                exc = traceback.format_exc()
                err = f"[DEL]MySQLError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.Error(err) from ex
            except Exception as ex:
                exc = traceback.format_exc()
                err = f"[DEL]MySQL Exception. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise Exception(err) from ex
        return "OK", "", ""

    def execute(self, query):
        """Execute query."""
        with self.get_connection() as (conn, cursor):
            try:
                cursor.execute(query)
            except pymysql.InterfaceError as ex:
                exc = traceback.format_exc()
                err = f"[EXC]MySQLInterfaceError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.InterfaceError(err) from ex
            except pymysql.Error as ex:
                exc = traceback.format_exc()
                err = f"[EXC]MySQLError. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise pymysql.Error(err) from ex
            except Exception as ex:
                exc = traceback.format_exc()
                err = f"[EXC]MySQL Exception. Ex: {ex}. Trace: {exc}"
                conn.rollback()
                raise Exception(err) from ex
        return "OK", "", ""


class dbinterface:
    """Database interface."""

    def __init__(self, serviceName="", config="", sitename=""):
        # TOOD: All the rest should remove use of those params
        self.config = config
        self.sitename = sitename
        self.serviceName = serviceName
        self.db = DBBackend()

    def createdb(self):
        """Create Database."""
        self.db.createdb()

    @staticmethod
    def getcall(callaction, calltype):
        """Get call from ALL available ones."""
        callquery = ""
        try:
            callquery = getattr(dbcalls, f"{callaction}_{calltype}")
        except AttributeError as ex:
            exc = traceback.format_exc()
            err = f"Called {callaction}_{calltype}, but got exception {str(ex)}. Trace: {exc}"
            raise AttributeError(err) from ex
        return callquery

    def isDBReady(self):
        """Check if database is ready."""
        try:
            with self.db.get_connection() as (_conn, cursor):
                self.db.checkConnection(cursor)
            return True
        except pymysql.MySQLError as ex:
            exc = traceback.format_exc()
            print(f"Database is not ready. Error: {ex}. Trace: {exc}")
            return False
        except Exception as ex:
            exc = traceback.format_exc()
            print(f"Unexpected error while checking database readiness: {ex}. Trace: {exc}")
            return False

    # =====================================================
    #  HERE GOES GET CALLS
    # =====================================================
    def _caller(self, origquery, limit=None, orderby=None, search=None):
        """Modifies get call and include WHER/ORDER/LIMIT."""
        query = ""
        if search:
            first = True
            for item in search:
                if not item:
                    continue
                if first:
                    query = "WHERE "
                    first = False
                else:
                    query += "AND "
                # if item len == 2, then it is =
                if len(item) == 2:
                    query += f'{item[0]} = "{str(item[1])}" '
                elif len(item) == 3:
                    query += f'{item[0]} {item[1]} "{str(item[2])}" '
        if orderby:
            query += f"ORDER BY {orderby[0]} {orderby[1]} "
        if limit:
            query += f"LIMIT {limit}"
        fullquery = f"{origquery} {query}"
        return self.db.execute_get(fullquery)

    def get(self, calltype, limit=None, search=None, orderby=None, mapping=True):
        """GET Call for APPs."""
        # pylint: disable=too-many-arguments
        _callExit, colname, dbout = self._caller(self.getcall("get", calltype), limit, orderby, search)
        out = []
        if mapping:
            for item in dbout:
                out.append(dict(list(zip(colname, list(item)))))
            return out
        return dbout

    # =====================================================
    #  HERE GOES INSERT CALLS
    # =====================================================

    def insert(self, calltype, values):
        """INSERT call for APPs."""
        return self.db.execute_ins(self.getcall("insert", calltype), values)

    # =====================================================
    #  HERE GOES UPDATE CALLS
    # =====================================================

    def update(self, calltype, values):
        """UPDATE Call for APPs."""
        return self.db.execute_ins(self.getcall("update", calltype), values)

    # =====================================================
    #  HERE GOES DELETE CALLS
    # =====================================================

    def delete(self, calltype, values):
        """DELETE Call for APPs."""
        query = ""
        if values:
            first = True
            for item in values:
                if first:
                    query = "WHERE "
                else:
                    query += "AND "
                first = False
                query += f'{item[0]} = "{str(item[1])}" '
        fullquery = f"{self.getcall('delete', calltype)} {query}"
        return self.db.execute_del(fullquery, None)

    # =====================================================
    #  HERE GOES CLEAN CALLS
    # =====================================================
    def _clean(self, calltype, values):
        """Database Clean Up"""
        del calltype, values
        self.db.cleandb()

    def _cleantable(self, calltype, values):
        """Clean specific table"""
        del values
        self.db.cleandbtable(calltype)
