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


class IperfServer(BaseDebugAction):
    """Iperf Server class. Run Iperf server."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.service = "IperfServer"
        super().__init__()

    def main(self):
        """Run IPerf Server"""
        self.jsonout.setdefault('iperf-server', {'exitCode': -1, 'output': []})
        if ipVersion(self.backgConfig['ip']) == -1:
            self.processout.wn(f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6")
            return
        command = "timeout %s iperf3 --server -p %s --bind %s %s" % (self.backgConfig['time'],
                                                                     self.backgConfig['port'],
                                                                     self.backgConfig['ip'],
                                                                     '-1' if self.backgConfig['onetime'] == 'True' else '')
        self.processout.wn(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles['stdout'], self.outfiles['stderr'])
        self.jsonout['iperf-server']['exitCode'] = 0
