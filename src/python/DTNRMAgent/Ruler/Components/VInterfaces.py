#!/usr/bin/env python
"""
    Virtual interfaces component, which creates or tierdowns virtual interface.
    This is called from a Ruler component.

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
Title             : dtnrm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2016 California Institute of Technology
Date            : 2017/09/26
"""
# TODO. Configure also MTU and txqueuelen
import ipaddress
import netifaces
from DTNRMLibs.MainUtilities import execute
from DTNRMLibs.CustomExceptions import FailedInterfaceCommand

def getBroadCast(inIP):
    """ Return broadcast IP """
    myNet = ipaddress.ip_network(unicode(inIP), strict=False)
    return str(myNet.broadcast_address)


def identifyL23(addition):
    """ Check if it is L2 or L3 delta request """
    return 'L3' if 'routes' in addition.keys() else 'L2'



class VInterfaces(object):
    """ Virtual interface class """
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def add(self, vlan, raiseError=False):
        """ Add specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface add L2 for %s' % str(vlan))
            command = "ip link add link %s name vlan.%s type vlan id %s" % (vlan['destport'],
                                                                            vlan['vlan'],
                                                                            vlan['vlan'])
            return execute(command, self.logger, raiseError)
        return None

    def setup(self, vlan, raiseError=False):
        """ Setup vlan """
        if identifyL23(vlan) == 'L2':
            if 'ip' in vlan.keys():
                self.logger.info('Called VInterface setup L2 for %s' % str(vlan))
                command = "ip addr add %s broadcast %s dev vlan.%s" % (vlan['ip'],
                                                                       getBroadCast(vlan['ip']),
                                                                       vlan['vlan'])
                return execute(command, self.logger, raiseError)
            else:
                self.logger.info('Called VInterface setup for %s, but ip key is not present.' % str(vlan))
                self.logger.info('Continue as nothing happened')
        return None

    def start(self, vlan, raiseError=False):
        """ Start specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface start L2 for %s' % str(vlan))
            command = "ip link set vlan.%s up" % (vlan['vlan'])
            return execute(command, self.logger, raiseError)
        else:
            self.logger.info('Called VInterface start L3 for %s' % str(vlan))
            for routel in vlan['routes']:
                if 'routeTo' in routel.keys() and 'nextHop' in routel.keys():
                    if 'value' in routel['routeTo'].keys() and 'value' in routel['nextHop'].keys():
                        command = "ip route add %s via %s" % (routel['routeTo']['value'],
                                                              routel['nextHop']['value'].split('/')[0])
                        execute(command, self.logger, raiseError)
                else:
                    self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                     % routel)
        return None

    def stop(self, vlan, raiseError=False):
        """ Stop specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface L2 stop for %s' % str(vlan))
            command = "ip link set vlan.%s down" % (vlan['vlan'])
            return execute(command, self.logger, raiseError)
        return None

    def remove(self, vlan, raiseError=False):
        """ Remove specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface remove for %s' % str(vlan))
            command = "ip link delete vlan.%s" % (vlan['vlan'])
            return execute(command, self.logger, raiseError)
        else:
            self.logger.info('Called VInterface remove L3 for %s' % str(vlan))
            for routel in vlan['routes']:
                if 'routeTo' in routel.keys() and 'nextHop' in routel.keys():
                    if 'value' in routel['routeTo'].keys() and 'value' in routel['nextHop'].keys():
                        command = "ip route del %s via %s" % (routel['routeTo']['value'],
                                                              routel['nextHop']['value'].split('/')[0])
                        execute(command, self.logger, raiseError)
                else:
                    self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                     % routel)
        return None

    def status(self, vlan, raiseError=False):
        """ Get status of specific vlan """
        out = None
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface status for %s' % str(vlan))
            command = "ip link show dev vlan.%s" % (vlan['vlan'])
            out = execute(command, self.logger, raiseError)
            self.checkInterfacePresense(vlan, raiseError)
        else:
            self.logger.info('Called VInterface status L3 for %s' % str(vlan))
            for routel in vlan['routes']:
                if 'routeTo' in routel.keys() and 'nextHop' in routel.keys():
                    if 'value' in routel['routeTo'].keys() and 'value' in routel['nextHop'].keys():
                        command = "ip route get %s" % (routel['routeTo']['value'])
                        out = execute(command, self.logger, raiseError)
                else:
                    self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                     % routel)
        return out

    def checkInterfacePresense(self, vlan, raiseError=False):
        error = None
        allInterfaces = netifaces.interfaces()
        if 'vlan.%s' % vlan['vlan'] not in allInterfaces:
            self.logger.debug('Previously called debug FAILED. Retry: %s' % str(vlan))
            error = "Interface is not present for %s" % vlan
        else:
            allIPs = netifaces.ifaddresses('vlan.%s' % vlan['vlan'])
            if 2 not in allIPs.keys():
                error = "IPv4 address metrics are not available"
            else:
                ipPresent = False
                serviceIp = vlan['ip'].split('/')[0]
                for ipv4m in allIPs[2]:
                    if serviceIp == ipv4m['addr']:
                        ipPresent = True
                if not ipPresent:
                    error = 'IP Is not Set. Trying to reinitiate.'
        if raiseError and error:
            raise FailedInterfaceCommand(error)


if __name__ == '__main__':
    print 'This has to be called through main Ruler component. Not supported direct call'
