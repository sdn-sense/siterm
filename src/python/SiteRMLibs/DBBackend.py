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

    @staticmethod
    def destroy(conn, cursor):
        """Destroy connection."""
        if cursor:
            cursor.close()
        if conn:
            conn.close()

    def _createdb(self):
        """Create database."""
        conn, cursor = self.initialize()
        for argname in dir(dbcalls):
            if argname.startswith('create_'):
                print(f'Call to create {argname}')
                cursor.execute(getattr(dbcalls, argname))
        conn.commit()
        self.destroy(conn, cursor)

    def _cleandbtable(self, dbtable):
        """Clean only specific table if available"""
        conn, cursor = self.initialize()
        for argname in dir(dbcalls):
            if argname == f'delete_{dbtable}':
                print(f'Call to clean from {argname}')
                cursor.execute(getattr(dbcalls, argname))
        conn.commit()
        self.destroy(conn, cursor)

    def _cleandb(self):
        """Clean database."""
        conn, cursor = self.initialize()
        for argname in dir(dbcalls):
            if argname.startswith('delete_'):
                print(f'Call to clean from {argname}')
                cursor.execute(getattr(dbcalls, argname))
        conn.commit()
        self.destroy(conn, cursor)

    def initialize(self):
        """Initialize mariadb connection."""
        conn = mariadb.connect(user=self.muser,
                               password=self.mpass,
                               host=self.mhost,
                               port=self.mport,
                               database=self.mdb)
        cursor = conn.cursor()
        return conn, cursor

    def execute_get(self, query):
        """GET Execution."""
        alldata = []
        colname = []
        conn, cursor = self.initialize()
        try:
            cursor.execute(query)
            colname = [tup[0] for tup in cursor.description]
            alldata = cursor.fetchall()
        except Exception as ex:
            raise ex
        finally:
            self.destroy(conn, cursor)
        return 'OK', colname, alldata

    def execute_ins(self, query, values):
        """INSERT Execute."""
        lastID = -1
        conn, cursor = self.initialize()
        try:
            for item in values:
                cursor.execute(query, item)
                lastID = cursor.lastrowid
            conn.commit()
        except mariadb.Error as ex:
            print(f'MariaDBError. Ex: {ex}')
            conn.rollback()
            raise ex
        except Exception as ex:
            print(f'Got Exception {ex} ')
            conn.rollback()
            raise ex
        finally:
            self.destroy(conn, cursor)
        return 'OK', '', lastID

    def execute_del(self, query, values):
        """DELETE Execute."""
        del values
        conn, cursor = self.initialize()
        try:
            cursor.execute(query)
            conn.commit()
        except Exception as ex:
            print(f'Got Exception {ex} ')
            conn.rollback()
            raise ex
        finally:
            self.destroy(conn, cursor)
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

    def _setStartCallTime(self, calltype):
        """Set Call Start timer."""
        del calltype
        self.callStart = float(getUTCnow())

    def _setEndCallTime(self, calltype, callExit):
        """Set Call End timer."""
        self.callEnd = float(getUTCnow())

    @staticmethod
    def getcall(callaction, calltype):
        """Get call from ALL available ones."""
        callquery = ""
        try:
            callquery = getattr(dbcalls, f'{callaction}_{calltype}')
        except AttributeError as ex:
            print('Called %s_%s, but got exception %s', callaction, calltype, ex)
            raise ex
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
            return out
        return dbout

    # =====================================================
    #  HERE GOES INSERT CALLS
    # =====================================================

    def insert(self, calltype, values):
        """INSERT call for APPs."""
        self._setStartCallTime(calltype)
        out = self.db.execute_ins(self.getcall('insert', calltype), values)
        self._setEndCallTime(calltype, out[0])
        return out

    # =====================================================
    #  HERE GOES UPDATE CALLS
    # =====================================================

    def update(self, calltype, values):
        """UPDATE Call for APPs."""
        self._setStartCallTime(calltype)
        out = self.db.execute_ins(self.getcall('update', calltype), values)
        self._setEndCallTime(calltype, out[0])
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
        out = self.db.execute_del(fullquery, None)
        self._setEndCallTime(calltype, out[0])
        return out

    # =====================================================
    #  HERE GOES CLEAN CALLS
    # =====================================================
    def _clean(self, calltype, values):
        """Database Clean Up"""
        del calltype, values
        self.db._cleandb()

    def _cleantable(self, calltype, values):
        """Clean specific table"""
        del values
        self.db._cleandbtable(calltype)
