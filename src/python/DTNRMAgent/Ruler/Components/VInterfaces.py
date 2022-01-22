#!/usr/bin/env python3
"""Virtual interfaces component, which creates or tierdowns virtual interface.
This is called from a Ruler component.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/20
"""
# TODO. Configure also MTU and txqueuelen
import ipaddress
import netifaces
from DTNRMLibs.MainUtilities import execute

def getBroadCast(inIP):
    """Return broadcast IP."""
    myNet = ipaddress.ip_network(str(inIP), strict=False)
    return str(myNet.broadcast_address)

class VInterfaces():
    """Virtual interface class."""
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def _add(self, vlan, raiseError=False):
        """Add specific vlan."""
        self.logger.info('Called VInterface add L2 for %s' % str(vlan))
        command = "ip link add link %s name vlan.%s type vlan id %s" % (vlan['destport'],
                                                                        vlan['vlan'],
                                                                        vlan['vlan'])
        return execute(command, self.logger, raiseError)

    def _setup(self, vlan, raiseError=False):
        """Setup vlan."""
        if 'ip' in vlan.keys():
            self.logger.info('Called VInterface setup L2 for %s' % str(vlan))
            command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ip'],
                                                                   getBroadCast(vlan['ip']),
                                                                   vlan['vlan'])
            return execute(command, self.logger, raiseError)
        self.logger.info('Called VInterface setup for %s, but ip key is not present.' % str(vlan))
        self.logger.info('Continue as nothing happened')
        return None

    def _start(self, vlan, raiseError=False):
        """Start specific vlan."""
        self.logger.info('Called VInterface start L2 for %s' % str(vlan))
        command = "ip link set dev vlan.%s up" % (vlan['vlan'])
        return execute(command, self.logger, raiseError)

    def _stop(self, vlan, raiseError=False):
        """Stop specific vlan."""
        out = []
        self.logger.info('Called VInterface L2 stop for %s' % str(vlan))
        for command in ["ip link set dev vlan.%s down" % (vlan['vlan']),
                        "ip link set dev vlan.%s-ifb down" % (vlan['vlan'])]:
            out.append(execute(command, self.logger, raiseError))
        return out

    def _remove(self, vlan, raiseError=False):
        """Remove specific vlan."""
        out = []
        self.logger.info('Called VInterface remove for %s' % str(vlan))
        for command in ["ip link delete dev vlan.%s" % (vlan['vlan']),
                        "ip link delete dev vlan.%s-ifb" % (vlan['vlan'])]:
            out.append(execute(command, self.logger, raiseError))
        return out

    @staticmethod
    def _statusvlan(vlan, raiseError=False):
        """Get status of specific vlan."""
        allInterfaces = netifaces.interfaces()
        if 'vlan.%s' % vlan['vlan'] not in allInterfaces:
            return False
        return True

    @staticmethod
    def _statusvlanIP(vlan, raiseError=False):
        allIPs = netifaces.ifaddresses('vlan.%s' % vlan['vlan'])
        serviceIp = vlan['ip'].split('/')[0]
        for ipv4m in allIPs.get(2, {}):
            if serviceIp == ipv4m['addr']:
                return True
        return False

    @staticmethod
    def _getvlanlist(inParams):
        vlans = []
        for key, vals in inParams.items():
            vlan = {}
            vlan['destport'] = key
            vlan['vlan'] = vals.get('hasLabel', {}).get('value', '')
            # TODO: Allow IPv6 assignment? TODO
            vlan['ip'] = vals.get('hasNetworkAddress', {}).get('value', '')
            vlans.append(vlan)
        return vlans

    def activate(self, inParams):
        """ Activate Virtual Interface resources """
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            if self._statusvlan(vlan):
                if 'ip' in vlan and vlan['ip']:
                    if self._statusvlanIP(vlan):
                        continue
                    self._setup(vlan)
            else:
                self._add(vlan)
                self._setup(vlan)
            # TODO: Check if it is up?
            self._start(vlan)

    def terminate(self, inParams):
        """ Terminate Virtual Interface resources """
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            if self._statusvlan(vlan):
                self._stop(vlan)
                self._remove(vlan)

    def modify(self, oldParams, newParams):
        """ Modify Virtual Interface resources """
        old = self._getvlanlist(oldParams)
        new = self._getvlanlist(newParams)
        if old == new:
            # This can happen if we modify QOS only. So there is no IP or VLAN
            # change.
            return
        # TODO: check if vlan same, if not - tier down old one, set up new one
        # check if IPs ==, if not - set new IPs.
        print('Called modify. TODO')

if __name__ == '__main__':
    print('This has to be called through main Ruler component. Not supported direct call')
