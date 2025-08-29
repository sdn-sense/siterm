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


class EthrServer(BaseDebugAction):
    """EthrServer class"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "EthrServer"
        super().__init__()

    def main(self):
        """Main EthrServer work. Run Ethr server."""
        self.logMessage(
            f"NOT IMPLEMENTED call {self.backgConfig} to run Ethr Server on Switch",
            "warning",
        )
        raise BackgroundException("NOT IMPLEMENTED! -1")
