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
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
# TODO. Configure also MTU and txqueuelen
import ipaddress
from DTNRMLibs.MainUtilities import execute


def getBroadCast(inIP, logger):
    """ Return broadcast IP """
    logger.info('Getting boardcast IP info')
    my_net = ipaddress.ip_network(unicode(inIP), strict=False)
    logger.info('Broadcast for %s is set to %s' % (inIP, str(my_net.broadcast_address)))
    return str(my_net.broadcast_address)


def identifyL23(addition):
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
            command = "ip link add link %s name %s.%s type vlan id %s" % (vlan['destport'],
                                                                          vlan['destport'],
                                                                          vlan['vlan'],
                                                                          vlan['vlan'])
            return execute(command, self.logger, raiseError)
        return None

    def setup(self, vlan, raiseError=False):
        """ Setup vlan """
        if identifyL23(vlan) == 'L2':
            if 'ip' in vlan.keys():
                self.logger.info('Called VInterface setup L2 for %s' % str(vlan))
                command = "ip addr add %s broadcast %s dev %s.%s" % (vlan['ip'], getBroadCast(vlan['ip'], self.logger),
                                                                     vlan['destport'], vlan['vlan'])
                return execute(command, self.logger, raiseError)
            else:
                self.logger.info('Called VInterface setup for %s, but ip key is not present.' % str(vlan))
                self.logger.info('Continue as nothing happened')
        return None

    def start(self, vlan, raiseError=False):
        """ Start specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface start L2 for %s' % str(vlan))
            command = "ip link set %s.%s up" % (vlan['destport'], vlan['vlan'])
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
            command = "ip link set %s.%s down" % (vlan['destport'], vlan['vlan'])
            return execute(command, self.logger, raiseError)
        return None

    def remove(self, vlan, raiseError=False):
        """ Remove specific vlan """
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface remove for %s' % str(vlan))
            command = "ip link delete %s.%s" % (vlan['destport'], vlan['vlan'])
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
        if identifyL23(vlan) == 'L2':
            self.logger.info('Called VInterface status for %s' % str(vlan))
            command = "ip link show dev %s.%s" % (vlan['destport'], vlan['vlan'])
            return execute(command, self.logger, raiseError)
        else:
            self.logger.info('Called VInterface status L3 for %s' % str(vlan))
            for routel in vlan['routes']:
                if 'routeTo' in routel.keys() and 'nextHop' in routel.keys():
                    if 'value' in routel['routeTo'].keys() and 'value' in routel['nextHop'].keys():
                        command = "ip route get %s" % (routel['routeTo']['value'])
                        execute(command, self.logger, raiseError)
                else:
                    self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                     % routel)
        return None

if __name__ == '__main__':
    print 'This has to be called through main Ruler component. Not supported direct call'
