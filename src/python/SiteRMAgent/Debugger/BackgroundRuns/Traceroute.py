#!/usr/bin/env python3
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/07/19
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.ipaddr import getInterfaces
from SiteRMLibs.ipaddr import ipVersion


class Traceroute(BaseDebugAction):
    """Traceroute class. Run trace route to specific IP."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "Traceroute"
        super().__init__()

    def main(self):
        """Main TraceRoute work. Run TraceRoute on host."""
        cmd = "traceroute "
        # Add from interface section
        if 'from_interface' in self.requestdict and self.requestdict['from_interface']:
            if self.requestdict['from_interface'] not in getInterfaces():
                self.logMessage(f"Interface {self.requestdict['from_interface']} is not available on the node")
                return
            cmd += f"-i {self.requestdict['from_interface']} "
        # Add from ip section
        if 'from_ip' in self.requestdict and self.requestdict['from_ip']:
            if ipVersion(self.requestdict['from_ip']) == -1:
                self.logMessage(f"IP {self.requestdict['from_ip']} does not appear to be an IPv4 or IPv6")
                return
            cmd += f"-s {self.requestdict['from_ip']} "
        if ipVersion(self.requestdict['ip']) == -1:
            self.logMessage(f"IP {self.requestdict['ip']} does not appear to be an IPv4 or IPv6")
            return
        cmd += f"{self.requestdict['ip']}"
        self.logMessage(f"Running command: {cmd}")
        externalCommandStdOutErr(cmd, self.outfiles['stdout'], self.outfiles['stderr'])
        self.jsonout['exitCode'] = 0
