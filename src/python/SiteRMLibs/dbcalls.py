#!/usr/bin/env python3
"""DB Backend SQL Calls to databses.

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
create_models = """CREATE TABLE IF NOT EXISTS models(
                          id int auto_increment,
                          uid text NOT NULL,
                          insertdate int NOT NULL,
                          fileloc text NOT NULL,
                          content longtext NOT NULL,
                          primary key(id))"""
create_deltas = """CREATE TABLE IF NOT EXISTS deltas(
                          id int auto_increment,
                          uid text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          state text NOT NULL,
                          deltat text NOT NULL,
                          content longtext NOT NULL,
                          modelid text NOT NULL,
                          reduction longtext NOT NULL,
                          addition longtext NOT NULL,
                          reductionid text,
                          modadd longtext,
                          connectionid text NOT NULL,
                          primary key(id))"""
create_delta_connections = """CREATE TABLE IF NOT EXISTS delta_connections(
                          id int auto_increment,
                          deltaid text NOT NULL,
                          connectionid text NOT NULL,
                          state text NOT NULL,
                          primary key(id))"""
create_states = """CREATE TABLE IF NOT EXISTS states(
                          id int auto_increment,
                          deltaid text NOT NULL,
                          state text NOT NULL,
                          insertdate int NOT NULL,
                          primary key(id))"""
create_hoststates = """CREATE TABLE IF NOT EXISTS hoststates(
                          id int auto_increment,
                          deltaid text NOT NULL,
                          state text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          hostname text NOT NULL,
                          primary key(id))"""
create_hoststateshistory = """CREATE TABLE IF NOT EXISTS hoststateshistory(
                          id int auto_increment,
                          deltaid text NOT NULL,
                          state text NOT NULL,
                          insertdate int NOT NULL,
                          hostname text NOT NULL,
                          primary key(id))"""
create_parsed = """CREATE TABLE IF NOT EXISTS parsed(
                          id int auto_increment,
                          deltaid text NOT NULL,
                          vals longtext NOT NULL,
                          insertdate int NOT NULL,
                          primary key(id))"""
create_hosts = """CREATE TABLE IF NOT EXISTS hosts(
                          id int auto_increment,
                          ip text NOT NULL,
                          hostname text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          hostinfo longtext NOT NULL,
                          primary key(id))"""
create_switches = """CREATE TABLE IF NOT EXISTS switches(
                          id int auto_increment,
                          sitename text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output longtext NOT NULL,
                          error longtext NOT NULL,
                          primary key(id))"""
create_servicestates = """CREATE TABLE IF NOT EXISTS servicestates(
                          id int auto_increment,
                          hostname text NOT NULL,
                          servicename text NOT NULL,
                          servicestate text NOT NULL,
                          runtime int NOT NULL,
                          version text NOT NULL,
                          updatedate int NOT NULL,
                          primary key(id))"""
create_debugrequests = """CREATE TABLE IF NOT EXISTS debugrequests(
                          id int auto_increment,
                          hostname text NOT NULL,
                          state text NOT NULL,
                          requestdict longtext NOT NULL,
                          output longtext NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          primary key(id))"""
create_activeDeltas = """CREATE TABLE IF NOT EXISTS activeDeltas(
                          id int auto_increment,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output longtext NOT NULL,
                          primary key(id))"""
create_snmpmon = """CREATE TABLE IF NOT EXISTS snmpmon(
                          id int auto_increment,
                          hostname text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output longtext NOT NULL,
                          primary key(id))"""
create_deltatimestates = """CREATE TABLE IF NOT EXISTS deltatimestates(
                             id int auto_increment,
                             insertdate int NOT NULL,
                             uuid text NOT NULL,
                             uuidtype text NOT NULL,
                             hostname text NOT NULL,
                             hostport text NOT NULL,
                             uuidstate text NOT NULL,
                             primary key(id))"""

insert_models = "INSERT INTO models(uid, insertdate, fileloc, content) VALUES(%(uid)s, %(insertdate)s, %(fileloc)s, %(content)s)"
insert_deltas = """INSERT INTO deltas(uid, insertdate, updatedate, state, deltat, content, modelid, reduction, addition, reductionid, modadd, connectionid)
                   VALUES(%(uid)s, %(insertdate)s, %(updatedate)s, %(state)s, %(deltat)s, %(content)s, %(modelid)s, %(reduction)s, %(addition)s, %(reductionid)s, %(modadd)s, %(connectionid)s)"""
insert_delta_connections = """INSERT INTO delta_connections(deltaid, connectionid, state) VALUES(%(deltaid)s, %(connectionid)s, %(state)s)"""
insert_states = "INSERT INTO states(deltaid, state, insertdate) VALUES(%(deltaid)s, %(state)s, %(insertdate)s)"
insert_hoststates = "INSERT INTO hoststates(deltaid, state, insertdate, updatedate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(updatedate)s, %(hostname)s)"
insert_hoststateshistory = "INSERT INTO hoststateshistory(deltaid, state, insertdate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(hostname)s)"
insert_parsed = "INSERT INTO parsed(deltaid, vals, insertdate) VALUES(%(deltaid)s, %(vals)s, %(insertdate)s)"
insert_hosts = "INSERT INTO hosts(ip, hostname, insertdate, updatedate, hostinfo) VALUES(%(ip)s, %(hostname)s, %(insertdate)s, %(updatedate)s, %(hostinfo)s)"
insert_switches = "INSERT INTO switches(sitename, insertdate, updatedate, output, error) VALUES(%(sitename)s, %(insertdate)s, %(updatedate)s, %(output)s, %(error)s)"
insert_activeDeltas = "INSERT INTO activeDeltas(insertdate, updatedate, output) VALUES(%(insertdate)s, %(updatedate)s, %(output)s)"
insert_servicestates = "INSERT INTO servicestates(hostname, servicename, servicestate, runtime, version, updatedate) VALUES(%(hostname)s, %(servicename)s, %(servicestate)s, %(runtime)s, %(version)s, %(updatedate)s)"
insert_debugrequests = "INSERT INTO debugrequests(hostname, state, requestdict, output, insertdate, updatedate) VALUES(%(hostname)s, %(state)s, %(requestdict)s, %(output)s, %(insertdate)s, %(updatedate)s)"
insert_snmpmon = "INSERT INTO snmpmon(hostname, insertdate, updatedate, output) VALUES(%(hostname)s, %(insertdate)s, %(updatedate)s, %(output)s)"
insert_deltatimestates = "INSERT INTO deltatimestates(insertdate, uuid, uuidtype, hostname, hostport, uuidstate) VALUES(%(insertdate)s, %(uuid)s, %(uuidtype)s, %(hostname)s, %(hostport)s, %(uuidstate)s)"

get_models = "SELECT id, uid, insertdate, fileloc, content FROM models"
get_deltas = "SELECT id, uid, insertdate, updatedate, state, deltat, content, modelid, reduction, addition, reductionid, modadd, connectionid FROM deltas"
get_delta_connections = "SELECT id, deltaid, connectionid, state FROM delta_connections"
get_states = "SELECT id, deltaid, state, insertdate FROM states"
get_hoststates = "SELECT id, deltaid, state, insertdate, updatedate, hostname FROM hoststates"
get_hoststateshistory = "SELECT id, deltaid, state, insertdate, hostname FROM hoststateshistory"
get_parsed = "SELECT id, deltaid, vals, insertdate FROM parsed"
get_hosts = "SELECT id, ip, hostname, insertdate, updatedate, hostinfo FROM hosts"
get_switches = "SELECT id, sitename, insertdate, updatedate, output FROM switches"
get_activeDeltas = "SELECT id, insertdate, updatedate, output FROM activeDeltas"
get_servicestates = "SELECT id, hostname, servicename, servicestate, runtime, version, updatedate FROM servicestates"
get_debugrequests = "SELECT id, hostname, state, requestdict, output, insertdate, updatedate FROM debugrequests"
get_debugrequestsids = "SELECT id FROM debugrequests"
get_snmpmon = "SELECT id, hostname, insertdate, updatedate, output FROM snmpmon"
get_deltatimestates = "SELECT id, insertdate, uuid, uuidtype, hostname, hostport, uuidstate FROM deltatimestates"

update_deltas = "UPDATE deltas SET updatedate = %(updatedate)s, state = %(state)s WHERE uid = %(uid)s"
update_delta_connections = "UPDATE delta_connections SET state = %(state)s WHERE connectionid = %(connectionid)s AND deltaid = %(deltaid)s"
update_deltasmod = "UPDATE deltas SET updatedate = %(updatedate)s, modadd = %(modadd)s WHERE uid = %(uid)s"
update_hoststates = "UPDATE hoststates SET state = %(state)s, updatedate = %(updatedate)s WHERE id = %(id)s"
update_hosts = "UPDATE hosts SET ip = %(ip)s, hostname = %(hostname)s, updatedate = %(updatedate)s, hostinfo = %(hostinfo)s WHERE id = %(id)s"
update_switches = "UPDATE switches SET sitename = %(sitename)s, updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s"
update_switches_error = "UPDATE switches SET sitename = %(sitename)s, updatedate = %(updatedate)s, error = %(error)s WHERE id = %(id)s"
update_activeDeltas = "UPDATE activeDeltas SET updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s"
update_servicestates = "UPDATE servicestates SET servicestate = %(servicestate)s, updatedate = %(updatedate)s, runtime = %(runtime)s, version = %(version)s WHERE hostname = %(hostname)s AND servicename = %(servicename)s"
update_debugrequests = "UPDATE debugrequests SET state = %(state)s, output = %(output)s, updatedate = %(updatedate)s WHERE id = %(id)s"
update_snmpmon = "UPDATE snmpmon SET updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s AND hostname = %(hostname)s"
# update_deltatimestates - Update call is not needed for update delta timestates. It always write a new entrya and update not needed.

delete_models = "DELETE FROM models"
delete_deltas = "DELETE FROM deltas"
delete_delta_connections = "DELETE FROM delta_connections"
delete_states = "DELETE FROM states"
delete_hoststates = "DELETE FROM hoststates"
delete_hoststateshistory = "DELETE FROM hoststateshistory"
delete_parsed = "DELETE FROM parsed"
delete_hosts = "DELETE FROM hosts"
delete_switches = "DELETE FROM switches"
delete_servicestates = "DELETE FROM servicestates"
delete_debugrequests = "DELETE FROM debugrequests"
delete_activeDeltas = "DELETE FROM activeDeltas"
delete_snmpmon = "DELETE FROM snmpmon"
delete_deltatimestates = "DELETE FROM deltatimestates"