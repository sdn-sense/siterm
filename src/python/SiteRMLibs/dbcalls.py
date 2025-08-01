#!/usr/bin/env python3
# pylint: disable=line-too-long
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
Email                   : jbalcas (at) es (dot) net
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
                          modadd longtext,
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
                          ip varchar(45) NOT NULL,
                          hostname varchar(255) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          hostinfo varchar(4096) NOT NULL,
                          primary key(id), unique key(ip))"""
create_services = """CREATE TABLE IF NOT EXISTS services(
                          id int auto_increment,
                          hostname varchar(255) NOT NULL,
                          servicename varchar(50) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          serviceinfo varchar(4096) NOT NULL,
                          primary key(id), unique key(hostname, servicename))"""
create_switch = """CREATE TABLE IF NOT EXISTS switch(
                          id int auto_increment,
                          sitename text NOT NULL,
                          device text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output longtext NOT NULL,
                          error longtext NOT NULL,
                          primary key(id))"""
create_servicestates = """CREATE TABLE IF NOT EXISTS servicestates(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          servicename VARCHAR(50) NOT NULL,
                          servicestate VARCHAR(50) NOT NULL,
                          runtime int NOT NULL,
                          version VARCHAR(50) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          exc varchar(4096) NOT NULL,
                          primary key(id))"""
create_debugworkers = """CREATE TABLE IF NOT EXISTS debugworkers(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          hostinfo varchar(4096) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          primary key(id))"""
create_debugrequests = """CREATE TABLE IF NOT EXISTS debugrequests(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          state VARCHAR(20) NOT NULL,
                          debuginfo varchar(4096) NOT NULL,
                          outputinfo varchar(4096) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          primary key(id))"""
create_activeDeltas = """CREATE TABLE IF NOT EXISTS activeDeltas(
                          id int auto_increment,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output json NOT NULL,
                          primary key(id))"""
create_snmpmon = """CREATE TABLE IF NOT EXISTS snmpmon(
                          id int auto_increment,
                          hostname text NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output json NOT NULL,
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
create_serviceaction = """CREATE TABLE IF NOT EXISTS serviceaction(
                                id int auto_increment,
                                servicename text NOT NULL,
                                hostname text NOT NULL,
                                serviceaction text NOT NULL,
                                insertdate int NOT NULL,
                                primary key(id))"""
create_forceapplyuuid = """CREATE TABLE IF NOT EXISTS forceapplyuuid(
                                id int auto_increment,
                                uuid text NOT NULL,
                                primary key(id))"""
create_instancestartend = """CREATE TABLE IF NOT EXISTS instancestartend(
                                id int auto_increment,
                                instanceid text NOT NULL,
                                insertdate int NOT NULL,
                                starttimestamp int NOT NULL,
                                endtimestamp int NOT NULL,
                                primary key(id))"""
create_deltasusertracking = """CREATE TABLE IF NOT EXISTS deltasusertracking(
                                id int auto_increment,
                                username text NOT NULL,
                                insertdate int NOT NULL,
                                deltaid text NOT NULL,
                                useraction text NOT NULL,
                                otherinfo longtext NOT NULL,
                                primary key(id))"""
create_dbversion = """CREATE TABLE IF NOT EXISTS dbversion(
                                id int auto_increment,
                                version text NOT NULL,
                                primary key(id))"""

insert_models = "INSERT INTO models(uid, insertdate, fileloc, content) VALUES(%(uid)s, %(insertdate)s, %(fileloc)s, %(content)s)"
insert_deltas = """INSERT INTO deltas(uid, insertdate, updatedate, state, deltat, content, modelid, modadd)
                   VALUES(%(uid)s, %(insertdate)s, %(updatedate)s, %(state)s, %(deltat)s, %(content)s, %(modelid)s, %(modadd)s)"""
insert_delta_connections = """INSERT INTO delta_connections(deltaid, connectionid, state) VALUES(%(deltaid)s, %(connectionid)s, %(state)s)"""
insert_states = "INSERT INTO states(deltaid, state, insertdate) VALUES(%(deltaid)s, %(state)s, %(insertdate)s)"
insert_hoststates = "INSERT INTO hoststates(deltaid, state, insertdate, updatedate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(updatedate)s, %(hostname)s)"
insert_hoststateshistory = "INSERT INTO hoststateshistory(deltaid, state, insertdate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(hostname)s)"
insert_parsed = "INSERT INTO parsed(deltaid, vals, insertdate) VALUES(%(deltaid)s, %(vals)s, %(insertdate)s)"
insert_hosts = "INSERT INTO hosts(ip, hostname, insertdate, updatedate, hostinfo) VALUES (%(ip)s, %(hostname)s, %(insertdate)s, %(updatedate)s, %(hostinfo)s)"
insert_services = "INSERT INTO services(hostname, servicename, insertdate, updatedate, serviceinfo) VALUES (%(hostname)s, %(servicename)s, %(insertdate)s, %(updatedate)s, %(serviceinfo)s)"
insert_switch = "INSERT INTO switch(sitename, device, insertdate, updatedate, output, error) VALUES(%(sitename)s, %(device)s, %(insertdate)s, %(updatedate)s, %(output)s, %(error)s)"
insert_switch_error = "INSERT INTO switch(sitename, device, insertdate, updatedate, output, error) VALUES(%(sitename)s, %(device)s, %(updatedate)s, %(updatedate)s, '{}', %(error)s)"
insert_activeDeltas = "INSERT INTO activeDeltas(insertdate, updatedate, output) VALUES(%(insertdate)s, %(updatedate)s, %(output)s)"
insert_servicestates = "INSERT INTO servicestates(hostname, servicename, servicestate, runtime, version, insertdate, updatedate, exc) VALUES(%(hostname)s, %(servicename)s, %(servicestate)s, %(runtime)s, %(version)s, %(insertdate)s, %(updatedate)s, %(exc)s)"
insert_debugworkers = "INSERT INTO debugworkers(hostname, hostinfo, insertdate, updatedate) VALUES(%(hostname)s, %(hostinfo)s, %(insertdate)s, %(updatedate)s)"
insert_debugrequests = (
    "INSERT INTO debugrequests(hostname, state, debuginfo, outputinfo, insertdate, updatedate) VALUES(%(hostname)s, %(state)s, %(debuginfo)s, %(outputinfo)s, %(insertdate)s, %(updatedate)s)"
)
insert_snmpmon = "INSERT INTO snmpmon(hostname, insertdate, updatedate, output) VALUES(%(hostname)s, %(insertdate)s, %(updatedate)s, %(output)s)"
insert_deltatimestates = (
    "INSERT INTO deltatimestates(insertdate, uuid, uuidtype, hostname, hostport, uuidstate) VALUES(%(insertdate)s, %(uuid)s, %(uuidtype)s, %(hostname)s, %(hostport)s, %(uuidstate)s)"
)
insert_serviceaction = "INSERT INTO serviceaction(servicename, hostname, serviceaction, insertdate) VALUES(%(servicename)s, %(hostname)s, %(serviceaction)s, %(insertdate)s)"
insert_forceapplyuuid = "INSERT INTO forceapplyuuid(uuid) VALUES(%(uuid)s)"
insert_instancestartend = "INSERT INTO instancestartend(instanceid, insertdate, starttimestamp, endtimestamp) VALUES(%(instanceid)s, %(insertdate)s, %(starttimestamp)s, %(endtimestamp)s)"
insert_deltasusertracking = "INSERT INTO deltasusertracking(username, insertdate, deltaid, useraction, otherinfo) VALUES(%(username)s, %(insertdate)s, %(deltaid)s, %(useraction)s, %(otherinfo)s)"
insert_dbversion = "INSERT INTO dbversion(version) VALUES(%(version)s)"

get_models = "SELECT id, uid, insertdate, fileloc, content FROM models"
get_deltas = "SELECT id, uid, insertdate, updatedate, state, deltat, content, modelid, modadd FROM deltas"
get_delta_connections = "SELECT id, deltaid, connectionid, state FROM delta_connections"
get_states = "SELECT id, deltaid, state, insertdate FROM states"
get_hoststates = "SELECT id, deltaid, state, insertdate, updatedate, hostname FROM hoststates"
get_hoststateshistory = "SELECT id, deltaid, state, insertdate, hostname FROM hoststateshistory"
get_parsed = "SELECT id, deltaid, vals, insertdate FROM parsed"
get_hosts = "SELECT id, ip, hostname, insertdate, updatedate, hostinfo FROM hosts"
get_services = "SELECT id, hostname, servicename, insertdate, updatedate, serviceinfo FROM services"
get_switch = "SELECT id, sitename, device, insertdate, updatedate, output FROM switch"
get_activeDeltas = "SELECT id, insertdate, updatedate, output FROM activeDeltas"
get_servicestates = "SELECT id, hostname, servicename, servicestate, runtime, version, insertdate, updatedate, exc FROM servicestates"
get_debugworkers = "SELECT id, hostname, hostinfo, insertdate, updatedate FROM debugworkers"
get_debugrequests = "SELECT id, hostname, state, debuginfo, outputinfo, insertdate, updatedate FROM debugrequests"
get_snmpmon = "SELECT id, hostname, insertdate, updatedate, output FROM snmpmon"
get_deltatimestates = "SELECT id, insertdate, uuid, uuidtype, hostname, hostport, uuidstate FROM deltatimestates"
get_serviceaction = "SELECT id, servicename, hostname, serviceaction, insertdate FROM serviceaction"
get_forceapplyuuid = "SELECT id, uuid FROM forceapplyuuid"
get_instancestartend = "SELECT id, instanceid, insertdate, starttimestamp, endtimestamp FROM instancestartend"
get_deltasusertracking = "SELECT id, username, insertdate, deltaid, useraction, otherinfo FROM deltasusertracking"
get_dbversion = "SELECT id, version FROM dbversion"

update_deltas = "UPDATE deltas SET updatedate = %(updatedate)s, state = %(state)s WHERE uid = %(uid)s"
update_delta_connections = "UPDATE delta_connections SET state = %(state)s WHERE connectionid = %(connectionid)s AND deltaid = %(deltaid)s"
update_deltasmod = "UPDATE deltas SET updatedate = %(updatedate)s, modadd = %(modadd)s WHERE uid = %(uid)s"
update_hoststates = "UPDATE hoststates SET state = %(state)s, updatedate = %(updatedate)s WHERE id = %(id)s"
update_hosts = "UPDATE hosts SET ip = %(ip)s, hostname = %(hostname)s, updatedate = %(updatedate)s, hostinfo = %(hostinfo)s WHERE id = %(id)s"
update_services = "UPDATE services SET hostname = %(hostname)s, servicename = %(servicename)s, updatedate = %(updatedate)s, serviceinfo = %(serviceinfo)s WHERE id = %(id)s"
update_switch = "UPDATE switch SET sitename = %(sitename)s, updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s"
update_switch_error = "UPDATE switch SET sitename = %(sitename)s, updatedate = %(updatedate)s, error = %(error)s WHERE id = %(id)s"
update_activeDeltas = "UPDATE activeDeltas SET updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s"
update_servicestates = "UPDATE servicestates SET servicestate = %(servicestate)s, updatedate = %(updatedate)s, runtime = %(runtime)s, version = %(version)s, exc = %(exc)s WHERE hostname = %(hostname)s AND servicename = %(servicename)s"
update_debugworkers = "UPDATE debugworkers SET updatedate = %(updatedate)s, hostinfo = %(hostinfo)s, WHERE hostname = %(hostname)s"
update_debugrequests = "UPDATE debugrequests SET state = %(state)s, updatedate = %(updatedate)s WHERE id = %(id)s"
update_debugrequestsworker = "UPDATE debugrequests SET state = %(state)s, hostname = %(hostname)s, updatedate = %(updatedate)s WHERE id = %(id)s"
update_snmpmon = "UPDATE snmpmon SET updatedate = %(updatedate)s, output = %(output)s WHERE id = %(id)s AND hostname = %(hostname)s"
# update_deltatimestates - Update call is not needed for update delta timestates. It always write a new entry and update not needed.
update_serviceaction = "UPDATE serviceaction SET serviceaction = %(serviceaction)s WHERE id = %(id)s"
update_forceapplyuuid = "UPDATE forceapplyuuid SET uuid = %(uuid)s WHERE id = %(id)s"
# update_instancestartend - Update call is not needed for update instance start end. It always write a new entry and update not needed.
# update_deltasusertracking - Update call is not needed for update deltas user tracking. It always write a new entry and update not needed.
update_dbversion = "UPDATE dbversion SET version = %(version)s WHERE id = %(id)s"

delete_models = "DELETE FROM models"
delete_deltas = "DELETE FROM deltas"
delete_delta_connections = "DELETE FROM delta_connections"
delete_states = "DELETE FROM states"
delete_hoststates = "DELETE FROM hoststates"
delete_hoststateshistory = "DELETE FROM hoststateshistory"
delete_parsed = "DELETE FROM parsed"
delete_hosts = "DELETE FROM hosts"
delete_services = "DELETE FROM services"
delete_switch = "DELETE FROM switch"
delete_servicestates = "DELETE FROM servicestates"
delete_debugworkers = "DELETE FROM debugworkers"
delete_debugrequests = "DELETE FROM debugrequests"
delete_activeDeltas = "DELETE FROM activeDeltas"
delete_snmpmon = "DELETE FROM snmpmon"
delete_deltatimestates = "DELETE FROM deltatimestates"
delete_serviceaction = "DELETE FROM serviceaction"
delete_forceapplyuuid = "DELETE FROM forceapplyuuid"
delete_instancestartend = "DELETE FROM instancestartend"
delete_deltasusertracking = "DELETE FROM deltasusertracking"
delete_dbversion = "DELETE FROM dbversion"
