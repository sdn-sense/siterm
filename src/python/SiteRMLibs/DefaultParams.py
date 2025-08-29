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
# Auto refresh of git configuration time in seconds (In case forced via API)
GIT_CONFIG_REFRESH_TIMEOUT = 300
# Time for delta to receive commit message (5 minutes)
DELTA_COMMIT_TIMEOUT = 300
# Time for delta to be removed from database (1 hour)
DELTA_REMOVE_TIMEOUT = 3600
