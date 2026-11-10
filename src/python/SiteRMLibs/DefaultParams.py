#!/usr/bin/env python3
"""
Default parameters for SiteRM libraries
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""

# Default parameters for SiteRM libraries
# Defaults for limit queries (used in most of them)
# These are used in various parts of the code to limit the number of results returned from database
LIMIT_DEFAULT = 50
LIMIT_MIN = 1
LIMIT_MAX = 100
# Default parameters for service queries (Identify that service is up and running)
LIMIT_SERVICE_DEFAULT = 500
LIMIT_SERVICE_MIN = 1
LIMIT_SERVICE_MAX = 1000

# Service policies
# Not accept requests if service not updated state for 2 minutes
SERVICE_NOACCEPT_TIMEOUT = 120
# Mark service as down if not updated for 5 minutes
SERVICE_DOWN_TIMEOUT = 300
# Mark service as dead if not updated for 10 minutes
SERVICE_DEAD_TIMEOUT = 600
# Auto refresh of git configuration if changes only every 15 minutes
GIT_CONFIG_REFRESH_TIMEOUT = 900
# Grace period for a continuously not-ready / not-alive SiteRM Frontend before
# the daemon escalates it to a reported FAILED state (and thus an alert). Up to
# this many seconds (10 minutes) of back-to-back HTTPServerNotReady is logged
# only; past it the service reports FAILED so liveness/readiness and central
# monitoring pick it up.
HTTP_SERVER_NOT_READY_ALERT_TIMEOUT = 600
# Time for delta to receive commit message (5 minutes)
DELTA_COMMIT_TIMEOUT = 300
# Time a delta POST waits for PolicyService to accept or reject the delta
DELTA_ACCEPT_TIMEOUT = 50
# Delta POST Idempotency-Key still in progress without any PolicyService result after
# this many seconds (and no queued delta file) is treated as lost, so a retry resubmits it (5 minutes)
IDEMPOTENCY_STALE_TIMEOUT = 300
# Time for delta to be removed from database (1 hour)
DELTA_REMOVE_TIMEOUT = 3600
# Mark BGP monitoring data as stale if not updated for 70 minutes (hourly cycle + margin)
BGP_MONITORING_DOWN_TIMEOUT = 4200

# Shared state between FE components (SiteRMLibs.DBState)
# Lease lifetime for leader roles, devices and membership; renewed every LEASE_TTL / 3 seconds
LEASE_TTL = 60
# FE components that must have exactly one active instance; extra replicas wait as standby
FE_LEADER_COMPONENTS = [
    "LookUpService",
    "PolicyService",
    "ProvisioningService",
    "DBWorker",
    "DBCleaner",
    "ValidatorService",
    "Debugger",
]
# FE components that split devices between their replicas
FE_SHARDED_COMPONENTS = ["SwitchManager", "SNMPMonitoring", "BGPMonitoring"]
# LookUpService first run waits this long for ProvisioningService first run, then for fresh switch data
FIRSTRUN_PROVISION_WAIT = 1800
FIRSTRUN_SWITCHDATA_WAIT = 300

# Database retention (seconds) used by DBCleaner; override with daemoncontrols.DBCleaner.retention.<key>
DB_RETENTION = {
    # Tables cleaned by their update/insert timestamp
    "debugrequests": 3 * 86400,
    "deltas": 7 * 86400,
    "deltatimestates": 7 * 86400,
    "hosts": 7 * 86400,
    "services": 7 * 86400,
    "servicestates": 7 * 86400,
    "states": 7 * 86400,
    "hoststates": 7 * 86400,
    "hoststateshistory": 7 * 86400,
    "switch": 7 * 86400,
    "snmpmon": 7 * 86400,
    "bgpmon": 7 * 86400,
    "activeDeltas": 7 * 86400,
    "instancestartend": 7 * 86400,
    "deltasusertracking": 7 * 86400,
    "deltaidempotency": 7 * 86400,
    "debugworkers": 7 * 86400,
    # Signals read by every replica (not deleted on read); must outlive GIT_CONFIG_REFRESH_TIMEOUT
    "serviceaction": 2 * 3600,
    "bgpforcerescan": 3600,
    # Delta submissions: result is deleted when REST reads it; this drops unread/lost ones
    "deltarequests": 3600,
    # Models: keep the last 24h, at most MODEL_MAX_COUNT; the latest model is always kept
    "models": 86400,
    # Stale per-instance FE service states (scaled replicas that no longer exist)
    "servicestates_instance": 3600,
    # Expired leases
    "leases": 3600,
    # kvstore namespaces (missing namespace = kept until overwritten/deleted by its owner)
    "kv:m2m": 300,
    "kv:switchupdate": 86400,
    "kv:snapshot": 86400,
    # Disabled-probe records are refreshed by every probe run while disabled
    "kv:probes": 600,
}
MODEL_MAX_COUNT = 100
# Tables rebuilt once a day so deleted large rows return disk space (InnoDB keeps freed pages otherwise)
DB_OPTIMIZE_TABLES = ["modelcontent", "deltarequests", "debugrequests", "kvstore", "hosts", "services"]
DB_OPTIMIZE_INTERVAL = 86400
