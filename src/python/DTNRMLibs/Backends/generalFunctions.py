#!/usr/bin/env python3
"""
    General functions for Lookup Service Plugins

Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2021 California Institute of Technology
Date            : 2021/11/08
"""
import copy
from ipaddress import ip_address, IPv4Address

def checkConfig(config, logger, site):
    """Get info from config and ensure all params correct."""
    if not config.has_section(site):
        logger.info('SiteName %s is not defined' % site)
        return True
    logger.debug('Looking for switch config for %s site' % site)
    # These config parameters are mandatory. In case not available, return empty list
    for key in ['plugin', 'switch']:
        if not config.has_option(site, key):
            logger.info('Option %s is not defined in Site Config. Return' % key)
            return True
    return False

def cleanupEmpty(output):
    """Final check remove empty dicts/lists inside output."""
    tmpOut = copy.deepcopy(output)
    for swn, swd in list(output['switches'].items()):
        if not swd:
            del tmpOut['switches'][swn]
            continue
        for swp, swpVal in list(output['switches'][swn].items()):
            if not swpVal and not output.get('ports', {}).get(swn, {}).get(swp, {}).get('isAlias'):
                del tmpOut['switches'][swn][swp]
                continue
    return tmpOut

def getValFromConfig(config, switch, port, key):
    """Get val from config."""
    tmpVal = config.get(switch, "port%s%s" % (port, key))
    try:
        tmpVal = int(tmpVal)
    except ValueError:
        pass
    return tmpVal


def validIPAddress(ipInput):
    """ Check if IP is valid.
        Input: str
        Returns: (one of) IPv4, IPv6, Invalid"""
    try:
        return "IPv4" if isinstance(ip_address(ipInput), IPv4Address) else "IPv6"
    except ValueError:
        return "Invalid"
