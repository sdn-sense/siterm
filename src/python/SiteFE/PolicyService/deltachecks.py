#!/usr/bin/env python3
"""Check for conflicting deltas

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import copy
from datetime import datetime
from collections import namedtuple
from ipaddress import IPv4Network, IPv6Network
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import OverlapException


class ConflictChecker():
    """Conflict Checker"""
    def __init__(self):
        self.newid = ""
        self.oldid = ""

    @staticmethod
    def _ipOverlap(ip1, ip2, iptype):
        """Check if IP Overlap. Return True/False"""
        overlap = False
        if not ip1 or not ip2:
            return overlap
        if iptype == 'ipv4':
            net1 = IPv4Network(ip1, False)
            net2 = IPv4Network(ip2, False)
            overlap = net1.subnet_of(net2) or net2.subnet_of(net1)
        if iptype == 'ipv6':
            net1 = IPv6Network(ip1, False)
            net2 = IPv6Network(ip2, False)
            overlap = net1.subnet_of(net2) or net2.subnet_of(net1)
        return overlap

    @staticmethod
    def _checkVlanInRange(polcls, vlan, hostname):
        """Check if VLAN in Allowed range"""
        if not vlan or not vlan.get('vlan', ''):
            return
        # TODO: In future we should exclude all form activeDeltas
        # Which should be done during config preparation and changed
        # everytime activedeltas changes.
        #
        # If switch, check in Switch config
        if hostname in polcls.config.getraw('MAIN'):
            if vlan['vlan'] not in polcls.config.getraw('MAIN').get(hostname, {}).get('vlan_range_list', []):
                raise OverlapException(f'Vlan {vlan} not available for switch {hostname} in configuration. \
                                       Either used or not configured.')
            return
        # If Agent, check in agent reported configuration
        if hostname in polcls.hosts:
            interfaces = polcls.hosts[hostname].get('hostinfo', {}).get('NetInfo', {}).get('interfaces', {})
            if vlan['interface'] not in interfaces:
                raise OverlapException(f'Interface not available for dtn {hostname} in configuration.')
            if vlan['vlan'] not in interfaces.get(vlan['interface'], {}).get('vlan_range_list', {}):
                raise OverlapException(f'Vlan {vlan} not available for dtn {hostname} in configuration. \
                                       Either used or not configured.')
            return
        raise OverlapException('Hostname {hostname} not available in this Frontend.')

    def _checkifIPInRange(self, polcls, ipval, iptype, hostname):
        """Check if IP in Allowed range"""

        def checkOverlap(inrange, ipval, iptype):
            overlap = False
            for vrange in inrange:
                overlap = self._ipOverlap(vrange, ipval, iptype)
                if overlap:
                    return overlap
            return overlap

        if not ipval or not ipval.get(f'{iptype}-address', ''):
            return
        # TODO: In future we should exclude all form activeDeltas
        # Which should be done during config preparation and changed
        # everytime activedeltas changes.
        iptoCheck = ipval[f'{iptype}-address']

        #if hostname in polcls.config.getraw('MAIN'):
        #    inrange = polcls.config.getraw('MAIN').get(hostname, {}).get(f'{iptype}-address-pool-list', [])
        #    overlap = checkOverlap(inrange, iptoCheck, iptype)
        #    if not overlap:
        #        raise OverlapException(f'IP {ipval} not available for {hostname} in configuration. \
        #                  Either used or not configured.')
        #elif hostname in polcls.hosts:
        #    interfaces = polcls.hosts[hostname].get('hostinfo', {}).get('NetInfo', {}).get('interfaces', {})
        #    if ipval['interface'] not in interfaces:
        #        raise OverlapException(f'Interface not available for dtn {hostname} in configuration.')
        #    inrange = interfaces.get(ipval['interface'], {}).get(f'{iptype}-address-pool-list', [])
        #    overlap = checkOverlap(inrange, iptoCheck, iptype)
        #    if not overlap:
        #        raise OverlapException(f'IP {ipval} not available for {hostname} in configuration. \
        #                  Either used or not configured.')
        #else:
        #    raise OverlapException(f'Hostname {hostname} not available in this Frontend.')

    def _checkIfVlanOverlap(self, vlan1, vlan2):
        """Check if Vlan equal. Raise error if True"""
        if vlan1 == vlan2:
            raise OverlapException(f'New Request VLANs Overlap on same controlled resources. \
                                   Overlap resources: {self.newid} and {self.oldid}')

    def _checkIfIPOverlap(self, ip1, ip2, iptype):
        """Check if IP Overlap. Raise error if True"""
        overlap = self._ipOverlap(ip1, ip2, iptype)
        if overlap:
            raise OverlapException(f'New Request {iptype} overlap on same controlled resources. \
                                   Overlap resources: {self.newid} and {self.oldid}')

    @staticmethod
    def _getVlanIPs(dataIn):
        """Get Vlan IPs"""
        out = {}
        for intf, val in dataIn.items():
            out.setdefault('interface', intf)
            for key1, val1 in val.items():
                if key1 == 'hasLabel':
                    out.setdefault('vlan', val1['value'])
                    continue
                if key1 == 'hasNetworkAddress' and 'ipv6-address' in val1:
                    out.setdefault('ipv6-address', val1['ipv6-address']['value'])
                if key1 == 'hasNetworkAddress' and 'ipv4-address' in val1:
                    out.setdefault('ipv4-address', val1['ipv4-address']['value'])
        return out

    @staticmethod
    def _overlap_count(times1, times2):
        """Find out if times overlap."""
        latestStart = max(times1.start, times2.start)
        earliestEnd = min(times1.end, times2.end)
        delta = (earliestEnd - latestStart).seconds
        overlap = max(0, delta)
        if earliestEnd < latestStart:
            overlap = 0
        return overlap

    @staticmethod
    def _getTimings(params):
        """Get Runtime params"""
        dates = [0, 2147483647]
        if params and 'existsDuring' in params:
            if 'start' in params['existsDuring']:
                dates[0] = int(params['existsDuring']['start'])
            if 'end' in params['existsDuring']:
                dates[1] = int(params['existsDuring']['end'])
        Range = namedtuple('Range', ['start', 'end'])
        timeRange = Range(start=datetime.fromtimestamp(dates[0]), end=datetime.fromtimestamp(dates[1]))
        return timeRange

    def _checkIfOverlap(self, newitem, oldItem):
        """Check if 2 deltas overlap for timing"""
        dates1 = self._getTimings(newitem)
        dates2 = self._getTimings(oldItem)
        if self._overlap_count(dates1, dates2):
            return True
        return False

    def checkvsw(self, cls, newConfig, oldConfig):
        """Check vsw Service"""
        for svc, svcitems in newConfig.items():
            if svc in ['SubnetMapping', 'RoutingMapping']:
                continue
            for connID, connItems in svcitems.items():
                self.newid = connID
                # If Connection ID in oldConfig - it is either == or it is a modify call.
                if connID in oldConfig.get(svc, {}):
                    if oldConfig[svc][connID] != connItems:
                        print('MODIFY!!!')
                        # TODO Checks for Modify. For Now just continue
                        continue
                    if oldConfig[svc][connID] == connItems:
                        # No Changes - connID is same, ignoring it
                        continue
                for hostname, hostitems in connItems.items():
                    if hostname == '_params':
                        continue
                    nStats = self._getVlanIPs(hostitems)
                    # Check if vlan is in allowed list;
                    self._checkVlanInRange(cls, nStats, hostname)
                    # check if ip address with-in available ranges
                    self._checkifIPInRange(cls, nStats, 'ipv4', hostname)
                    self._checkifIPInRange(cls, nStats, 'ipv6', hostname)
                    for oldID, oldItems in oldConfig.get(svc, {}).items():
                        # connID == oldID was checked in step3. Skipping it
                        self.oldid = oldID
                        if oldID == connID:
                            continue
                        # Check if 2 items overlap
                        overlap = self._checkIfOverlap(connItems, oldItems)
                        if overlap:
                            # If 2 items overlap, and have same host for config
                            # Check that vlans and IPs are not overlapping
                            if oldItems.get(hostname, {}):
                                oStats = self._getVlanIPs(oldItems[hostname])
                                self._checkIfVlanOverlap(nStats.get('vlan', ''), oStats.get('vlan', ''))
                                self._checkIfIPOverlap(nStats.get('ipv6-address', ''),
                                                       oStats.get('ipv6-address', ''),
                                                       'ipv6')
                                self._checkIfIPOverlap(nStats.get('ipv4-address', ''),
                                                       oStats.get('ipv4-address', ''),
                                                       'ipv4')

    def checkConflicts(self, cls, newConfig, oldConfig):
        """Check conflicting resources and not allow them"""
        if newConfig == oldConfig:
            return False
        self.checkvsw(cls, newConfig, oldConfig)
        return False

    @staticmethod
    def serviceEnded(indict):
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
