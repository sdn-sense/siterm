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
from pyroute2 import IPRoute
from DTNRMLibs.MainUtilities import execute
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.ipaddr import normalizedip, normalizedipwithnet

def getBroadCast(inIP):
    """Return broadcast IP."""
    myNet = ipaddress.ip_network(str(inIP), strict=False)
    return str(myNet.broadcast_address)

def intfUp(intf):
    """Check if Interface is up"""
    state = 'DOWN'
    with IPRoute() as ipObj:
        state = ipObj.get_links(ipObj.link_lookup(ifname=intf)[0])[0].get_attr('IFLA_OPERSTATE')
    return state == 'UP'


class VInterfaces():
    """Virtual interface class."""
    def __init__(self, config):
        self.config = config if config else getConfig()
        self.logger = getLoggingObject(config=self.config, service='Ruler')

    def _add(self, vlan, raiseError=False):
        """Add specific vlan."""
        self.logger.info('Called VInterface add L2 for %s' % str(vlan))
        command = "ip link add link %s name vlan.%s type vlan id %s" % (vlan['destport'],
                                                                        vlan['vlan'],
                                                                        vlan['vlan'])
        return execute(command, self.logger, raiseError)

    def _setup(self, vlan, raiseError=False):
        """Setup vlan."""
        if 'ip' in vlan.keys() and vlan['ip']:
            self.logger.info('Called VInterface IPv4 setup L2 for %s' % str(vlan))
            command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ip'],
                                                                   getBroadCast(vlan['ip']),
                                                                   vlan['vlan'])
            execute(command, self.logger, raiseError)
        elif 'ipv6' in vlan.keys() and vlan['ipv6']:
            self.logger.info('Called VInterface IPv6 setup L2 for %s' % str(vlan))
            command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ipv6'],
                                                                   getBroadCast(vlan['ipv6']),
                                                                   vlan['vlan'])
            execute(command, self.logger, raiseError)
        else:
            self.logger.info('Called VInterface setup for %s, but ip/ipv6 keys are not present.' % str(vlan))
            self.logger.info('Continue as nothing happened')

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
        del raiseError
        allInterfaces = netifaces.interfaces()
        if 'vlan.%s' % vlan['vlan'] not in allInterfaces:
            return False
        return True

    @staticmethod
    def _statusvlanIP(vlan, raiseError=False):
        """Check if IP set on vlan"""
        del raiseError
        allIPs = netifaces.ifaddresses('vlan.%s' % vlan['vlan'])
        ip4Exists = False
        if 'ip' in vlan and vlan['ip']:
            serviceIp = vlan['ip'].split('/')[0]
            for ipv4m in allIPs.get(2, {}):
                if serviceIp == ipv4m['addr']:
                    ip4Exists = True
                    break
        else:
            # IPv4 IP was not requested.
            ip4Exists = True
        ip6Exists = False
        if 'ipv6' in vlan and vlan['ipv6']:
            vlan['ipv6'] = normalizedip(vlan['ipv6'])
            for ipv6m in allIPs.get(10, {}):
                if vlan['ipv6'] == normalizedipwithnet(ipv6m.get('addr', ''), ipv6m.get('netmask', '')):
                    ip6Exists = True
        else:
            # IPv6 IP was not requested.
            ip6Exists = True
        return ip4Exists and ip6Exists

    @staticmethod
    def _getvlanlist(inParams):
        """Get All Vlan List"""
        vlans = []
        for key, vals in inParams.items():
            vlan = {}
            vlan['destport'] = key
            vlan['vlan'] = vals.get('hasLabel', {}).get('value', '')
            vlan['ip'] = vals.get('hasNetworkAddress', {}).get('ipv4-address', {}).get('value', '')
            vlan['ipv6'] = vals.get('hasNetworkAddress', {}).get('ipv6-address', {}).get('value', '')
            vlans.append(vlan)
        return vlans

    def activate(self, inParams):
        """Activate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            if self._statusvlan(vlan):
                if not self._statusvlanIP(vlan):
                    self._setup(vlan)
            else:
                self._add(vlan)
                self._setup(vlan)
            if not intfUp("vlan.%s" % vlan['vlan']):
                self._start(vlan)

    def terminate(self, inParams):
        """Terminate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            if self._statusvlan(vlan):
                self._stop(vlan)
                self._remove(vlan)

    def modify(self, oldParams, newParams):
        """Modify Virtual Interface resources"""
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
    testdata = {'enp143s0': {'isAlias': 'urn:ogf:network:ultralight.org:2013:dellos9_s0:hundredGigE_1-23:vlanport+3610', '_params': {'tag': 'urn:ogf:network:service+27cfe535-09e4-4510-bee2-e30331fbc9f5:vt+l2-policy::Connection_1'}, 'hasLabel': {'labeltype': 'ethernet#vlan', 'value': 3610}, 'hasService': {'bwuri': 'urn:ogf:network:ultralight.org:2013:sdn-dtn-1-7.ultralight.org:enp143s0:vlanport+3610:service+bw', 'availableCapacity': 1000000000, 'granularity': 1000000, 'maximumCapacity': 1000000000, 'priority': 0, 'reservableCapacity': 1000000000, 'type': 'guaranteedCapped', 'unit': 'bps'}, 'hasNetworkAddress': {'ipv6-address': {'type': 'ipv6-address|unverifiable', 'value': 'fc00:0:0:0:0:0:0:1c/127'}}}}
    vInt = VInterfaces(None)
    vInt.activate(testdata)
