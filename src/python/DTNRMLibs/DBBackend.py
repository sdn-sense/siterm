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
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2019 California Institute of Technology
Date                    : 2019/05/01
"""
from __future__ import print_function
import os
import time
import mariadb
import DTNRMLibs.dbcalls as dbcalls


class DBBackend():
    """Database Backend class."""
    def __init__(self):
        self.mpass = os.getenv('MARIA_DB_PASSWORD')
        self.muser = os.getenv('MARIA_DB_USER', 'root')
        self.mhost = os.getenv('MARIA_DB_HOST', 'localhost')
        self.mport = int(os.getenv('MARIA_DB_PORT', '3306'))
        self.mdb = os.getenv('MARIA_DB_DATABASE', 'sitefe')
        self.conn = None
        self.cursor = None

    def destroy(self):
        """Destroy connection."""
        if self.conn:
            self.conn.close()
        self.conn = None
        self.cursor = None

    def _createdb(self):
        """Create database."""
        self.initialize()
        for argname in dir(dbcalls):
            if argname.startswith('create_'):
                print('Call to create %s' % argname)
                self.cursor.execute(getattr(dbcalls, argname))
        self.conn.commit()
        self.destroy()

    def initialize(self):
        """Initialize mariadb connection."""
        if not self.conn:
            self.conn = mariadb.connect(user=self.muser,
                                        password=self.mpass,
                                        host=self.mhost,
                                        port=self.mport,
                                        database=self.mdb)
        if not self.cursor:
            self.cursor = self.conn.cursor()

    def execute_get(self, query):
        """GET Execution."""
        alldata = []
        colname = []
        try:
            self.initialize()
            self.cursor.execute(query)
            colname = [tup[0] for tup in self.cursor.description]
            alldata = self.cursor.fetchall()
        except Exception as ex:
            raise ex
        finally:
            self.destroy()
        return 'OK', colname, alldata

    def execute_ins(self, query, values):
        """INSERT Execute."""
        try:
            self.initialize()
            for item in values:
                self.cursor.execute(query, item)
            self.conn.commit()
        except mariadb.Error as ex:
            print('MariaDBError. Ex: %s' % ex)
            self.conn.rollback()
            raise ex
        except Exception as ex:
            print('Got Exception %s ' % ex)
            self.conn.rollback()
            raise ex
        finally:
            self.destroy()
        return 'OK', '', ''

    def execute_del(self, query, values):
        """DELETE Execute."""
        try:
            self.initialize()
            self.cursor.execute(query)
            self.conn.commit()
        except Exception as ex:
            print('Got Exception %s ' % ex)
            self.conn.rollback()
            self.destroy()
            raise ex
        finally:
            self.destroy()
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
        self.callStart = float(time.time())

    def _setEndCallTime(self, calltype, callExit):
        """Set Call End timer."""
        self.callEnd = float(time.time())
        self._calldiff(calltype, callExit)

    def _calldiff(self, calltype, callExit):
        """Log timing for call."""
        diff = self.callEnd - self.callStart
        msg = "DB: %s %s %s %s" % (self.serviceName, calltype, str(diff), callExit)
        print(msg)

    def getcall(self, callaction, calltype):
        """Get call from ALL available ones."""
        callquery = ""
        try:
            callquery = getattr(dbcalls, '%s_%s' % (callaction, calltype))
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
                if first:
                    query = "WHERE "
                    first = False
                else:
                    query += "AND "
                query += '%s = "%s" ' % (item[0], item[1])
        if orderby:
            query += "ORDER BY %s %s " % (orderby[0], orderby[1])
        if limit:
            query += "LIMIT %s" % limit
        fullquery = "%s %s" % (origquery, query)
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
        callExit, _, _ = self.db.execute_ins(self.getcall('insert', calltype), values)
        self._setEndCallTime(calltype, callExit)

    # =====================================================
    #  HERE GOES UPDATE CALLS
    # =====================================================

    def update(self, calltype, values):
        """UPDATE Call for APPs."""
        self._setStartCallTime(calltype)
        callExit, _, _ = self.db.execute_ins(self.getcall('update', calltype), values)
        self._setEndCallTime(calltype, callExit)

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
                query += '%s = "%s" ' % (item[0], item[1])
        fullquery = "%s %s" % (self.getcall('delete', calltype), query)
        self._setStartCallTime(calltype)
        callExit, _, _ = self.db.execute_del(fullquery, None)
        self._setEndCallTime(calltype, callExit)
