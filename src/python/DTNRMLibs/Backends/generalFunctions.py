#!/usr/bin/env python3
# pylint: disable=E1101
"""
General functions for Backends

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import copy

def checkConfig(config, site):
    """Get info from config and ensure all params correct."""
    if not config.has_section(site):
        msg = f'SiteName {site} is not defined'
        raise Exception(msg)
    for key in ['plugin', 'switch']:
        if not config.has_option(site, key):
            msg = f'Option {key} is not defined in Site Config. Return'
            raise Exception(msg)

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

def getValFromConfig(config, switch, port, key, portKey="port_%s_%s"):
    """Get val from config."""
    tmpVal = config.get(switch, portKey % (port, key))
    try:
        tmpVal = int(tmpVal)
    except ValueError:
        pass
    return tmpVal


def getConfigParams(config, switch, cls=None):
    """
    Get config params from yaml. like what ports allowed to use
    and which to ignore, which vlans for port, or what default vlan range to use
    """
    ports = []
    vlanRange = ""
    portsIgnore = []
    if config.has_option(switch, 'allports') and config.get(switch, 'allports'):
        ports = cls.plugin.getports(cls.switches['output'][switch])
    elif config.has_option(switch, 'ports'):
        ports = config.get(switch, 'ports').split(',')
    if config.has_option(switch, 'vlan_range'):
        vlanRange = config.get(switch, 'vlan_range')
    if config.has_option(switch, 'ports_ignore'):
        portsIgnore = config.get(switch, 'ports_ignore').split(',')
    return ports, vlanRange, portsIgnore
