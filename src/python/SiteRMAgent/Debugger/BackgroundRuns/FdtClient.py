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
        self.logMessage(f"Running FdtClient background run. Input requestdict: {self.requestdict}")
        command = f'timeout {self.requestdict["time"]} java -jar /opt/fdt.jar -p {self.requestdict["port"]}'
        command += f' -c {self.requestdict["ip"].split("/")[0]}'
        command += f' -P {self.requestdict["streams"]}'
        command += " -nettest"
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(
            command, self.outfiles["stdout"], self.outfiles["stderr"]
        )
        self.jsonout["exitCode"] = 0
        self.logMessage("FdtClient background run finished successfully.")
