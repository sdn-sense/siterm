#!/usr/bin/env python3
# pylint: disable=line-too-long
"""DB Models for SQLAlchemy.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2026 ESnet
Date                    : 2026/01/02
"""

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import LONGBLOB, LONGTEXT
from sqlalchemy.orm import DeclarativeBase

# LONGTEXT/LONGBLOB on MariaDB, plain TEXT/BLOB elsewhere (unit tests run on SQLite).
LongText = Text().with_variant(LONGTEXT(), "mysql", "mariadb")
LongBlob = LargeBinary().with_variant(LONGBLOB(), "mysql", "mariadb")


class Base(DeclarativeBase):
    """Base class for all models."""


class Model(Base):
    """Model table. Content lives in modelcontent under contentid (shared by identical models)."""

    __tablename__ = "models"

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    contentid = Column(String(255), nullable=False)


class ModelContent(Base):
    """Compressed model serializations, keyed by models.contentid."""

    __tablename__ = "modelcontent"
    __table_args__ = (UniqueConstraint("uid", "fmt", name="uq_modelcontent_uid_fmt"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(String(255), nullable=False)
    fmt = Column(String(16), nullable=False)
    content = Column(LongBlob, nullable=False)
    insertdate = Column(Integer, nullable=False)


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
    error = Column(LONGTEXT, nullable=True)


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
    hostinfo = Column(LongText, nullable=False)


class Service(Base):
    """Service table."""

    __tablename__ = "services"
    __table_args__ = (UniqueConstraint("hostname", "servicename"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    servicename = Column(String(50), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    serviceinfo = Column(LongText, nullable=False)


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
    # exccode: stable machine-readable error code (see CustomExceptions.exceptionCode).
    # -100 = unknown/unclassified. Permanent: codes are never reused.
    exccode = Column(Integer, nullable=False, server_default="-100")
    # exccodes: full list of exccode values reported this cycle (a WARNING
    # state can batch several distinct causes together); exccode above is
    # always exccodes[0]. Nullable/no default: existing rows predate this
    # column and are simply absent until their next report.
    exccodes = Column(JSON, nullable=True)


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
    debuginfo = Column(LongText, nullable=False)
    outputinfo = Column(LongText, nullable=False)
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


class BGPMon(Base):
    """BGPMon table. One row per host, output is the normalized
    {"vrf": ..., "afi_checked": [...], "peers": [...]} schema produced by
    the bgpsummary.yaml ansible playbook (see docs/plans/bgp-monitoring.md)."""

    __tablename__ = "bgpmon"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    output = Column(JSON, nullable=False)


class BGPForceRescan(Base):
    """BGPForceRescan table. A row here signals BGPMonitoring.startwork() to
    bypass its check-interval throttle and rescan immediately."""

    __tablename__ = "bgpforcerescan"

    id = Column(Integer, primary_key=True, autoincrement=True)
    insertdate = Column(Integer, nullable=False)


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


class DeltaIdempotency(Base):
    """DeltaIdempotency table: delta POST Idempotency-Key per user and its stored result."""

    __tablename__ = "deltaidempotency"
    __table_args__ = (UniqueConstraint("username", "idemkey"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), nullable=False)
    idemkey = Column(String(255), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    deltaid = Column(String(255), nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)
    # Null while the original request is still in progress
    statuscode = Column(Integer, nullable=True)
    response = Column(LONGTEXT, nullable=True)


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
    permissions = Column(Integer, nullable=False)
    disabled = Column(Boolean, default=False)
    created_at = Column(Integer, nullable=False)
    updated_at = Column(Integer, nullable=False)
    password_changed_at = Column(Integer, nullable=False)


class RefreshToken(Base):
    """RefreshToken table."""

    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(36), nullable=False)
    client_ip = Column(String(64), nullable=False)
    token_hash = Column(String(64), primary_key=True)
    session_id = Column(String(64), nullable=False)
    expires_at = Column(Integer, nullable=False)
    permissions = Column(Integer, nullable=False)
    revoked = Column(Boolean, default=False)
    rotated_from = Column(String(64))


class KVStore(Base):
    """Small shared state between FE components (flags, snapshots, published config), JSON encoded."""

    __tablename__ = "kvstore"
    __table_args__ = (UniqueConstraint("namespace", "name", name="uq_kvstore_namespace_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    namespace = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    value = Column(LongText, nullable=False)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)


class Lease(Base):
    """Time-limited ownership of a named resource (leader role, device, membership)."""

    __tablename__ = "leases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, unique=True)
    holder = Column(String(255), nullable=False)
    expires_at = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)


class DeltaRequest(Base):
    """Delta submissions queued by REST for PolicyService, with the accept result."""

    __tablename__ = "deltarequests"
    __table_args__ = (Index("ix_deltarequests_deltaid", "deltaid"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    deltaid = Column(String(255), nullable=False)
    state = Column(String(32), nullable=False)
    payload = Column(LongText, nullable=False)
    result = Column(LongText, nullable=True)
    insertdate = Column(Integer, nullable=False)
    updatedate = Column(Integer, nullable=False)


REGISTRY = {
    "models": Model,
    "modelcontent": ModelContent,
    "kvstore": KVStore,
    "leases": Lease,
    "deltarequests": DeltaRequest,
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
    "bgpmon": BGPMon,
    "bgpforcerescan": BGPForceRescan,
    "deltatimestates": DeltaTimeState,
    "serviceaction": ServiceAction,
    "forceapplyuuid": ForceApplyUUID,
    "instancestartend": InstanceStartEnd,
    "deltasusertracking": DeltaUserTracking,
    "deltaidempotency": DeltaIdempotency,
    "dbversion": DBVersion,
    "users": User,
    "refresh_tokens": RefreshToken,
}
