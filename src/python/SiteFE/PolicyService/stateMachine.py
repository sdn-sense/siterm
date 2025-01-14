#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Everything goes here when they do not fit anywhere else.

Copyright 2017 California Institute of Technology
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
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2018/11/26
"""
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import getLoggingObject

class ConnectionMachine():
    """Connection State machine.Maps Deltas with 1 to N connections"""
    def __init__(self, config):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='PolicyService')

    @staticmethod
    def accepted(dbObj, delta):
        """If delta addition and accepted - add connection entry in DB"""
        if delta['deltat'] in ['addition', 'modify'] and delta['state'] in ['accepting', 'accepted']:
            for connid in evaldict(delta['connectionid']):
                dbOut = {'deltaid': delta['uid'],
                         'connectionid': connid,
                         'state': 'accepted'}
                dbObj.insert('delta_connections', [dbOut])

    @staticmethod
    def committed(dbObj, delta):
        """Change specific delta connection id state to commited."""
        if delta['deltat'] in ['addition', 'modify']:
            for connid in evaldict(delta['connectionid']):
                dbOut = {'deltaid': delta['uid'],
                         'connectionid': connid,
                         'state': 'committed'}
                dbObj.update('delta_connections', [dbOut])

    @staticmethod
    def activating(dbObj, delta):
        """Change specific delta connection id state to commited."""
        if delta['deltat'] in ['addition', 'modify']:
            for connid in evaldict(delta['connectionid']):
                dbOut = {'deltaid': delta['uid'],
                         'connectionid': connid,
                         'state': 'activating'}
                dbObj.update('delta_connections', [dbOut])

    @staticmethod
    def activated(dbObj, delta):
        """Change specific delta connection id state to activated. Reduction - cancelled"""
        if delta['deltat'] in ['addition', 'modify']:
            for connid in evaldict(delta['connectionid']):
                dbOut = {'deltaid': delta['uid'],
                         'connectionid': connid,
                         'state': 'activated'}
                dbObj.update('delta_connections', [dbOut])
        elif delta['deltat'] == 'reduction':
            for connid in evaldict(delta['connectionid']):
                for dConn in dbObj.get('delta_connections', search=[['connectionid', connid], ['state', 'activated']]):
                    dbOut = {'deltaid': dConn['deltaid'],
                             'connectionid': dConn['connectionid'],
                             'state': 'cancelled'}
                    dbObj.update('delta_connections', [dbOut])


class StateMachine():
    """State machine for Frontend and policy service."""
    def __init__(self, config):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='PolicyService')
        self.limit = 100
        self.connMgr = ConnectionMachine(config)

    def stateChangerDelta(self, dbObj, newState, **kwargs):
        """Delta State change."""
        tNow = getUTCnow()
        self.logger.info(f"Changing delta {kwargs['uid']} to {newState}")
        dbObj.update('deltas', [{'uid': kwargs['uid'],
                                 'state': newState,
                                 'updatedate': tNow}])
        dbObj.insert('states', [{'deltaid': kwargs['uid'],
                                 'state': newState,
                                 'insertdate': tNow}])

    @staticmethod
    def modelstatechanger(dbObj, newState, **kwargs):
        """Model State change."""
        tNow = getUTCnow()
        dbObj.update('deltasmod', [{'uid': kwargs['uid'],
                                    'modadd': newState,
                                    'updatedate': tNow}])

    def modelstatecancel(self, dbObj, **kwargs):
        """Cancel Model addition."""
        if kwargs['modadd'] in ['idle']:
            self.modelstatechanger(dbObj, 'removed', **kwargs)
        elif kwargs['modadd'] in ['add', 'added']:
            self.modelstatechanger(dbObj, 'remove', **kwargs)

    def stateChangerHost(self, dbObj, hid, **kwargs):
        """Change state for host."""
        tNow = getUTCnow()
        self.logger.info(f"Changing delta {kwargs['deltaid']} hoststate {kwargs['hostname']} to {kwargs['state']}")
        dbObj.update('hoststates', [{'deltaid': kwargs['deltaid'],
                                     'state': kwargs['state'],
                                     'updatedate': tNow,
                                     'id': hid}])
        dbObj.insert('hoststateshistory', [kwargs])

    def _newdelta(self, dbObj, delta, state):
        """Add new delta to db."""
        dbOut = {'uid': delta['ID'],
                 'insertdate': int(delta['InsertTime']),
                 'updatedate': int(delta['UpdateTime']),
                 'state': str(state),
                 'deltat': str(delta['Type']),
                 'content': str(delta['Content']),
                 'modelid': str(delta['modelId']),
                 'modadd': str(delta['modadd']),
                 'error': '' if 'Error' not in list(delta.keys()) else str(delta['Error'])}
        dbObj.insert('deltas', [dbOut])
        self.connMgr.accepted(dbObj, dbOut)
        dbOut['state'] = delta['State']
        self.stateChangerDelta(dbObj, delta['State'], **dbOut)

    @staticmethod
    def _newhoststate(dbObj, **kwargs):
        """Private to add new host states."""
        tNow = getUTCnow()
        kwargs['insertdate'] = tNow
        kwargs['updatedate'] = tNow
        dbObj.insert('hoststates', [kwargs])

    def accepted(self, dbObj, delta):
        """Marks delta as accepting."""
        self._newdelta(dbObj, delta, 'accepting')

    def commit(self, dbObj, delta):
        """Marks delta as committing."""
        self.stateChangerDelta(dbObj, 'committing', **delta)

    def stateChange(self, dbObj, delta):
        """Set new state for delta."""
        self.stateChangerDelta(dbObj, delta['state'], **delta)

    def committing(self, dbObj):
        """Committing state Check."""
        for delta in dbObj.get('deltas', search=[['state', 'committing']]):
            self.stateChangerDelta(dbObj, 'committed', **delta)
            self.modelstatechanger(dbObj, 'add', **delta)
            self.connMgr.committed(dbObj, delta)

    def committed(self, dbObj):
        """Committed state Check."""
        for delta in dbObj.get('deltas', search=[['state', 'committed']]):
            self.stateChangerDelta(dbObj, 'activating', **delta)

    def activating(self, dbObj):
        """Check on all deltas in state activating."""
        for delta in dbObj.get('deltas', search=[['state', 'activating']]):
            # Delay making active for 30seconds. Allow agents and switchworker to apply.
            tNow = getUTCnow()
            deltaupdated = delta.get('updatedate', tNow)
            if (tNow - deltaupdated) <= 30:
                self.logger.info(f"Delta {delta['uid']} is not ready to be activated. Waiting for 30 seconds")
                self.logger.info(f"Current time {tNow} - Delta updated time {deltaupdated} = Diff: {tNow - deltaupdated}")
                continue
            if delta['modadd'] in ['added', 'removed']:
                self.stateChangerDelta(dbObj, 'activated', **delta)
            if delta['modadd'] == 'failed':
                self.stateChangerDelta(dbObj, 'failed', **delta)

    def activated(self, dbObj):
        """Check on all activated state deltas."""
        for delta in dbObj.get('deltas', search=[['state', 'activated']]):
            if delta['modadd'] == 'removed':
                self.stateChangerDelta(dbObj, 'remove', **delta)

    def remove(self, dbObj):
        """Check on all remove state deltas."""
        # Remove fully from database
        for delta in dbObj.get('deltas', search=[['state', 'remove']]):
            if delta['updatedate'] < int(getUTCnow() - 600):
                self.stateChangerDelta(dbObj, 'removed', **delta)
                self.modelstatecancel(dbObj, **delta)

    def removed(self, dbObj):
        """Check on all remove state deltas."""
        # Remove fully from database
        for delta in dbObj.get('deltas', search=[['state', 'removed']]):
            print(f"Remove {delta['id']} delta")
            dbObj.delete('deltas', [['id', delta['id']]])


    def failed(self, dbObj, delta):
        """Marks delta as failed. This is only during submission"""
        self._newdelta(dbObj, delta, 'failed')
