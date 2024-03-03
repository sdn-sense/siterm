#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class TCPDump(BaseDebugAction):
    """TCPDump class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.service = "TCPDump"
        super().__init__()

    def main(self):
        """Main TCPDump work. Run TCPDump on switches."""
        self.jsonout.setdefault('tcpdump', [])
        self.processout.wn(f"NOT IMPLEMENTED call {self.backgConfig} to run TCPDump on switches")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to run TCPDump on switches")
        raise Exception("NOT IMPLEMENTED! -1")
