#!/usr/bin/env python3
"""Virtual interfaces component, which creates or tierdowns virtual interface.
This is called from a Ruler component.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/20
"""
# TODO. Configure also MTU and txqueuelen
from pyroute2 import IPRoute
from SiteRMLibs.MainUtilities import execute
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import publishToSiteFE
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.CustomExceptions import FailedInterfaceCommand
from SiteRMLibs.ipaddr import getBroadCast
from SiteRMLibs.ipaddr import normalizedip
from SiteRMLibs.ipaddr import getInterfaces
from SiteRMLibs.ipaddr import getInterfaceIP
from SiteRMLibs.ipaddr import normalizedipwithnet


def publishState(vlan, inParams, uuid, hostname, state, fullURL):
    """Publish Agent apply state to Frontend."""
    oldState = inParams.get(vlan['destport'], {}).get('_params', {}).get('networkstatus', 'unknown')
    if state != oldState:
        out = {'uuidtype': 'vsw',
               'uuid': uuid,
               'hostname': hostname,
               'hostport': vlan['destport'],
               'uuidstate': state}
        publishToSiteFE(out, fullURL, "/sitefe/v1/deltatimestates", 'POST')


def getDefaultMTU(config, intfKey):
    """Get Default MTU"""
    if config.has_section(intfKey):
        if config.has_option(intfKey, 'defaultMTU'):
            return int(config.get(intfKey, 'defaultMTU'))
    elif config.has_section('agent'):
        if config.has_option('agent', 'defaultMTU'):
            return int(config.get('agent', 'defaultMTU'))
    return 1500


def getDefaultTXQ(config, intfKey):
    """Get Default Txqueuelen"""
    if config.has_section(intfKey):
        if config.has_option(intfKey, 'defaultTXQueuelen'):
            return int(config.get(intfKey, 'defaultTXQueuelen'))
    elif config.has_section('agent'):
        if config.has_option('agent', 'defaultTXQueuelen'):
            return int(config.get('agent', 'defaultTXQueuelen'))
    return 1000


def intfUp(intf):
    """Check if Interface is up"""
    state = 'DOWN'
    with IPRoute() as ipObj:
        state = ipObj.get_links(ipObj.link_lookup(ifname=intf)[0])[0].get_attr('IFLA_OPERSTATE')
    return state == 'UP'


