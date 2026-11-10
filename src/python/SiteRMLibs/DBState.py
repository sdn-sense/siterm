#!/usr/bin/env python3
"""Shared FE state kept in the database: system state, flags, snapshots, models, leases and sharding.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2026 ESnet
@License                : Apache License, Version 2.0
Date                    : 2026/11/09
"""

import hashlib
import json
import os
import socket
import threading
import zlib

from rdflib import Graph
from SiteRMLibs.CustomExceptions import NotFoundError
from SiteRMLibs.DBBackend import dbinterface, getUTCnow, loadEnvFile
from SiteRMLibs.DefaultParams import LEASE_TTL

# kvstore namespaces
NS_SYSTEM = "system"
NS_FIRSTRUN = "firstrun"
NS_SWITCHUPDATE = "switchupdate"
NS_SNAPSHOT = "snapshot"
NS_M2M = "m2m"
NS_PROBES = "probes"

MODEL_FORMATS = ("ntriples", "turtle", "json-ld")

_STATEDB = {}


def dbConfigured():
    """Return True if this process has database settings (FE containers)."""
    loadEnvFile()
    return bool(os.getenv("DATABASE_URL") or os.getenv("MARIA_DB_HOST"))


def getStateDB():
    """Return a process-wide dbinterface for shared state."""
    if "db" not in _STATEDB:
        _STATEDB["db"] = dbinterface("DBState")
    return _STATEDB["db"]


def getInstanceName():
    """Return this FE instance name used for service states (SITERM_INSTANCE; 'hostname' = container hostname)."""
    instance = os.getenv("SITERM_INSTANCE", "") or "default"
    return socket.gethostname() if instance == "hostname" else instance


def getHolderID():
    """Return a lease holder id unique to this process."""
    return f"{socket.gethostname()}:{os.getpid()}"


# ==========================================================
#  System state (database init, published config)
# ==========================================================
def setDBInitState(dbI, state, version, msg=""):
    """Record database init/upgrade state (running, done, failed)."""
    dbI.kvset(NS_SYSTEM, "dbinit", {"state": state, "version": version, "msg": msg, "time": getUTCnow()})


def getDBInitState(dbI):
    """Return the database init state dict, or None if never recorded."""
    return dbI.kvget(NS_SYSTEM, "dbinit")


def feStartupState(version, requireConfig=True):
    """Return (state, message) of FE startup: 'ready', 'waiting' or 'failed'."""
    try:
        dbI = getStateDB()
        if not dbI.isDBReady():
            return "waiting", "Database is not reachable yet."
        dbinit = getDBInitState(dbI)
        if not dbinit or dbinit.get("state") == "running":
            return "waiting", "Database init/upgrade is still running (dbinit)."
        if dbinit.get("state") == "failed":
            return "failed", f"Database init failed: {dbinit.get('msg', '')}"
        if version and dbinit.get("version") != version:
            return "waiting", f"Database schema is for version {dbinit.get('version')}, this service runs {version}. Waiting for dbinit."
        if requireConfig and not loadSiteConfig(dbI):
            return "waiting", "Site configuration is not published to the database yet (ConfigFetcher)."
    except Exception as ex:  # pylint: disable=broad-except
        return "waiting", f"Unable to read startup state from database: {ex}"
    return "ready", ""


def recordProbeDisabled(probe, disabled):
    """Record (or clear) a disabled liveness/readiness probe of this container, so Validator can warn about it."""
    if not dbConfigured():
        return
    name = f"{socket.gethostname()}:{probe}"
    try:
        if disabled:
            getStateDB().kvset(NS_PROBES, name, getUTCnow())
        else:
            getStateDB().kvdelete(NS_PROBES, name)
    except Exception as ex:  # pylint: disable=broad-except
        print(f"Unable to record probe state in database: {ex}")


def disabledProbes(dbI):
    """Return names (container:probe) of disabled probes reported recently."""
    return sorted(dbI.kvlist(NS_PROBES).keys())


def publishSiteConfig(dbI, config):
    """Publish raw site configuration; return True if it changed."""
    digest = hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    current = dbI.kvget(NS_SYSTEM, "siteconfig")
    if current and current.get("hash") == digest:
        return False
    dbI.kvset(NS_SYSTEM, "siteconfig", {"hash": digest, "config": config})
    return True


def loadSiteConfig(dbI):
    """Return the published raw site configuration, or None."""
    current = dbI.kvget(NS_SYSTEM, "siteconfig")
    return current.get("config") if current else None


def loadOrCreateJWTKey(dbI, generate):
    """Return the JWT signing key (private PEM) shared by all frontends; the first caller stores generate() once."""
    stored = dbI.kvget(NS_SYSTEM, "jwtkey")
    if not stored:
        # Atomic insert: when replicas race, one key wins and every caller returns that one.
        dbI.kvadd(NS_SYSTEM, "jwtkey", {"private_key": generate(), "time": getUTCnow()})
        stored = dbI.kvget(NS_SYSTEM, "jwtkey")
    return stored["private_key"]


# ==========================================================
#  First run state and switch refresh requests
# ==========================================================
def setFirstRunState(dbI, service, state):
    """Record first-run state of a service: running or done."""
    dbI.kvset(NS_FIRSTRUN, service, {"state": state, "time": getUTCnow()})


def firstRunDone(dbI, service):
    """Return True once the service finished its first run."""
    value = dbI.kvget(NS_FIRSTRUN, service)
    return bool(value) and value.get("state") == "done"


def requestDeviceUpdate(dbI, device):
    """Ask the SwitchWorker of a device to refresh its data."""
    dbI.kvset(NS_SWITCHUPDATE, device, getUTCnow())


