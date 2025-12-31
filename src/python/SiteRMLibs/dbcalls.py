#!/usr/bin/env python3
# pylint: disable=line-too-long
"""DB Backend SQL Calls to databases.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2019 California Institute of Technology
Date                    : 2019/05/01
"""
create_models = """CREATE TABLE IF NOT EXISTS models(
                          id int auto_increment,
                          uid VARCHAR(255) NOT NULL,
                          insertdate int NOT NULL,
                          fileloc VARCHAR(4096) NOT NULL,
                          primary key(id))"""
create_deltas = """CREATE TABLE IF NOT EXISTS deltas(
                          id int auto_increment,
                          uid VARCHAR(255) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          deltat VARCHAR(64) NOT NULL,
                          content longtext NOT NULL,
                          modelid VARCHAR(255) NOT NULL,
                          modadd VARCHAR(64),
                          primary key(id))"""
create_delta_connections = """CREATE TABLE IF NOT EXISTS delta_connections(
                          id int auto_increment,
                          deltaid VARCHAR(255) NOT NULL,
                          connectionid VARCHAR(1024) NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          primary key(id))"""
create_states = """CREATE TABLE IF NOT EXISTS states(
                          id int auto_increment,
                          deltaid VARCHAR(255) NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          insertdate int NOT NULL,
                          primary key(id))"""
create_hoststates = """CREATE TABLE IF NOT EXISTS hoststates(
                          id int auto_increment,
                          deltaid VARCHAR(255) NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          hostname VARCHAR(255) NOT NULL,
                          primary key(id))"""
create_hoststateshistory = """CREATE TABLE IF NOT EXISTS hoststateshistory(
                          id int auto_increment,
                          deltaid VARCHAR(255) NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          insertdate int NOT NULL,
                          hostname VARCHAR(255) NOT NULL,
                          primary key(id))"""
create_hosts = """CREATE TABLE IF NOT EXISTS hosts(
                          id int auto_increment,
                          ip VARCHAR(45) NOT NULL,
                          hostname VARCHAR(255) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          hostinfo VARCHAR(4096) NOT NULL,
                          primary key(id), unique key(ip))"""
create_services = """CREATE TABLE IF NOT EXISTS services(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          servicename VARCHAR(50) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          serviceinfo VARCHAR(4096) NOT NULL,
                          primary key(id), unique key(hostname, servicename))"""
create_switch = """CREATE TABLE IF NOT EXISTS switch(
                          id int auto_increment,
                          sitename VARCHAR(64) NOT NULL,
                          device VARCHAR(64) NOT NULL,
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
                          exc VARCHAR(4096) NOT NULL,
                          primary key(id))"""
create_debugworkers = """CREATE TABLE IF NOT EXISTS debugworkers(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          hostinfo VARCHAR(4096) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          primary key(id))"""
create_debugrequests = """CREATE TABLE IF NOT EXISTS debugrequests(
                          id int auto_increment,
                          hostname VARCHAR(255) NOT NULL,
                          state VARCHAR(64) NOT NULL,
                          action VARCHAR(64) NOT NULL,
                          debuginfo VARCHAR(4096) NOT NULL,
                          outputinfo VARCHAR(4096) NOT NULL,
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
                          hostname VARCHAR(255) NOT NULL,
                          insertdate int NOT NULL,
                          updatedate int NOT NULL,
                          output json NOT NULL,
                          primary key(id))"""
create_deltatimestates = """CREATE TABLE IF NOT EXISTS deltatimestates(
                             id int auto_increment,
                             insertdate int NOT NULL,
                             uuid VARCHAR(255) NOT NULL,
                             uuidtype VARCHAR(64) NOT NULL,
                             hostname VARCHAR(255) NOT NULL,
                             hostport VARCHAR(64) NOT NULL,
                             uuidstate VARCHAR(64) NOT NULL,
                             primary key(id))"""
create_serviceaction = """CREATE TABLE IF NOT EXISTS serviceaction(
                                id int auto_increment,
                                servicename VARCHAR(64) NOT NULL,
                                hostname VARCHAR(255) NOT NULL,
                                serviceaction VARCHAR(64) NOT NULL,
                                insertdate int NOT NULL,
                                primary key(id))"""
create_forceapplyuuid = """CREATE TABLE IF NOT EXISTS forceapplyuuid(
                                id int auto_increment,
                                uuid VARCHAR(255) NOT NULL,
                                primary key(id))"""
