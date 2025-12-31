#!/usr/bin/env python3
# pylint: disable=line-too-long
"""DB Models for SQLAlchemy.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2026 ESnet
Date                    : 2026/01/02
"""
from sqlalchemy import JSON, Boolean, Column, Integer, String, UniqueConstraint
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all models."""


class Model(Base):
    """Model table."""

    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    fileloc = Column(String(4096), nullable=False)


class Delta(Base):
    """Delta table."""

    __tablename__ = "deltas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    state = Column(String(64), nullable=False)
    deltat = Column(String(64), nullable=False)
    content = Column(LONGTEXT, nullable=False)
    modelid = Column(String(255), nullable=False)
    modadd = Column(String(64))


class DeltaConnection(Base):
    """DeltaConnection table."""

    __tablename__ = "delta_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deltaid = Column(String(255), nullable=False)
    connectionid = Column(String(1024), nullable=False)
    state = Column(String(64), nullable=False)


class State(Base):
    """State table."""

    __tablename__ = "states"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deltaid = Column(String(255), nullable=False)
    state = Column(String(64), nullable=False)
    insertdate = Column(Integer, nullable=False)


class HostState(Base):
    """HostState table."""

    __tablename__ = "hoststates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deltaid = Column(String(255), nullable=False)
    state = Column(String(64), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    hostname = Column(String(255), nullable=False)


class HostStateHistory(Base):
    """HostStateHistory table."""

    __tablename__ = "hoststateshistory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deltaid = Column(String(255), nullable=False)
    state = Column(String(64), nullable=False)
    insertdate = Column(Integer, nullable=False)
    hostname = Column(String(255), nullable=False)


class Host(Base):
    """Host table."""

    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ip = Column(String(45), nullable=False, unique=True)
    hostname = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    hostinfo = Column(String(4096), nullable=False)


class Service(Base):
    """Service table."""

    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("hostname", "servicename"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    servicename = Column(String(50), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    serviceinfo = Column(String(4096), nullable=False)


class Switch(Base):
    """Switch table."""

    __tablename__ = "switch"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sitename = Column(String(64), nullable=False)
    device = Column(String(64), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    output = Column(LONGTEXT, nullable=False)
    error = Column(LONGTEXT, nullable=False)


class ServiceState(Base):
    """ServiceState table."""

    __tablename__ = "servicestates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    servicename = Column(String(50), nullable=False)
    servicestate = Column(String(50), nullable=False)
    runtime = Column(Integer, nullable=False)
    version = Column(String(50), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    exc = Column(String(4096), nullable=False)


class DebugWorker(Base):
    """DebugWorker table."""

    __tablename__ = "debugworkers"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    hostinfo = Column(String(4096), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)


class DebugRequest(Base):
    """DebugRequest table."""

    __tablename__ = "debugrequests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    state = Column(String(64), nullable=False)
    action = Column(String(64), nullable=False)
    debuginfo = Column(String(4096), nullable=False)
    outputinfo = Column(String(4096), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)


class ActiveDelta(Base):
    """ActiveDelta table."""

    __tablename__ = "activeDeltas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    output = Column(JSON, nullable=False)


class SNMPMon(Base):
    """SNMPMon table."""

    __tablename__ = "snmpmon"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    output = Column(JSON, nullable=False)


class DeltaTimeState(Base):
    """DeltaTimeState table."""

    __tablename__ = "deltatimestates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insertdate = Column(Integer, nullable=False)
    uuid = Column(String(255), nullable=False)
    uuidtype = Column(String(64), nullable=False)
    hostname = Column(String(255), nullable=False)
    hostport = Column(String(64), nullable=False)
    uuidstate = Column(String(64), nullable=False)


class ServiceAction(Base):
    """ServiceAction table."""

    __tablename__ = "serviceaction"

    id = Column(Integer, primary_key=True, autoincrement=True)
    servicename = Column(String(64), nullable=False)
    hostname = Column(String(255), nullable=False)
    serviceaction = Column(String(64), nullable=False)
    insertdate = Column(Integer, nullable=False)


class ForceApplyUUID(Base):
    """ForceApplyUUID table."""

    __tablename__ = "forceapplyuuid"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(255), nullable=False)


class InstanceStartEnd(Base):
    """InstanceStartEnd table."""

    __tablename__ = "instancestartend"

    id = Column(Integer, primary_key=True, autoincrement=True)
    instanceid = Column(String(1024), nullable=False)
    insertdate = Column(Integer, nullable=False)
    starttimestamp = Column(Integer, nullable=False)
    endtimestamp = Column(Integer, nullable=False)


class DeltaUserTracking(Base):
    """DeltaUserTracking table."""

    __tablename__ = "deltasusertracking"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    deltaid = Column(String(255), nullable=False)
    useraction = Column(String(255), nullable=False)
    otherinfo = Column(LONGTEXT, nullable=False)


class DBVersion(Base):
    """DBVersion table."""

    __tablename__ = "dbversion"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(255), nullable=False)


class User(Base):
    """User table."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    username = Column(String(128), unique=True, nullable=False)
    password_hash = Column(LONGTEXT, nullable=False)
    display_name = Column(String(255))
    is_admin = Column(Boolean, default=False)
    disabled = Column(Boolean, default=False)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
    password_changed_at = Column(Integer, nullable=False)


class RefreshToken(Base):
    """RefreshToken table."""

    __tablename__ = "refresh_tokens"

    token_hash = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False)
    expires_at = Column(Integer, nullable=False)
    revoked = Column(Boolean, default=False)
    rotated_from = Column(String(64))


REGISTRY = {
    "models": Model,
    "deltas": Delta,
    "delta_connections": DeltaConnection,
    "states": State,
    "hoststates": HostState,
    "hoststateshistory": HostStateHistory,
    "hosts": Host,
    "services": Service,
    "switch": Switch,
    "servicestates": ServiceState,
    "debugworkers": DebugWorker,
    "debugrequests": DebugRequest,
    "activeDeltas": ActiveDelta,
    "snmpmon": SNMPMon,
    "deltatimestates": DeltaTimeState,
    "serviceaction": ServiceAction,
    "forceapplyuuid": ForceApplyUUID,
    "instancestartend": InstanceStartEnd,
    "deltasusertracking": DeltaUserTracking,
    "dbversion": DBVersion,
    "users": User,
    "refresh_tokens": RefreshToken,
}
