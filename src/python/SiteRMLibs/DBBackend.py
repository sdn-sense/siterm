#!/usr/bin/env python3
"""DB Backend for communication with database. Mainly we use mariadb, but in
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
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2019 California Institute of Technology
Date                    : 2019/05/01
"""
import os
import copy
import uuid
import random
import time
from contextlib import contextmanager
from datetime import datetime, timezone
import mariadb
from SiteRMLibs import dbcalls


def getUTCnow():
    """Get UTC Time."""
    return int(datetime.now(timezone.utc).timestamp())


def loadEnv(envFile='/etc/siterm-mariadb'):
    """Load Environment file and export variables"""
    if not os.path.isfile(envFile):
        return
    with open(envFile, 'r', encoding='utf-8') as fd:
        for line in fd:
            if line.startswith('#') or not line.strip():
                continue
            key, val = line.strip().split('=', 1)
            if not os.environ.get(key):
                os.environ[key] = val


class DBBackend():
    """Database Backend class."""
    def __init__(self):
        loadEnv()
        self.mpass = os.getenv('MARIA_DB_PASSWORD')
        self.muser = os.getenv('MARIA_DB_USER', 'root')
        self.mhost = os.getenv('MARIA_DB_HOST', 'localhost')
        self.mport = int(os.getenv('MARIA_DB_PORT', '3306'))
        self.mdb = os.getenv('MARIA_DB_DATABASE', 'sitefe')
        self.autocommit = os.getenv('MARIA_DB_AUTOCOMMIT', 'True') in ['True', 'true', '1']
        self.poolName = f"{os.getenv('MARIA_DB_POOLNAME', 'sitefe')}_{uuid.uuid4().hex}"
        if os.getenv('WORKERS') and os.getenv('THREADS'):
            self.poolSize = int(os.getenv('WORKERS')) * int(os.getenv('THREADS')) * 2
            self.connPool = None
        else:
            self.poolSize = int(os.getenv('MARIA_DB_POOLSIZE', '1'))
            self.connPool = self.__createConnPool()

    @staticmethod
    def __checkConnection(cursor):
        """Check if connection is available."""
        # Check that the connection was successful
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        if not result or result[0] != 1:
            raise mariadb.Error("Failed to establish a connection to the database.")

    def __createConnPool(self):
        """Create connection pool."""
        try:
            return mariadb.ConnectionPool(user=self.muser,
                                          password=self.mpass,
                                          host=self.mhost,
                                          port=self.mport,
                                          database=self.mdb,
                                          autocommit=self.autocommit,
                                          pool_name=self.poolName,
                                          pool_size=self.poolSize)
        except mariadb.Error as ex:
            print(f"Error creating connection pool: {ex}")
            raise ex

    @contextmanager
    def get_connection(self, maxretries=10, delay=0.1):
        """Open connection and cursor."""
        conn = None
        cursor = None
        attempt = 0
        while attempt < maxretries:
            try:
                if self.connPool is None:
                    conn = mariadb.connect(user=self.muser,
                                           password=self.mpass,
                                           host=self.mhost,
                                           port=self.mport,
                                           database=self.mdb,
                                           autocommit=self.autocommit)
                else:
                    # Use the connection pool to get a connection
                    conn = self.connPool.get_connection()
                cursor = conn.cursor()
                self.__checkConnection(cursor)
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
                return
            except mariadb.PoolError:
                attempt += 1
                wait = delay * (2 ** attempt) + random.uniform(0, 0.1)
                time.sleep(wait)
            except Exception as ex:
                print(f"Error establishing database connection: {ex}")
                raise ex
        raise mariadb.Error("Failed to establish a connection to the database after multiple attempts.")

    def createdb(self):
        """Create database."""
        for argname in dir(dbcalls):
            if argname.startswith('create_'):
                print(f'Call to create {argname}')
                with self.get_connection() as (_conn, cursor):
                    cursor.execute(getattr(dbcalls, argname))

    def cleandbtable(self, dbtable):
        """Clean only specific table if available"""
        for argname in dir(dbcalls):
            if argname == f'delete_{dbtable}':
                print(f'Call to clean from {argname}')
                with self.get_connection() as (_conn, cursor):
                    cursor.execute(getattr(dbcalls, argname))

    def cleandb(self):
        """Clean database."""
        for argname in dir(dbcalls):
            if argname.startswith('delete_'):
                print(f'Call to clean from {argname}')
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
            except mariadb.InterfaceError as ex:
                err = f'[GET]MariaDBInterfaceError. Ex: {ex}'
                raise mariadb.InterfaceError(err) from ex
            except mariadb.Error as ex:
                err = f'[GET]MariaDBError. Ex: {ex}'
                raise mariadb.Error(err) from ex
            except Exception as ex:
                err = f'[GET]MariaDB Exception. Ex: {ex}'
                raise Exception(err) from ex
        return 'OK', colname, alldata

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
            except mariadb.InterfaceError as ex:
                err = f'[INS]MariaDBInterfaceError. Ex: {ex}'
                conn.rollback()
                raise mariadb.InterfaceError(err) from ex
            except mariadb.Error as ex:
                err = f'[INS]MariaDBError. Ex: {ex}'
                conn.rollback()
                raise mariadb.Error(err) from ex
            except Exception as ex:
                err = f'[INS]MariaDB Exception. Ex: {ex}'
                conn.rollback()
                raise Exception(err) from ex
        return 'OK', '', lastID

    def execute_del(self, query, _values):
        """DELETE Execute."""
        with self.get_connection() as (conn, cursor):
            try:
                cursor.execute(query)
            except mariadb.InterfaceError as ex:
                err = f'[DEL]MariaDBInterfaceError. Ex: {ex}'
                conn.rollback()
                raise mariadb.InterfaceError(err) from ex
            except mariadb.Error as ex:
                err = f'[DEL]MariaDBError. Ex: {ex}'
                conn.rollback()
                raise mariadb.Error(err) from ex
            except Exception as ex:
                err = f'[DEL]MariaDB Exception. Ex: {ex}'
                conn.rollback()
                raise Exception(err) from ex
        return 'OK', '', ''

    def execute(self, query):
        """Execute query."""
        with self.get_connection() as (conn, cursor):
            try:
                cursor.execute(query)
            except mariadb.InterfaceError as ex:
                err = f'[EXC]MariaDBInterfaceError. Ex: {ex}'
                conn.rollback()
                raise mariadb.InterfaceError(err) from ex
            except mariadb.Error as ex:
                err = f'[EXC]MariaDBError. Ex: {ex}'
                conn.rollback()
                raise mariadb.Error(err) from ex
            except Exception as ex:
                err = f'[EXC]MariaDB Exception. Ex: {ex}'
                conn.rollback()
                raise Exception(err) from ex
        return 'OK', '', ''