create_instancestartend = """CREATE TABLE IF NOT EXISTS instancestartend(
                                id int auto_increment,
                                instanceid VARCHAR(1024) NOT NULL,
                                insertdate int NOT NULL,
                                starttimestamp int NOT NULL,
                                endtimestamp int NOT NULL,
                                primary key(id))"""
create_deltasusertracking = """CREATE TABLE IF NOT EXISTS deltasusertracking(
                                id int auto_increment,
                                username VARCHAR(255) NOT NULL,
                                insertdate int NOT NULL,
                                deltaid VARCHAR(255) NOT NULL,
                                useraction VARCHAR(255) NOT NULL,
                                otherinfo longtext NOT NULL,
                                primary key(id))"""
create_dbversion = """CREATE TABLE IF NOT EXISTS dbversion(
                                id int auto_increment,
                                version VARCHAR(255) NOT NULL,
                                primary key(id))"""

create_users = """CREATE TABLE IF NOT EXISTS users(
                    id CHAR(36) PRIMARY KEY,
                    username VARCHAR(128) UNIQUE NOT NULL,
                    password_hash LONGTEXT NOT NULL,
                    display_name VARCHAR(255),
                    is_admin BOOLEAN DEFAULT FALSE,
                    disabled BOOLEAN DEFAULT FALSE,
                    created_at INT NOT NULL,
                    updated_at INT NOT NULL,
                    password_changed_at INT NOT NULL)"""

create_sessions = """CREATE TABLE IF NOT EXISTS sessions (
                        session_id CHAR(64) PRIMARY KEY,
                        user_id CHAR(36) NOT NULL,
                        created_at INT NOT NULL,
                        expires_at INT NOT NULL,
                        revoked BOOLEAN DEFAULT FALSE,
                        INDEX(user_id),
                        FOREIGN KEY (user_id) REFERENCES users(id))"""

create_refresh_tokens = """CREATE TABLE IF NOT EXISTS refresh_tokens (
                            token_hash CHAR(64) PRIMARY KEY,
                            session_id CHAR(64) NOT NULL,
                            expires_at INT NOT NULL,
                            revoked BOOLEAN DEFAULT FALSE,
                            rotated_from CHAR(64)"""

insert_users = "INSERT INTO users(id, username, password, display_name, is_admin, disabled, created_at) VALUES(%(id)s, %(username)s, %(password)s, %(display_name)s, %(is_admin)s, %(disabled)s, %(created_at)s)"
get_users = "SELECT * FROM users"
update_users = "UPDATE users SET username=%(username)s, password=%(password)s, display_name=%(display_name)s, is_admin=%(is_admin)s, disabled=%(disabled)s, created_at=%(created_at)s WHERE id=%(id)s"
delete_users = "DELETE FROM users"
get_sessions = "SELECT * FROM sessions"
insert_sessions = "INSERT INTO sessions(session_id, user_id, created_at, expires_at, revoked) VALUES(%(session_id)s, %(user_id)s, %(created_at)s, %(expires_at)s, %(revoked)s)"
update_sessions = "UPDATE sessions SET user_id=%(user_id)s, created_at=%(created_at)s, expires_at=%(expires_at)s, revoked=%(revoked)s WHERE session_id=%(session_id)s"
delete_sessions = "DELETE FROM sessions"
get_refresh_tokens = "SELECT * FROM refresh_tokens"
insert_refresh_tokens = "INSERT INTO refresh_tokens(token_hash, session_id, expires_at, revoked, rotated_from) VALUES(%(token_hash)s, %(session_id)s, %(expires_at)s, %(revoked)s, %(rotated_from)s)"
update_refresh_tokens = "UPDATE refresh_tokens SET session_id=%(session_id)s, expires_at=%(expires_at)s, revoked=%(revoked)s, rotated_from=%(rotated_from)s WHERE token_hash=%(token_hash)s"
delete_refresh_tokens = "DELETE FROM refresh_tokens"


insert_models = "INSERT INTO models(uid, insertdate, fileloc) VALUES(%(uid)s, %(insertdate)s, %(fileloc)s)"
insert_deltas = """INSERT INTO deltas(uid, insertdate, updatedate, state, deltat, content, modelid, modadd)
                   VALUES(%(uid)s, %(insertdate)s, %(updatedate)s, %(state)s, %(deltat)s, %(content)s, %(modelid)s, %(modadd)s)"""
