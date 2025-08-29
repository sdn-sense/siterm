c#!/usr/bin/env python3
# pylint: disable=too-few-public-methods
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2025/05/30
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.MainUtilities import externalCommandStdOutErr


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
        """Main EthrServer work. Run Ethr Server."""
        self.logMessage(f"Running EthrServer background run. Input requestdict: {self.requestdict}")
        command = f'timeout {self.requestdict["time"]} /opt/ethr -s -p {self.requestdict["port"]}'
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles["stdout"], self.outfiles["stderr"])
        self.jsonout["exitCode"] = 0
        self.logMessage("EthrServer background run finished successfully.")
