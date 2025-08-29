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


class EthrClient(BaseDebugAction):
    """EthrClient class"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "EthrClient"
        super().__init__()

    def main(self):
        """Main EthrClient work. Run Ethr client."""
        self.logMessage(f"Running EthrClient background run. Input requestdict: {self.requestdict}")
        command = f'timeout {int(self.requestdict["time"])+5} /opt/ethr'
        command += f' -c {self.requestdict["ip"].split("/")[0]}'
        command += f' -n {self.requestdict["streams"]} -d {self.requestdict["time"]}s'
        command += f' -port {self.requestdict["port"]}'
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles["stdout"], self.outfiles["stderr"])
        self.jsonout["exitCode"] = 0
        self.logMessage("EthrClient background run finished successfully.")