insert_delta_connections = """INSERT INTO delta_connections(deltaid, connectionid, state) VALUES(%(deltaid)s, %(connectionid)s, %(state)s)"""
insert_states = "INSERT INTO states(deltaid, state, insertdate) VALUES(%(deltaid)s, %(state)s, %(insertdate)s)"
insert_hoststates = "INSERT INTO hoststates(deltaid, state, insertdate, updatedate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(updatedate)s, %(hostname)s)"
insert_hoststateshistory = "INSERT INTO hoststateshistory(deltaid, state, insertdate, hostname) VALUES(%(deltaid)s, %(state)s, %(insertdate)s, %(hostname)s)"
insert_hosts = "INSERT INTO hosts(ip, hostname, insertdate, updatedate, hostinfo) VALUES (%(ip)s, %(hostname)s, %(insertdate)s, %(updatedate)s, %(hostinfo)s)"
insert_services = "INSERT INTO services(hostname, servicename, insertdate, updatedate, serviceinfo) VALUES (%(hostname)s, %(servicename)s, %(insertdate)s, %(updatedate)s, %(serviceinfo)s)"
insert_switch = "INSERT INTO switch(sitename, device, insertdate, updatedate, output, error) VALUES(%(sitename)s, %(device)s, %(insertdate)s, %(updatedate)s, %(output)s, %(error)s)"
insert_switch_error = "INSERT INTO switch(sitename, device, insertdate, updatedate, output, error) VALUES(%(sitename)s, %(device)s, %(updatedate)s, %(updatedate)s, '{}', %(error)s)"
insert_activeDeltas = "INSERT INTO activeDeltas(insertdate, updatedate, output) VALUES(%(insertdate)s, %(updatedate)s, %(output)s)"
insert_servicestates = "INSERT INTO servicestates(hostname, servicename, servicestate, runtime, version, insertdate, updatedate, exc) VALUES(%(hostname)s, %(servicename)s, %(servicestate)s, %(runtime)s, %(version)s, %(insertdate)s, %(updatedate)s, %(exc)s)"
insert_debugworkers = "INSERT INTO debugworkers(hostname, hostinfo, insertdate, updatedate) VALUES(%(hostname)s, %(hostinfo)s, %(insertdate)s, %(updatedate)s)"
insert_debugrequests = (
    "INSERT INTO debugrequests(hostname, state, action, debuginfo, outputinfo, insertdate, updatedate) VALUES(%(hostname)s, %(state)s, %(action)s, %(debuginfo)s, %(outputinfo)s, %(insertdate)s, %(updatedate)s)"
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

get_models = "SELECT id, uid, insertdate, fileloc FROM models"
get_deltas = "SELECT id, uid, insertdate, updatedate, state, deltat, content, modelid, modadd FROM deltas"
get_delta_connections = "SELECT id, deltaid, connectionid, state FROM delta_connections"
get_states = "SELECT id, deltaid, state, insertdate FROM states"
get_hoststates = "SELECT id, deltaid, state, insertdate, updatedate, hostname FROM hoststates"
get_hoststateshistory = "SELECT id, deltaid, state, insertdate, hostname FROM hoststateshistory"
get_hosts = "SELECT id, ip, hostname, insertdate, updatedate, hostinfo FROM hosts"
get_services = "SELECT id, hostname, servicename, insertdate, updatedate, serviceinfo FROM services"
get_switch = "SELECT id, sitename, device, insertdate, updatedate, output FROM switch"
get_activeDeltas = "SELECT id, insertdate, updatedate, output FROM activeDeltas"
get_servicestates = "SELECT id, hostname, servicename, servicestate, runtime, version, insertdate, updatedate, exc FROM servicestates"
get_debugworkers = "SELECT id, hostname, hostinfo, insertdate, updatedate FROM debugworkers"
get_debugrequests = "SELECT id, hostname, state, action, debuginfo, outputinfo, insertdate, updatedate FROM debugrequests"
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
update_debugrequestsfull = "UPDATE debugrequests SET hostname = %(hostname)s, state = %(state)s, action = %(action)s, debuginfo = %(debuginfo)s, outputinfo = %(outputinfo)s, updatedate = %(updatedate)s WHERE id = %(id)s"
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
