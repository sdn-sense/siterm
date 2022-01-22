#!/usr/bin/env python3
"""Check for conflicting deltas

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import copy
from datetime import datetime
from collections import namedtuple
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import OverlapException
from DTNRMLibs.CustomExceptions import DeltaKeyMissing
from DTNRMLibs.CustomExceptions import BadRequestError


def _checksvc(svc, activeDeltas):
    if svc not in ['vsw', 'rst', 'SubnetMapping']:
        raise BadRequestError('Service does not exist. Requested %s' % svc)
    if svc not in activeDeltas:
        return True
    return False

def _checkTime(intfDict, activeDeltas):
    # Need to load all times from active deltas in advance
    # If we have many checks, it will be faster if all active
    # delta times are preloaded
    return

def _checkIP(intfDict, activeDeltas):
    # Need to check if IP is valid and from our supported ranges
    # Seems Orchestrator ignores this check
    if 'hasNetworkAddress' in intfDict:
        return
    return
#                                    'hasNetworkAddress': {'type': 'unverifiable|ipv4-address',
#                                                          'value': '10.251.85.2/24'},


def _checkService(intfDict, activeDeltas):
    if 'hasService' in intfDict:
        return
    return
#'hasService': {'availableCapacity': 1000000000,
#                                                    'granularity': 1000000,
#                                                    'maximumCapacity': 1000000000,
#                                                    'priority': 0,
#                                                    'reservableCapacity': 1000000000,
#                                                    'type': 'guaranteedCapped',
#                                                    'unit': 'bps'}



def _checkLabel(intfDict, activeDeltas):
    # Need to check if vlan in supported.
    # Also if addition - check that it does not overlap
    # In case modify - ensure it exists and preconfigured
    if  'hasLabel' in intfDict:
        return
    return
#'hasLabel': {'labeltype': 'ethernet#vlan',
#             'value': 1791}



def _checkHosts(hostname, activeDeltas):
    # Check if hostname is known. If not known
    # Delta will not be activated
    return

def _checkInterface(hostname, interface, activeDeltas):
    # Check if hostname has that interface and
    # Orchestrator is allowed to control that.
    _checkHosts(hostname, activeDeltas)
    return

def _checkParams(inVals, activeDeltas):
    # Things to check:
    if 'existsDuring' in inVals:
        _checkTime(inVals['existsDuring'], activeDeltas)
    # labelSwapping - check with config param if supported
    return
#{'_params': {'belongsTo': 'urn:ogf:network:ultralight.org:2013:service+vsw:dellos9_s0:conn+ccdc7cb5-025c-428e-96d2-b9ba51def912:resource+links-Connection_1:vlan+1791',
#             'existsDuring': {'end': 1639433000, 'start': 1639346600},
#             'labelSwapping': 'false',
#             'tag': 'urn:ogf:network:service+ccdc7cb5-025c-428e-96d2-b9ba51def912:resource+links::Connection_1'}


def checkConflicts(dbObj, delta):
    """Check conflicting resources and not allow them"""
    delta['addition'] = evaldict(delta['addition'])
    activeDeltas = dbObj.get('activeDeltas')
    if not activeDeltas:
        return
    activeDeltas = evaldict(activeDeltas[0]['output'])
    for svc, svcitems in delta['addition'].items():
        if _checksvc(svc, activeDeltas):
            continue
        if svc == 'SubnetMapping':
            continue
        for connID, connIDitems in svcitems.items():
            import pprint
            print(connID)
            pprint.pprint(connIDitems)
            for hostname, vals in connIDitems.items():
                if hostname == '_params':
                    _checkParams(vals, activeDeltas)
                    continue
                if isinstance(vals, dict):
                    for intf, intfDict in vals.items():
                        _checkInterface(hostname, intf, activeDeltas)
                        _checkIP(intfDict, activeDeltas)
                        _checkService(intfDict, activeDeltas)
                        _checkLabel(intfDict, activeDeltas)
                        # TODO: This should also include later check for RST
                        # And for routing information. Need to check if all info is good.

def serviceEnded(indict):
    if 'end' in indict:
        if getUTCnow() > indict['end']:
            return True
    return False

def checkActiveConfig(activeConfig):
    newconf = copy.deepcopy(activeConfig)
    cleaned = []
    for host, pSubnets in activeConfig.get('SubnetMapping', {}).items():
        for subnet, _ in pSubnets.get('providesSubnet', {}).items():
            if 'existsDuring' in activeConfig.get('vsw', {}).get(subnet, {}).get('_params', {}):
                clean = serviceEnded(activeConfig['vsw'][subnet]['_params']['existsDuring'])
                if clean:
                    cleaned.append(subnet)
                    newconf['SubnetMapping'][host]['providesSubnet'].pop(subnet)
                    newconf['vsw'].pop(subnet)
    return newconf, cleaned


def overlap_count(times1, times2):
    """Find out if times overlap."""
    Range = namedtuple('Range', ['start', 'end'])
    t1 = Range(start=datetime.fromtimestamp(times1[0]), end=datetime.fromtimestamp(times1[1]))
    t2 = Range(start=datetime.fromtimestamp(times2[0]), end=datetime.fromtimestamp(times2[1]))
    latestStart = max(t1.start, t2.start)
    earliestEnd = min(t1.end, t2.end)
    delta = (earliestEnd - latestStart).seconds
    overlap = max(0, delta)
    if earliestEnd < latestStart:
        overlap = 0
    return overlap


def compareTwoDeltaTimes(deltaInDB, deltaIN):
    for dInhost, dInvlan in deltaIN['hosts'].items():
        if dInhost in deltaInDB['hosts'].keys() and deltaInDB['hosts'][dInhost] == dInvlan:
            overlap = overlap_count(deltaInDB['times'], deltaIN['times'])
            if overlap:
                msg = 'New delta request overlaps with delta %s in %s state. Overlap time: %s' % (deltaInDB['uid'], deltaInDB['state'], overlap)
                raise OverlapException(msg)
