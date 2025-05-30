#!/usr/bin/env python3
# pylint: disable=too-few-public-methods
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2025/05/30
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.CustomExceptions import BackgroundException


class FdtClient(BaseDebugAction):
    """FdtClient class"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "FdtClient"
        super().__init__()

    def main(self):
        """Main FdtClient work. Run FDT client."""
        self.logMessage(f"NOT IMPLEMENTED call {self.backgConfig}. TODO", "warning")
        raise BackgroundException("NOT IMPLEMENTED! -1")
