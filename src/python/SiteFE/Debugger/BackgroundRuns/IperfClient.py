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

class IperfClient(BaseDebugAction):
    """IperfClient class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="IperfClient")
        self.logger.info("====== IperfClient Start Work. Config: %s", self.backgConfig)
        super().__init__()

    def main(self):
        """Main IperfClient work. Run IperfClient on switches."""
        self.jsonout.setdefault('iperf-client', [])
        self.stderr.append(f"NOT IMPLEMENTED call {self.backgConfig} to run iperf client on switches")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to run iperf client on switches")
        raise Exception("NOT IMPLEMENTED! -1")
