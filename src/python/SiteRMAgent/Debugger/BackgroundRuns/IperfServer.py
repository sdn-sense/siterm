#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.MainUtilities import externalCommandStdOutErr


class IperfServer(BaseDebugAction):
    """Iperf Server class. Run Iperf server."""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "IperfServer"
        super().__init__()

    def runiperf(self):
        """Run Iperf3 server"""
        self.logMessage(f"Running IperfServer background run. Input requestdict: {self.requestdict}")
        command = f'timeout {self.requestdict["time"]} iperf3 --server -p {self.requestdict["port"]}'
        if "ip" in self.requestdict:
            command += f' --bind {self.requestdict["ip"]}'
        if self.requestdict["onetime"] == "True":
            command += " -1"
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles["stdout"], self.outfiles["stderr"])
        self.jsonout["exitCode"] = 0
        self.logMessage("IperfServer background run finished successfully.")

    def main(self):
        """Run main to launch iperf3 server"""
        if self.requestdict.get("dynamicfrom") and self.requestdict.get("selectedip"):
            self.requestdict["ip"] = self.requestdict["selectedip"].split("/")[0]
        self.runiperf()
