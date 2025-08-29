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
from SiteRMLibs.ipaddr import getInterfaces
from SiteRMLibs.MainUtilities import externalCommandStdOutErr


class IperfClient(BaseDebugAction):
    """Iperf Client class. Run Iperf client"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "IperfClient"
        super().__init__()

    def runiperfclient(self):
        """Run TCP IPerf"""
        self.logMessage(f"Running IperfClient background run. Input requestdict: {self.requestdict}")
        command = f"iperf3 -c {self.requestdict['ip'].split('/')[0]} -p {self.requestdict['port']}"
        command += f" -t {self.requestdict['time']}"
        command += f" -P {self.requestdict['streams']}"
        if self.requestdict.get("interface"):
            if self.requestdict["interface"] not in getInterfaces():
                self.logMessage(f"Interface {self.requestdict['interface']} is not available on the node.")
                return
            command += f" -B {self.requestdict['interface']}"
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles["stdout"], self.outfiles["stderr"])
        self.jsonout["exitCode"] = 0
        self.logMessage("IperfClient background run finished successfully.")

    def main(self):
        """Run main to launch iperf3 client"""
        self.runiperfclient()
