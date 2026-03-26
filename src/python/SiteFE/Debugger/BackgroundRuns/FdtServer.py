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


class FdtServer(BaseDebugAction):
    """FdtServer class"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "FdtServer"
        super().__init__()

    def main(self):
        """Main FdtServer work. Run FDT client."""
        self.logMessage(
            f"NOT IMPLEMENTED call {self.backgConfig} to run FDT Server on Switch",
            "warning",
        )
        raise BackgroundException("NOT IMPLEMENTED! -1")