def consumeDeviceUpdate(dbI, device):
    """Return True (and clear it) if a refresh was requested for the device."""
    return dbI.kvdelete(NS_SWITCHUPDATE, device)


# ==========================================================
#  Snapshots (topology, prometheus metrics, worker ranges)
# ==========================================================
def saveSnapshot(dbI, name, value):
    """Store the latest output of a producer."""
    dbI.kvset(NS_SNAPSHOT, name, value)


def loadSnapshot(dbI, name):
    """Return the snapshot row ({'value', 'updatedate', ...}) or None."""
    return dbI.kvgetrow(NS_SNAPSHOT, name)


# ==========================================================
#  Model content
# ==========================================================
def saveModelContent(dbI, contentid, graph):
    """Store the model in all served formats, compressed, once per contentid."""
    for fmt in MODEL_FORMATS:
        if dbI.modelcontentget(contentid, fmt) is not None:
            continue
        dbI.modelcontentput(contentid, fmt, zlib.compress(graph.serialize(format=fmt).encode("utf-8"), 6))


def loadModelContent(dbI, contentid, fmt):
    """Return the model serialization as text or raise NotFoundError."""
    content = dbI.modelcontentget(contentid, fmt)
    if content is None:
        raise NotFoundError(f"Model content {contentid} in format {fmt} is not available in the database.")
    return zlib.decompress(content).decode("utf-8")


def loadModelGraph(dbI, contentid):
    """Return the model as an rdflib Graph or raise NotFoundError."""
    graph = Graph()
    graph.parse(data=loadModelContent(dbI, contentid, "ntriples"), format="ntriples")
    return graph


# ==========================================================
#  Leases
# ==========================================================
class LeaseKeeper:
    """Hold named leases and renew them from a background thread until released or lost."""

    def __init__(self, dbI=None, ttl=LEASE_TTL, holder=None, logger=None):
        self.dbI = dbI or getStateDB()
        self.ttl = ttl
        self.holder = holder or getHolderID()
        self.logger = logger
        self._held = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def _log(self, msg):
        """Log through the logger when available."""
        if self.logger:
            self.logger.info(msg)

    def _ensureThread(self):
        """Start the renew thread once."""
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._renewLoop, name="LeaseKeeper", daemon=True)
        self._thread.start()

    def _renewLoop(self):
        """Renew held leases every ttl/3 seconds; drop the ones taken by someone else."""
        while not self._stop.wait(max(1, self.ttl // 3)):
            with self._lock:
                names = list(self._held)
            for name in names:
                try:
                    ok = self.dbI.leaseacquire(name, self.holder, self.ttl)
                except Exception as ex:  # pylint: disable=broad-except
                    self._log(f"Lease {name} renew failed: {ex}")
                    ok = False
                with self._lock:
                    if ok and name in self._held:
                        self._held[name] = getUTCnow() + self.ttl
                    elif not ok:
                        self._held.pop(name, None)
                        self._log(f"Lost lease {name}")

    def acquire(self, name):
        """Take or keep a lease; return True if held."""
        if self.held(name):
            return True
        try:
            ok = self.dbI.leaseacquire(name, self.holder, self.ttl)
        except Exception as ex:  # pylint: disable=broad-except
            self._log(f"Lease {name} acquire failed: {ex}")
            return False
        if ok:
            with self._lock:
                self._held[name] = getUTCnow() + self.ttl
            self._ensureThread()
        return ok

    def held(self, name):
        """Return True if the lease is held and not past its expiry."""
        with self._lock:
            return self._held.get(name, 0) > getUTCnow()

    def heldNames(self):
        """Return names of currently held leases."""
        with self._lock:
            return [name for name, exp in self._held.items() if exp > getUTCnow()]

    def release(self, name):
        """Release one lease."""
        with self._lock:
            self._held.pop(name, None)
        try:
            self.dbI.leaserelease(name, self.holder)
        except Exception as ex:  # pylint: disable=broad-except
            self._log(f"Lease {name} release failed: {ex}")

    def releaseAll(self):
        """Release all leases and stop renewing."""
        self._stop.set()
        for name in self.heldNames():
            self.release(name)


def _hrwScore(member, item):
    """Rendezvous hashing score of an item for a member."""
    return hashlib.md5(f"{member}|{item}".encode()).hexdigest()


class Sharder:
    """Split items (devices) between live replicas of a component; each item is owned by one replica at a time."""

    def __init__(self, component, dbI=None, ttl=LEASE_TTL, holder=None, logger=None):
        self.component = component
        self.keeper = LeaseKeeper(dbI=dbI, ttl=ttl, holder=holder, logger=logger)
        self.dbI = self.keeper.dbI
        self.memberLease = f"member:{component}:{self.keeper.holder}"
        self.itemPrefix = f"item:{component}:"

    def members(self):
        """Return sorted holders of live member leases, including this replica."""
        live = {row["holder"] for row in self.dbI.leaselive(f"member:{self.component}:")}
        live.add(self.keeper.holder)
        return sorted(live)

    def myShare(self, items):
        """Return the items this replica owns now (assigned by rendezvous hashing and leased)."""
        self.keeper.acquire(self.memberLease)
        members = self.members()
        assigned = [item for item in items if max(members, key=lambda mem, it=item: _hrwScore(mem, it)) == self.keeper.holder]
        owned = [item for item in assigned if self.keeper.acquire(f"{self.itemPrefix}{item}")]
        # Give up items moved to another replica (or removed from the config) so they can be taken over.
        for name in self.keeper.heldNames():
            if name.startswith(self.itemPrefix) and name[len(self.itemPrefix) :] not in owned:
                self.keeper.release(name)
        return owned

    def release(self):
        """Leave the member set and release all items."""
        self.keeper.releaseAll()
