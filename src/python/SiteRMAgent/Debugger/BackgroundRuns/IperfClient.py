#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import getInterfaces
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.BaseDebugAction import BaseDebugAction


class IperfClient(BaseDebugAction):
    """Iperf Client class. Run Iperf client"""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "IperfClient"
        super().__init__()

    def main(self):
        """Run TCP IPerf"""
        if self.requestdict["interface"] not in getInterfaces():
            self.logMessage("Interface is not available on the node")
            return
        command = f"iperf3 -c {self.requestdict['ip']} -p {self.requestdict['port']}"
        command += f" -t {self.requestdict['time']}"
        command += f" -P {self.requestdict['streams']}"
        if self.requestdict.get('interface'):
            if self.requestdict["interface"] not in getInterfaces():
                self.logMessage(f"Interface {self.requestdict['interface']} is not available on the node.")
                return
            command += f" -B {self.requestdict['interface']}"

        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(command, self.outfiles["stdout"], self.outfiles["stderr"])
        self.jsonout["exitCode"] = 0