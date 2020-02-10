#!/usr/bin/env python
"""
DB Backend SQL Calls to databses.

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
create_models = "CREATE TABLE models(id INTEGER PRIMARY KEY AUTOINCREMENT, uid text NOT NULL, insertdate INTEGER NOT NULL, fileloc text NOT NULL)"
create_deltas = """CREATE TABLE deltas(id INTEGER PRIMARY KEY AUTOINCREMENT,
                                       uid text NOT NULL,
                                       insertdate INTEGER NOT NULL,
                                       updatedate INTEGER NOT NULL,
                                       state text NOT NULL,
                                       deltat text NOT NULL,
                                       content text NOT NULL,
                                       modelid text NOT NULL,
                                       reduction text NOT NULL,
                                       addition text NOT NULL,
                                       reductionid text,
                                       modadd text,
                                       connectionid text NOT NULL)"""
create_states = "CREATE TABLE states(id INTEGER PRIMARY KEY AUTOINCREMENT, deltaid text NOT NULL, state text NOT NULL, insertdate INTEGER NOT NULL)"
create_hoststates = "CREATE TABLE hoststates(id INTEGER PRIMARY KEY AUTOINCREMENT, deltaid text NOT NULL, state text NOT NULL, insertdate INTEGER NOT NULL, updatedate INTEGER NOT NULL, hostname text NOT NULL)"
create_hoststateshistory = "CREATE TABLE hoststateshistory(id INTEGER PRIMARY KEY AUTOINCREMENT, deltaid text NOT NULL, state text NOT NULL, insertdate INTEGER NOT NULL, hostname text NOT NULL)"
create_parsed = "CREATE TABLE parsed(id INTEGER PRIMARY KEY AUTOINCREMENT, deltaid text NOT NULL, vals text NOT NULL, insertdate INTEGER NOT NULL)"
create_hosts = "CREATE TABLE hosts(id INTEGER PRIMARY KEY AUTOINCREMENT, ip text NOT NULL, hostname text NOT NULL, insertdate INTEGER NOT NULL, updatedate INTEGER NOT NULL, hostinfo text NOT NULL)"


insert_models = "INSERT INTO models(uid, insertdate, fileloc) VALUES(:uid, :insertdate, :fileloc)"
insert_deltas = """INSERT INTO deltas(uid, insertdate, updatedate, state, deltat, content, modelid, reduction, addition, reductionid, modadd, connectionid)
                   VALUES(:uid, :insertdate, :updatedate, :state, :deltat, :content, :modelid, :reduction, :addition, :reductionid, :modadd, :connectionid)"""
insert_states = "INSERT INTO states(deltaid, state, insertdate) VALUES(:deltaid, :state, :insertdate)"
insert_hoststates = "INSERT INTO hoststates(deltaid, state, insertdate, updatedate, hostname) VALUES(:deltaid, :state, :insertdate, :updatedate, :hostname)"
insert_hoststateshistory = "INSERT INTO hoststateshistory(deltaid, state, insertdate, hostname) VALUES(:deltaid, :state, :insertdate, :hostname)"
insert_parsed = "INSERT INTO parsed(deltaid, vals, insertdate) VALUES(:deltaid, :vals, :insertdate)"
insert_hosts = "INSERT INTO hosts(ip, hostname, insertdate, updatedate, hostinfo) VALUES(:ip, :hostname, :insertdate, :updatedate, :hostinfo)"

get_models = "SELECT id, uid, insertdate, fileloc FROM models"
get_deltas = "SELECT id, uid, insertdate, updatedate, state, deltat, content, modelid, reduction, addition, reductionid, modadd, connectionid FROM deltas"
get_states = "SELECT id, deltaid, state, insertdate FROM states"
get_hoststates = "SELECT id, deltaid, state, insertdate, updatedate, hostname FROM hoststates"
get_hoststateshistory = "SELECT id, deltaid, state, insertdate, hostname FROM hoststateshistory"
get_parsed = "SELECT id, deltaid, vals, insertdate FROM parsed"
get_hosts = "SELECT id, ip, hostname, insertdate, updatedate, hostinfo FROM hosts"

update_deltas = "UPDATE deltas SET updatedate = :updatedate, state = :state WHERE uid = :uid"
update_deltasmod = "UPDATE deltas SET updatedate = :updatedate, modadd = :modadd WHERE uid = :uid"
update_hoststates = "UPDATE hoststates SET state = :state, updatedate = :updatedate WHERE id = :id"

update_hosts = "UPDATE hosts SET ip = :ip, hostname = :hostname, updatedate = :updatedate, hostinfo = :hostinfo WHERE id = :id"

delete_models = "DELETE FROM models"
delete_states = "DELETE FROM states"
delete_hoststates = "DELETE FROM hoststates"
delete_hosts = "DELETE FROM hosts"
