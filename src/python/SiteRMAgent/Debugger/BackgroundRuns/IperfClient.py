#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import getInterfaces, ipVersion
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class IperfClient(BaseDebugAction):
    """Iperf Client class. Run Iperf client"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.service = "IperfClient"
        super().__init__()

    def main(self):
        """Run TCP IPerf"""
        self.jsonout.setdefault('iperf-client', {'exitCode': -1, 'output': []})
        if self.backgConfig["interface"] not in getInterfaces():
            self.processout.wn("Interface is not available on the node")
            return
        if ipVersion(self.backgConfig["ip"]) == -1:
            self.processout.wn(f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6")
            return
        command = f"iperf3 -c {self.backgConfig['ip']} -P {self.backgConfig['port']} -B {self.backgConfig['interface']} -t {self.backgConfig['time']}"
        self.processout.wn(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles['stdout'], self.outfiles['stderr'])
        self.jsonout['iperf-client']['exitCode'] = 0
