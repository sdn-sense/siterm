#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import ipVersion
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.CustomExceptions import BackgroundException

class IperfServer(BaseDebugAction):
    """Iperf Server class. Run Iperf server."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "IperfServer"
        super().__init__()

    def main(self):
        """Run IPerf Server"""
        if ipVersion(self.requestdict['ip']) == -1:
            self.logMessage(f"IP {self.requestdict['ip']} does not appear to be an IPv4 or IPv6")
            return
        command = "timeout %s iperf3 --server -p %s --bind %s %s" % (self.requestdict['time'],
                                                                     self.requestdict['port'],
                                                                     self.requestdict['ip'],
                                                                     '-1' if self.requestdict['onetime'] == 'True' else '')
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles['stdout'], self.outfiles['stderr'])
        self.jsonout['exitCode'] = 0
