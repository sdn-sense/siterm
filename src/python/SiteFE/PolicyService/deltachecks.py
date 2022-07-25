#!/usr/bin/env python3
"""Check for conflicting deltas

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import copy
from datetime import datetime
from collections import namedtuple
from DTNRMLibs.MainUtilities import getUTCnow
#from DTNRMLibs.CustomExceptions import OverlapException
from DTNRMLibs.CustomExceptions import BadRequestError


class ConflictChecker():
    """Conflict Checker"""
    def __init__(self):
        self.allTimes = {}
        self.allIPs = {}
        self.allVlans = {}

    def _getAllParams(self, config):
        """Get All Params from parsed Model dict"""
        for svc, svcitems in config.items():
            if svc in ['SubnetMapping', 'RoutingMapping']:
                continue
            for connID, connItems in svcitems.items():
                for hostname, vals in connItems.items():
                    if hostname == '_params':
                        self._getTimings(connID, vals)
                    #elif isinstance(vals, dict):
                    #    for intf, intfDict in vals.items():
                    #        print(intf)

    def _getTimings(self, connID, params):
        """Get Runtime params"""
        if params and 'existsDuring' in params:
            if 'end' in params['existsDuring'] and \
               'start' in params['existsDuring']:
                self.allTimes.setdefault(connID, [])
                self.allTimes[connID].append([params['existsDuring']['start'],
                                              params['existsDuring']['end']])

    def _getAllIPs(self, newConfig):
        """Get All IPs from config"""
        return

    def _getAllVlans(self, newConfig):
        """Get all Vlans from config"""
        return

    def _checksvc(self, svc, activeDeltas):
        """Check that unknown svc are in delta"""
        if svc not in ['vsw', 'rst', 'SubnetMapping', 'RoutingMapping']:
            raise BadRequestError('Service does not exist. Requested %s' % svc)
        if svc not in activeDeltas:
            return True
        return False

    @staticmethod
    def _checkTime(intfDict, activeDeltas):
        """Check that times do not overlap"""
        # Need to load all times from active deltas in advance
        # If we have many checks, it will be faster if all active
        # delta times are preloaded
        return

    @staticmethod
    def _checkIP(intfDict, activeDeltas):
        """Check if IPs do not conflict"""
        # Need to check if IP is valid and from our supported ranges
        # Seems Orchestrator ignores this check
        if 'hasNetworkAddress' in intfDict:
            return
        return
    #                                    'hasNetworkAddress': {'type': 'unverifiable|ipv4-address',
    #                                                          'value': '10.251.85.2/24'},
    @staticmethod
    def _checkService(intfDict, activeDeltas):
        """Check If service has all params"""
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

    def _checkLabel(self, intfDict, activeDeltas):
        """Check Labels"""
        # Need to check if vlan in supported.
        # Also if addition - check that it does not overlap
        # In case modify - ensure it exists and preconfigured
        if  'hasLabel' in intfDict:
            return
        return
    #'hasLabel': {'labeltype': 'ethernet#vlan',
    #             'value': 1791}
    def _checkHosts(self, hostname, activeDeltas):
        """Check Hosts"""
        # Check if hostname is known. If not known
        # Delta will not be activated
        return

    def _checkInterface(self, hostname, interface, activeDeltas):
        """Check interface"""
        # Check if hostname has that interface and
        # Orchestrator is allowed to control that.
        self._checkHosts(hostname, activeDeltas)
        return

    def _checkParams(self, inVals, activeDeltas):
        """Check all parameters in activeDeltas"""
        # Things to check:
        if 'existsDuring' in inVals:
            self._checkTime(inVals['existsDuring'], activeDeltas)
        return
    #{'_params': {'belongsTo': 'urn:ogf:network:ultralight.org:2013:service+vsw:dellos9_s0:conn+ccdc7cb5-025c-428e-96d2-b9ba51def912:resource+links-Connection_1:vlan+1791',
    #             'existsDuring': {'end': 1639433000, 'start': 1639346600},
    #             'labelSwapping': 'false',
    #             'tag': 'urn:ogf:network:service+ccdc7cb5-025c-428e-96d2-b9ba51def912:resource+links::Connection_1'}

    def checkConflicts(self, cls, newConfig, oldConfig):
        """Check conflicting resources and not allow them"""
        resourceConflicts = False
        self._getAllParams(newConfig)
        if not oldConfig:
            return resourceConflicts
        if newConfig == oldConfig:
            return resourceConflicts
        for svc, svcitems in newConfig.items():
            if self._checksvc(svc, oldConfig):
                continue
            if svc in ['SubnetMapping', 'RoutingMapping']:
                continue
            if svc == 'vsw':
                # Virtual Switching Service
                #resourceConflicts = self.checkvsw()
                print(1)
            if svc == 'rst':
                # Routing Service
                # resourceConflicts = self.checkrst()
                print(1)
            for _connID, connIDitems in svcitems.items():
                for hostname, vals in connIDitems.items():
                    if hostname == '_params':
                        self._checkParams(vals, oldConfig)
                        # If times overlap, we should check
                        # that there are no conflicts and use of same IP Range
                        # Also that vlan is not in use.
                        # If they are not overlapping - good to continue
                        continue
                    if isinstance(vals, dict):
                        for intf, intfDict in vals.items():
                            self._checkInterface(hostname, intf, oldConfig)
                            self._checkIP(intfDict, oldConfig)
                            self._checkService(intfDict, oldConfig)
                            self._checkLabel(intfDict, oldConfig)
                            # TODO: This should also include later check for RST
                            # And for routing information. Need to check if all info is good.
        return False

    def serviceEnded(self, indict):
        """Check if Service Ended"""
        if 'end' in indict:
            if getUTCnow() > indict['end']:
                return True
        return False

    def checkActiveConfig(self, activeConfig):
        """Check all Active Config"""
        newconf = copy.deepcopy(activeConfig)
        cleaned = []
        for host, pSubnets in activeConfig.get('SubnetMapping', {}).items():
            for subnet, _ in pSubnets.get('providesSubnet', {}).items():
                if 'existsDuring' in activeConfig.get('vsw', {}).get(subnet, {}).get('_params', {}):
                    clean = self.serviceEnded(activeConfig['vsw'][subnet]['_params']['existsDuring'])
                    if clean:
                        cleaned.append(subnet)
                        newconf['SubnetMapping'][host]['providesSubnet'].pop(subnet)
                        newconf['vsw'].pop(subnet)
        return newconf, cleaned

    def overlap_count(self, times1, times2):
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

    # def compareTwoDeltaTimes(self, deltaInDB, deltaIN):
    #     for dInhost, dInvlan in deltaIN['hosts'].items():
    #         if dInhost in deltaInDB['hosts'].keys() and deltaInDB['hosts'][dInhost] == dInvlan:
    #             overlap = overlap_count(deltaInDB['times'], deltaIN['times'])
    #             if overlap:
    #                 msg = 'New delta request overlaps with delta %s in %s state. Overlap time: %s' % (deltaInDB['uid'], deltaInDB['state'], overlap)
    #                 raise OverlapException(msg)
