#!/usr/bin/env python3
"""Routing interface component. Applys route rules on DTN

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
from DTNRMLibs.MainUtilities import execute
from DTNRMLibs.MainUtilities import getLoggingObject

class Routing():
    """Virtual interface class."""
    def __init__(self, config):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='Ruler')

    def add(self, vlan, raiseError=False):
        """Add specific route."""
        self.logger.info(f'ADD ROUTE. TODO: {vlan} {raiseError}')


    def setup(self, vlan, raiseError=False):
        """Setup specific route."""
        self.logger.info(f'SETUP ROUTE. TODO: {vlan} {raiseError}')

    def start(self, vlan, raiseError=False):
        """Add specific route."""
        self.logger.info(f'START ROUTE. TODO: {vlan} {raiseError}')

    def stop(self, vlan, raiseError=False):
        """Stop specific route."""
        self.logger.info(f'STOP ROUTE. TODO: {vlan} {raiseError}')

    def remove(self, vlan, raiseError=False):
        """Remove specific route."""
        self.logger.info(f'REMOVE ROUTE. TODO: {vlan} {raiseError}')

    def status(self, vlan, raiseError=False):
        """Check status of specific route."""
        self.logger.info(f'STATUS ROUTE. TODO: {vlan} {raiseError}')

    def startRoute(self, vlan, raiseError=False):
        """Start/Add Route on DTN"""
        self.logger.info(f'Called VInterface start L3 for {str(vlan)}')
        for routel in vlan['routes']:
            if 'routeTo' in list(routel.keys()) and 'nextHop' in list(routel.keys()):
                if 'value' in list(routel['routeTo'].keys()) and 'value' in list(routel['nextHop'].keys()):
                    command = "ip route add %s via %s" % (routel['routeTo']['value'],
                                                          routel['nextHop']['value'].split('/')[0])
                    execute(command, self.logger, raiseError)
            else:
                self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                 % routel)

    def removeRoute(self, vlan, raiseError=False):
        """Remove Route from DTN"""
        out = []
        self.logger.info(f'Called VInterface remove L3 for {str(vlan)}')
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
        """Check Status of Route on DTN"""
        self.logger.info(f'Called VInterface status L3 for {str(vlan)}')
        for routel in vlan['routes']:
            if 'routeTo' in list(routel.keys()) and 'nextHop' in list(routel.keys()):
                if 'value' in list(routel['routeTo'].keys()) and 'value' in list(routel['nextHop'].keys()):
                    command = f"ip route get {routel['routeTo']['value']}"
                    execute(command, self.logger, raiseError)
            else:
                self.logger.info('Parsed delta did not had routeTo or nextHop keys in route info. Route details: %s'
                                 % routel)
