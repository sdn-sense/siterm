#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import ipVersion
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.ipaddr import getInterfaces

class RapidPing(BaseDebugAction):
    """Rapid Ping class. Run ping with specific interval and time."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "RapidPing"
        super().__init__()

    def main(self):
        """Return arptable for specific vlan"""
        self.jsonout.setdefault('rapid-ping', {'exitCode': -1, 'output': []})
        if self.requestdict['interface'] not in getInterfaces():
            self.processout.wn("Interface is not available on the node")
            return
        if ipVersion(self.requestdict['ip']) == -1:
            self.processout.wn(f"IP {self.requestdict['ip']} does not appear to be an IPv4 or IPv6")
            return

        command = f"ping -i {self.requestdict.get('interval', 1)} -w {self.requestdict['time']} {self.requestdict['ip']} -s {self.requestdict['packetsize']} -I {self.requestdict['interface']}"
        self.processout.wn(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles['stdout'], self.outfiles['stderr'])
        self.jsonout['rapid-ping']['exitCode'] = 0
