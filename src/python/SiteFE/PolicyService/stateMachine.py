#!/usr/bin/env python3
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
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2018/11/26
"""
from DTNRMLibs.MainUtilities import evaldict
from DTNRMLibs.MainUtilities import getUTCnow
from SiteFE.PolicyService.newDeltaChecks import checkConflicts


def timeendcheck(delta, logger):
    """Check delta timeEnd.

    if passed, returns True.
    """
    # TODO: Check this. might be broken.
    conns = []
    connEnded = False
    for connDelta in delta:
        try:
            if 'timeend' in list(connDelta.keys()):
                timeleft = getUTCnow() - int(connDelta['timeend'])
                logger.info('CurrentTime %s TimeStart %s. TimeLeft %s'
                            % (getUTCnow(), connDelta['timeend'], timeleft))
                if connDelta['timeend'] < getUTCnow():
                    logger.info('This delta already passed timeend mark. \
                                Setting state to cancel')
                    connEnded = True
                else:
                    logger.info('Time did not passed yet.')
        except IOError:
            logger.info('This delta had an error checking endtime. \
                        Leaving state as it is.')
    return connEnded


class ConnectionMachine():
    """Connection State machine.

    Maps Deltas with 1 to N connections
    """
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config

    @staticmethod
    def accepted(dbObj, delta):
        """ If delta addition and accepted - add connection entry in DB """
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
        """Change specific delta connection id state to activated.

        Reduction - cancelled
        """
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
    def __init__(self, logger, config):
        self.logger = logger
        self.config = config
        self.limit = 100
        self.connMgr = ConnectionMachine(logger, config)

    def _stateChangerDelta(self, dbObj, newState, **kwargs):
        """Delta State change."""
        tNow = getUTCnow()
        self.logger.info('Changing delta %s to %s' % (kwargs['uid'], newState))
        dbObj.update('deltas', [{'uid': kwargs['uid'],
                                 'state': newState,
                                 'updatedate': tNow}])
        dbObj.insert('states', [{'deltaid': kwargs['uid'],
                                 'state': newState,
                                 'insertdate': tNow}])

    @staticmethod
    def _modelstatechanger(dbObj, newState, **kwargs):
        """Model State change."""
        tNow = getUTCnow()
        dbObj.update('deltasmod', [{'uid': kwargs['uid'],
                                    'modadd': newState,
                                    'updatedate': tNow}])

    def modelstatecancel(self, dbObj, **kwargs):
        """Cancel Model addition."""
        if kwargs['modadd'] in ['idle']:
            self._modelstatechanger(dbObj, 'removed', **kwargs)
        elif kwargs['modadd'] in ['add', 'added']:
            self._modelstatechanger(dbObj, 'remove', **kwargs)

    def _stateChangerHost(self, dbObj, hid, **kwargs):
        """Change state for host."""
        tNow = getUTCnow()
        self.logger.info('Changing delta %s hoststate %s to %s' %
                         (kwargs['deltaid'], kwargs['hostname'], kwargs['state']))
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
                 'reduction': str(delta['ParsedDelta']['reduction']),
                 'addition': str(delta['ParsedDelta']['addition']),
                 'reductionid': '' if 'ReductionID' not in list(delta.keys()) else delta['ReductionID'],
                 'modadd': str(delta['modadd']),
                 'connectionid': str(delta['ConnID']),
                 'error': '' if 'Error' not in list(delta.keys()) else str(delta['Error'])}
        dbObj.insert('deltas', [dbOut])
        self.connMgr.accepted(dbObj, dbOut)
        dbOut['state'] = delta['State']
        self._stateChangerDelta(dbObj, delta['State'], **dbOut)

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
        self._stateChangerDelta(dbObj, 'committing', **delta)

    def stateChange(self, dbObj, delta):
        """Set new state for delta."""
        self._stateChangerDelta(dbObj, delta['state'], **delta)

    def committing(self, dbObj):
        """Committing state Check."""
        for delta in dbObj.get('deltas', search=[['state', 'committing']]):
            checkConflicts(dbObj, delta)
            # TODO: Check for any conflicts.
            self._stateChangerDelta(dbObj, 'committed', **delta)
            self._modelstatechanger(dbObj, 'add', **delta)
            self.connMgr.committed(dbObj, delta)

    def committed(self, dbObj):
        """Committing state Check."""
        for delta in dbObj.get('deltas', search=[['state', 'committed']]):
            if delta['deltat'] in ['addition', 'modify'] and delta['addition']:
                delta['addition'] = evaldict(delta['addition'])
                # Check the times...
                delayStart = False
                for connDelta in delta['addition']:
                    try:
                        if 'timestart' in list(connDelta.keys()):
                            timeleft = int(connDelta['timestart']) - getUTCnow()
                            self.logger.info('CurrentTime %s TimeStart %s. Seconds Left %s' %
                                             (getUTCnow(), connDelta['timestart'], timeleft))
                            if connDelta['timestart'] < getUTCnow():
                                self.logger.info('This delta already passed timestart mark. \
                                                 Setting state to activating')
                                delayStart = not delayStart
                            else:
                                self.logger.info('This delta %s did not passed timestart mark. \
                                                 Leaving state as it is' % delta['uid'])
                                delayStart = True
                    except:
                        self.logger.info('This delta %s had an error checking starttime. \
                                         Leaving state as it is.' % delta['uid'])
                    if not delayStart:
                        self._stateChangerDelta(dbObj, 'activating', **delta)
                        self.connMgr.activating(dbObj, delta)
            else:
                self.logger.info('This delta %s is in committed. Setting state to activating.' % delta['uid'])
                self._stateChangerDelta(dbObj, 'activating', **delta)
                if delta['deltat'] in ['reduction']:
                    for connid in evaldict(delta['connectionid']):
                        for dConn in dbObj.get('delta_connections', search=[['connectionid', connid]]):
                            self.logger.info('This connection %s belongs to this delta: %s. Cancel delta'
                                             % (connid, dConn['deltaid']))
                            deltaRem = {'uid': dConn['deltaid']}
                            self._stateChangerDelta(dbObj, 'remove', **deltaRem)

    def activating(self, dbObj):
        """Check on all deltas in state activating."""
        for delta in dbObj.get('deltas', search=[['state', 'activating']]):

            delta['reduction'] = evaldict(delta['reduction'])
            if delta['deltat'] == 'addition':
                activeDeltas = dbObj.get('activeDeltas')
                action = 'update'
                if not activeDeltas:
                    action = 'insert'
                    activeDeltas = {'insertdate': int(getUTCnow()),
                                    'output': '{}'}
                activeDeltas['output'] = evaldict(activeDeltas['output'])
                activeDeltas['updatedate'] = int(getUTCnow())
                activeDeltas['output'].update(evaldict(delta['addition']))
                activeDeltas['output'] = str(activeDeltas['output'])
                if action ==  'insert':
                    dbObj.insert('activeDeltas', [activeDeltas])
                elif action == 'update':
                    dbObj.update('activeDeltas', [activeDeltas])
            #for actionKey in ['reduction', 'addition']:
                # TODO: Hosts should be checked only for reduction!
                # Because all endpoints take all activated and apply
                # Reduction also should remove from active config
                # and leave new config without reduction
                # So it is not adding it again
                # if actionKey not in list(delta.keys()):
                #     self.logger.info('This delta %s does not have yet actionKey %s defined.'
                #                      % (delta['uid'], actionKey))
                #     continue
                # if not isinstance(delta[actionKey], list):
                #     self.logger.info('This delta %s does not have yet actionKey defined.' % delta['uid'])
                #     continue
                # for connDelta in delta[actionKey]:
                #     hostStates = {}
                #     if 'hosts' not in list(connDelta.keys()):
                #         self.logger.info('This delta %s does not have yet hosts defined.' % delta['uid'])
                #         continue
                #     for hostname in list(connDelta['hosts'].keys()):
                #         host = dbObj.get('hoststates', search=[['deltaid', delta['uid']], ['hostname', hostname]])
                #         if host:
                #             hostStates[host[0]['state']] = hostname
                #         else:
                #             self._newhoststate(dbObj, **{'hostname': hostname,
                #                                          'state': 'activating',
                #                                          'deltaid': delta['uid']})
                #             hostStates['unset'] = hostname
                # self.logger.info('Delta %s host states are: %s' % (delta['uid'], hostStates))
                # if timeendcheck(delta, self.logger):
                #     self._stateChangerDelta(dbObj, 'cancel', **delta)
                #     self.modelstatecancel(dbObj, **delta)
                # if list(hostStates.keys()) == ['active']:
                #     self._stateChangerDelta(dbObj, 'activated', **delta)
                #     self.connMgr.activated(dbObj, delta)
                # elif 'failed' in list(hostStates.keys()):
                #     self._stateChangerDelta(dbObj, 'failed', **delta)

    def activated(self, dbObj):
        """Check on all activated state deltas."""
        # What to do if activated? Pretty much nothing
        # Might be diff case for reduction;
        for delta in dbObj.get('deltas', search=[['state', 'activated']]):
            # Reduction
            #if delta['deltat'] in ['reduction']:
            #    if delta['updatedate'] < int(getUTCnow() - 600):
            #        self._stateChangerDelta(dbObj, 'removing', **delta)
            #    continue
            # Addition
            self.logger.info('Activated check on delta %s' % delta)
            delta['addition'] = evaldict(delta['addition'])
            #if timeendcheck(delta, self.logger):
            #    self._stateChangerDelta(dbObj, 'cancel', **delta)
            #    self.modelstatecancel(dbObj, **delta)

    def removing(self, dbObj):
        self.logger.info('Removal call')
        return

    def remove(self, dbObj):
        """Check on all remove state deltas."""
        # Remove fully from database
        for delta in dbObj.get('deltas', search=[['state', 'remove']]):
            if delta['updatedate'] < int(getUTCnow() - 600):
                self._stateChangerDelta(dbObj, 'removed', **delta)
                self.modelstatecancel(dbObj, **delta)


    def failed(self, dbObj, delta):
        """Marks delta as failed.

        This is only during submission
        """
        self._newdelta(dbObj, delta, 'failed')