class VInterfaces():
    """Virtual interface class."""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.hostname = self.config.get('agent', 'hostname')
        self.fullURL = getFullUrl(self.config, sitename)
        self.logger = getLoggingObject(config=self.config, service='Ruler')

    def _add(self, vlan, raiseError=False):
        """Add specific vlan."""
        self.logger.info(f'Called VInterface add L2 for {str(vlan)}')
        command = "ip link add link %s name vlan.%s type vlan id %s" % (vlan['destport'],
                                                                        vlan['vlan'],
                                                                        vlan['vlan'])
        return execute(command, self.logger, raiseError)

    def _setup(self, vlan, raiseError=False):
        """Setup vlan."""
        if 'ip' in vlan.keys() and vlan['ip']:
            self.logger.info(f'Called VInterface IPv4 setup L2 for {str(vlan)}')
            command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ip'],
                                                                   getBroadCast(vlan['ip']),
                                                                   vlan['vlan'])
            execute(command, self.logger, raiseError)
        elif 'ipv6' in vlan.keys() and vlan['ipv6']:
            self.logger.info(f'Called VInterface IPv6 setup L2 for {str(vlan)}')
            command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ipv6'],
                                                                   getBroadCast(vlan['ipv6']),
                                                                   vlan['vlan'])
            execute(command, self.logger, raiseError)
        else:
            self.logger.info(f'Called VInterface setup for {str(vlan)}, but ip/ipv6 keys are not present.')
            self.logger.info('Continue as nothing happened')

    def _removeIP(self, vlan, raiseError=False):
        """Remove IP from vlan"""
        if 'ip' in vlan.keys() and vlan['ip']:
            self.logger.info(f'Called VInterface IPv4 remove IP for {str(vlan)}')
            command = f"ip addr del {vlan['ip']} broadcast {getBroadCast(vlan['ip'])} dev vlan.{vlan['vlan']}"
            execute(command, self.logger, raiseError)
        elif 'ipv6' in vlan.keys() and vlan['ipv6']:
            self.logger.info(f'Called VInterface IPv6 remote IP for {str(vlan)}')
            command = f"ip addr del {vlan['ipv6']} broadcast {getBroadCast(vlan['ipv6'])} dev vlan.{vlan['vlan']}"
            execute(command, self.logger, raiseError)
        else:
            self.logger.info(f'Called VInterface remove ip for {str(vlan)}, but ip/ipv6 keys are not present.')
            self.logger.info('Continue as nothing happened')

    def _start(self, vlan, raiseError=False):
        """Start specific vlan."""
        self.logger.info(f'Called VInterface start L2 for {str(vlan)}')
        command = f"ip link set dev vlan.{vlan['vlan']} up"
        return execute(command, self.logger, raiseError)

    def _stop(self, vlan, raiseError=False):
        """Stop specific vlan."""
        out = []
        self.logger.info(f'Called VInterface L2 stop for {str(vlan)}')
        for command in [f"ip link set dev vlan.{vlan['vlan']} down"]:
            out.append(execute(command, self.logger, raiseError))
        return out

    def _remove(self, vlan, raiseError=False):
        """Remove specific vlan."""
        out = []
        self.logger.info(f'Called VInterface remove for {str(vlan)}')
        for command in [f"ip link delete dev vlan.{vlan['vlan']}"]:
            out.append(execute(command, self.logger, raiseError))
        return out

    @staticmethod
    def _statusvlan(vlan, raiseError=False):
        """Get status of specific vlan."""
        del raiseError
        if f"vlan.{vlan['vlan']}" not in getInterfaces():
            return False
        return True

    @staticmethod
    def _statusvlanIP(vlan, raiseError=False):
        """Check if IP set on vlan"""
        del raiseError
        allIPs = getInterfaceIP(f"vlan.{vlan['vlan']}")
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

    def _getvlanlist(self, inParams):
        """Get All Vlan List"""
        vlans = []
        for key, vals in inParams.items():
            netInfo = vals.get('hasNetworkAddress', {})
            vlan = {'destport': key,
                    'vlan': vals.get('hasLabel', {}).get('value', ''),
                    'ip': netInfo.get('ipv4-address', {}).get('value', ''),
                    'ipv6': netInfo.get('ipv6-address', {}).get('value', ''),
                    'mtu': netInfo.get('mtu', {}).get('value', getDefaultMTU(self.config, key)),
                    'txqueuelen': netInfo.get('txqueuelen', {}).get('value', getDefaultTXQ(self.config, key))}
            vlans.append(vlan)
        return vlans

    def activate(self, inParams, uuid):
        """Activate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            try:
                if self._statusvlan(vlan, True):
                    if not self._statusvlanIP(vlan, True):
                        self._setup(vlan, True)
                else:
                    self._add(vlan, True)
                    self._setup(vlan, True)
                if not intfUp(f"vlan.{vlan['vlan']}"):
                    self._start(vlan, True)
                publishState(vlan, inParams, uuid, self.hostname, 'activated', self.fullURL)
            except FailedInterfaceCommand:
                publishState(vlan, inParams, uuid, self.hostname, 'activate-error', self.fullURL)
        return vlans

    def terminate(self, inParams, uuid):
        """Terminate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            try:
                if self._statusvlan(vlan, False):
                    self._stop(vlan, False)
                    self._remove(vlan, False)
                publishState(vlan, inParams, uuid, self.hostname, 'deactivated', self.fullURL)
            except FailedInterfaceCommand:
                publishState(vlan, inParams, uuid, self.hostname, 'deactivate-error', self.fullURL)
        return vlans

    def modify(self, oldParams, newParams, uuid):
        """Modify Virtual Interface resources"""
        old = self._getvlanlist(oldParams)
        new = self._getvlanlist(newParams)
        if old == new:
            # This can happen if we modify QOS only. So there is no IP or VLAN
            # change.
            return []
        # TODO: check if vlan same, if not - tier down old one, set up new one
        # check if IPs ==, if not - set new IPs.
        print('Called modify. TODO')
        return []
