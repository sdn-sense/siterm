#!/usr/bin/env python
"""
DB Backend for communication with database. Mainly we use sqlite3,
but in near future can be any other database

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
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2019 California Institute of Technology
Date			: 2019/05/01
"""

import os
import sqlite3
import DTNRMLibs.dbcalls as dbcalls

class DBBackend(object):
    """ Database Backend class """
    def __init__(self, configFile):
        self.dbfile = configFile
        createdb = False
        if not os.path.isfile(self.dbfile):
            createdb = True
        self.conn = sqlite3.connect(self.dbfile)
        self.cursor = self.conn.cursor()
        if createdb:
            self._createdb()

    def destroy(self):
        """ Destroy connection """
        if self.conn:
            self.conn.close()
        self.conn = None
        self.cursor = None

    def _createdb(self):
        """ Create database """
        for argname in dir(dbcalls):
            if argname.startswith('create_'):
                print 'Call to create %s' % argname
                self.cursor.execute(getattr(dbcalls, argname))
        self.conn.commit()
        self.destroy()

    def initialize(self):
        """ Initialize sqlite3 connection """
        if not self.conn:
            self.conn = sqlite3.connect(self.dbfile)
        if not self.cursor:
            self.cursor = self.conn.cursor()

    def execute_get(self, query):
        """ GET Execution """
        self.initialize()
        alldata = []
        try:
            #print 'Call %s' % query
            self.cursor.execute(query)
            colname = [tup[0] for tup in self.cursor.description]
            alldata = self.cursor.fetchall()
        except Exception as ex:
            raise ex
        finally:
            self.destroy()
        return colname, alldata

    def execute_ins(self, query, values):
        """ INSERT Execute """
        self.initialize()
        try:
            for item in values:
                self.cursor.execute(query, item)
            self.conn.commit()
        except sqlite3.IntegrityError as ex:
            print 'Record Already Exists. Ex: %s' % ex
            self.conn.rollback()
            raise ex
        except Exception as ex:
            print 'Got Exception %s ' % ex
            self.conn.rollback()
            raise ex
        finally:
            self.destroy()
        return 'OK'

    def execute_del(self, query, values):
        """ DELETE Execute """
        self.initialize()
        try:
            self.cursor.execute(query)
            self.conn.commit()
        except Exception as ex:
            print 'Got Exception %s ' % ex
            self.conn.rollback()
            raise ex
        finally:
            self.destroy()
        return 'OK'


class dbinterface(object):
    def __init__(self, configFile):
        self.db = DBBackend(configFile)

    def getcall(self, callaction, calltype):
        """ Get call from ALL available ones """
        callquery = ""
        try:
            callquery = getattr(dbcalls, '%s_%s' % (callaction, calltype))
        except AttributeError as ex:
            print 'Called %s_%s, but got exception %s' % (callaction, calltype, ex)
            raise ex
        return callquery

    # =====================================================
    #  HERE GOES GET CALLS
    # =====================================================

    def _caller(self, origquery, limit=None, orderby=None, search=None):
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
        """ GET Call for APPs """
        dbout = self._caller(self.getcall('get', calltype), limit, orderby, search)
        out = []
        if mapping:
            for item in dbout[1]:
                out.append(dict(zip(dbout[0], list(item))))
            return out
        return dbout

    # =====================================================
    #  HERE GOES INSERT CALLS
    # =====================================================

    def insert(self, calltype, values):
        """ INSERT call for APPs """
        return self.db.execute_ins(self.getcall('insert', calltype), values)

    # =====================================================
    #  HERE GOES UPDATE CALLS
    # =====================================================

    def update(self, calltype, values):
        """ UPDATE Call for APPs """
        return self.db.execute_ins(self.getcall('update', calltype), values)

    # =====================================================
    #  HERE GOES DELETE CALLS
    # =====================================================

    def delete(self, calltype, values):
        """ DELETE Call for APPs """
        query = ""
        if values:
            first = True
            for item in values:
                if first:
                    query = "WHERE "
                else:
                    query += "AND"
                query += '%s = "%s" ' % (item[0], item[1])
        fullquery = "%s %s" % (self.getcall('delete', calltype), query)
        self.db.execute_del(fullquery, None)
