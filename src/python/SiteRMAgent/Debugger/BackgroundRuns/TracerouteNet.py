#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/07/17

This is only a placeholder for import and is not used by Agents (only by network/fe)
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.CustomExceptions import BackgroundException

class TracerouteNet(BaseDebugAction):
    """Traceroute class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "TracerouteNet"
        super().__init__()

    def main(self):
        """Main Traceroute work. Run Traceroute on switches."""
        self.jsonout.setdefault('traceroutenet', {'exitCode': -1, 'output': []})
        self.logMessage(f"NOT IMPLEMENTED call {self.backgConfig} to run traceroute on switches")
        raise BackgroundException("NOT IMPLEMENTED! -1")
