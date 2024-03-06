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
from SiteRMLibs.CustomExceptions import BackgroundException

class RapidPing(BaseDebugAction):
    """RapidPing class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "RapidPing"
        super().__init__()

    def main(self):
        """Main RapidPing work. Run RapidPing on switches."""
        self.jsonout.setdefault('rapid-ping', {'exitCode': -1, 'output': []})
        self.processout.wn(f"NOT IMPLEMENTED call {self.backgConfig} to run rapid ping on switches")
        self.logger.warning(f"NOT IMPLEMENTED call {self.backgConfig} to run rapid ping on switches")
        raise BackgroundException("NOT IMPLEMENTED! -1")
