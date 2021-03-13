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


def checkConflicts(dbObj, delta):
    """Check conflicting resources and not allow them"""
    delta['addition'] = evaldict(delta['addition'])
    for connDelta in delta['addition']:
        deltaIN = getdeltaInfo(connDelta, delta)
        checkNewDelta(deltaIN)
        for state in ['committing', 'committed', 'activating', 'activated']:
            for deltat in ['addition', 'modify']:
                for dbdelta in dbObj.get('deltas', search=[['state', state], ['deltat', deltat]]):
                    print(dbdelta)
                    dbdelta['addition'] = evaldict(dbdelta['addition'])
                    for connDelta1 in dbdelta['addition']:
                        deltaInDB = getdeltaInfo(connDelta1, delta)
                        compareTwoDeltaTimes(deltaInDB, deltaIN)


def checkNewDelta(deltaIn):
    """Check if new delta can be provisioned"""
    # We check only timing is ok here. All other cases are checked
    # by deltas comparison (vlan, host, timings)
    if getUTCnow() >= deltaIn['times'][1]:
        raise BadRequestError('New delta endtime is in the past. Nothing to configure.')


def getdeltaInfo(deltaAd, delta):
    """Get Delta Info (timestart, timeend, vlan, hostname) for comparison."""
    out = {'times': [], 'hosts': {}, 'state': '', 'uid': ''}
    print(deltaAd)
    out['state'] = delta['state']
    out['uid'] = delta['uid']
    out['conID'] = deltaAd['connectionID']
    if 'timestart' in deltaAd.keys():
        out['times'].append(deltaAd['timestart'])
    else:
        out['times'].append(0)
    if 'timeend' in deltaAd.keys():
        out['times'].append(deltaAd['timestart'])
    else:
        # As much as we can Jan 19, 2038
        out['times'].append(2147483648)
    # Add all hosts, any overlapping host + vlan - will do timing check.
    for hostname, hostdict in deltaAd['hosts'].items():
        # Catch KeyError: 'vlan' - this can happen multiple endpoints submit same time
        # And delta is not full as parts are inside the model.
        try:
            out['hosts'][hostname] = hostdict['vlan']
        except KeyError:
            raise DeltaKeyMissing('New delta request does not have vlan information. Failing')
    return out


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
