#!/usr/bin/env python3
"""Check for conflicting deltas

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
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) caltech.edu
@Copyright              : Copyright (C) 2021 California Institute of Technology
Date                    : 2021/03/04
"""
from datetime import datetime
from collections import namedtuple
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import OverlapException
from DTNRMLibs.CustomExceptions import DeltaKeyMissing
from DTNRMLibs.CustomExceptions import BadRequestError


def _checksvc(svc, activeDeltas):
    if svc not in ['vsw', 'rst']:
        raise Exception
    if svc not in activeDeltas:
        return True
    return False

def _checkTime(inVals, activeDeltas):
    print(inVals, activeDeltas)
    return

def _checkIP(inVals, activeDeltas):
    print(inVals, activeDeltas)
    return

def _checkService(inVals, activeDeltas):
    print(inVals, activeDeltas)
    return

def _checkLabel(inVals, activeDeltas):
    print(inVals, activeDeltas)
    return

def checkConflicts(dbObj, delta):
    """Check conflicting resources and not allow them"""
    delta['addition'] = evaldict(delta['addition'])
    activeDeltas = dbObj.get('activeDeltas')
    # TODO: Check if it is not empty. if empty, return
    if not activeDeltas:
        return
    for svc, svcitems in delta['addition'].items():
        if _checksvc(svc, activeDeltas):
            continue
        for connID, connIDitems in svcitems.items():
            for hostname, vals in connIDitems.items():
                if hostname == 'existsDuring':
                    _checkTime(vals, activeDeltas)
                    # Pass it to timecheck
                if isinstance(vals, dict):
                    for intf, intfDict in vals.items():
                        if 'hasNetworkAddress' in intfDict:
                            _checkIP(intfDict['hasNetworkAddress'], activeDeltas)
                        if 'hasService' in intfDict:
                            _checkService(intfDict['hasService'], activeDeltas)
                        if 'hasLabel' in intfDict:
                            _checkLabel(intfDict['hasLabel'], activeDeltas)
                        # TODO: This should also include later check for RST
                        # And for routing information. Need to check if all info is good.

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
