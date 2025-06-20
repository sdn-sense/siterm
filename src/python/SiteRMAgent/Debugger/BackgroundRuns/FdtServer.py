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
from SiteRMLibs.MainUtilities import externalCommandStdOutErr


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
        """Main FdtServer work. Run FDT Server."""
        command = f'timeout {self.requestdict["time"]} java -jar /opt/fdt.jar -p {self.requestdict["port"]}'
        if self.requestdict["onetime"] == "True":
            command += " -S"
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(
            command, self.outfiles["stdout"], self.outfiles["stderr"]
        )
        self.jsonout["exitCode"] = 0


# -FDT_LISTEN
