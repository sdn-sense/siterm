#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class IperfServer(BaseDebugAction):
    """IperfServer class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.service = "IperfServer"
        super().__init__()

    def startwork(self):
        """Main IperfServer work. Run IperfServer on switches."""
        self.jsonout.setdefault('iperf-server', [])
        self.processout.wn(f"NOT IMPLEMENTED call {self.backgConfig} to run iperf server on switches")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to run iperf server on switches")
        raise Exception("NOT IMPLEMENTED! -1")
