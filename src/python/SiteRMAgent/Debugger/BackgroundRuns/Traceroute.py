#!/usr/bin/env python3
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class Traceroute(BaseDebugAction):
    """Traceroute class. Run trace route to specific IP."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="TraceRoute")
        self.logger.info("====== Traceroute Start Work. Config: %s", self.backgConfig)
        super().__init__()

    def main(self):
        """Main TraceRoute work. Run TraceRoute on host."""
        self.jsonout.setdefault('traceroute', [])
        self.stderr.append(f"NOT IMPLEMENTED call {self.backgConfig} to refresh thread")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to refresh thread")
        raise Exception("NOT IMPLEMENTED! -1")