class dbinterface():
    """Database interface."""
    def __init__(self, serviceName, config, sitename):
        self.config = config
        self.sitename = sitename
        self.serviceName = serviceName
        self.db = DBBackend()
        self.callStart = None
        self.callEnd = None

    def createdb(self):
        """Create Database."""
        self.db.createdb()

    def _setStartCallTime(self, calltype):
        """Set Call Start timer."""
        del calltype
        self.callStart = float(getUTCnow())

    def _setEndCallTime(self, _calltype, _callExit):
        """Set Call End timer."""
        self.callEnd = float(getUTCnow())

    @staticmethod
    def getcall(callaction, calltype):
        """Get call from ALL available ones."""
        callquery = ""
        try:
            callquery = getattr(dbcalls, f'{callaction}_{calltype}')
        except AttributeError as ex:
            err = f'Called {callaction}_{calltype}, but got exception {str(ex)}'
            raise AttributeError(err) from ex
        return callquery

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
                query += f'{item[0]} = "{item[1]}" '
        if orderby:
            query += f"ORDER BY {orderby[0]} {orderby[1]} "
        if limit:
            query += f"LIMIT {limit}"
        fullquery = f"{origquery} {query}"
        return self.db.execute_get(fullquery)

    def get(self, calltype, limit=None, search=None, orderby=None, mapping=True):
        """GET Call for APPs."""
        self._setStartCallTime(calltype)
        callExit, colname, dbout = self._caller(self.getcall('get', calltype), limit, orderby, search)
        self._setEndCallTime(calltype, callExit)
        out = []
        if mapping:
            for item in dbout:
                out.append(dict(list(zip(colname, list(item)))))
        else:
            out = copy.deepcopy(dbout)
        # Memory cleaning
        del dbout
        del colname
        del callExit
        return out

    # =====================================================
    #  HERE GOES INSERT CALLS
    # =====================================================

    def insert(self, calltype, values):
        """INSERT call for APPs."""
        self._setStartCallTime(calltype)
        retout = self.db.execute_ins(self.getcall('insert', calltype), values)
        self._setEndCallTime(calltype, retout[0])
        out = copy.deepcopy(retout)
        del retout
        return out

    # =====================================================
    #  HERE GOES UPDATE CALLS
    # =====================================================

    def update(self, calltype, values):
        """UPDATE Call for APPs."""
        self._setStartCallTime(calltype)
        retout = self.db.execute_ins(self.getcall('update', calltype), values)
        self._setEndCallTime(calltype, retout[0])
        out = copy.deepcopy(retout)
        del retout
        return out

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
                query += f'{item[0]} = "{item[1]}" '
        fullquery = f"{self.getcall('delete', calltype)} {query}"
        self._setStartCallTime(calltype)
        retout = self.db.execute_del(fullquery, None)
        self._setEndCallTime(calltype, retout[0])
        out = copy.deepcopy(retout)
        del retout
        return out

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
