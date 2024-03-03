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

class ArpTable(BaseDebugAction):
    """ArpTable class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.service = "ArpTable"
        super().__init__()

    def main(self):
        """Main ArpTable work. Get all arp table from switches."""
        self.jsonout.setdefault('arp-table', {'exitCode': -1, 'output': []})
        self.processout.wn(f"NOT IMPLEMENTED call {self.backgConfig} to get arp table")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to get arp table")
        raise Exception("NOT IMPLEMENTED! -1")
