#!/usr/bin/env python3
"""Routing interface component. Applys route rules on DTN

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
from DTNRMLibs.MainUtilities import execute

class Routing():
    """Virtual interface class."""
    def __init__(self, config, logger):
        self.config = config
        self.logger = logger

    def add(self, vlan, raiseError=False):
        """Add specific route."""
        return

    def setup(self, vlan, raiseError=False):
        """Setup specific route."""
        return

    def start(self, vlan, raiseError=False):
        """Add specific route."""
        return

    def stop(self, vlan, raiseError=False):
        """Stop specific route."""
        return

    def remove(self, vlan, raiseError=False):
        """Remove specific route."""
        return

    def status(self, vlan, raiseError=False):
        """Check status of specific route."""
        return



    def startRoute(self, vlan, raiseError=False):
        self.logger.info('Called VInterface start L3 for %s' % str(vlan))
        for routel in vlan['routes']:
            if 'routeTo' in list(routel.keys()) and 'nextHop' in list(routel.keys()):
                if 'value' in list(routel['routeTo'].keys()) and 'value' in list(routel['nextHop'].keys()):
                    command = "ip route add %s via %s" % (routel['routeTo']['value'],
                                                          routel['nextHop']['value'].split('/')[0])
                    execute(command, self.logger, raiseError)
            else:
                self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                 % routel)
        return None

    def removeRoute(self, vlan, raiseError=False):
        out = []
        self.logger.info('Called VInterface remove L3 for %s' % str(vlan))
        for routel in vlan['routes']:
            if 'routeTo' in list(routel.keys()) and 'nextHop' in list(routel.keys()):
                if 'value' in list(routel['routeTo'].keys()) and 'value' in list(routel['nextHop'].keys()):
                    command = "ip route del %s via %s" % (routel['routeTo']['value'],
                                                          routel['nextHop']['value'].split('/')[0])
                    out.append(execute(command, self.logger, raiseError))
            else:
                self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                 % routel)

    def statusRoute(self, vlan, raiseError=False):
        out = []
        self.logger.info('Called VInterface status L3 for %s' % str(vlan))
        for routel in vlan['routes']:
            if 'routeTo' in list(routel.keys()) and 'nextHop' in list(routel.keys()):
                if 'value' in list(routel['routeTo'].keys()) and 'value' in list(routel['nextHop'].keys()):
                    command = "ip route get %s" % (routel['routeTo']['value'])
                    out = execute(command, self.logger, raiseError)
            else:
                self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                 % routel)
