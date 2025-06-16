#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.MainUtilities import externalCommandStdOutErr
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.ipaddr import getInterfaces


class RapidPing(BaseDebugAction):
    """Rapid Ping class. Run ping with specific interval and time."""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "RapidPing"
        super().__init__()

    def main(self):
        """Return arptable for specific vlan"""
        if self.requestdict["interface"] not in getInterfaces():
            self.logMessage("Interface is not available on the node")
            return
        ipaddr = self.requestdict["ip"].split("/")[0]
        command = f"ping -i {self.requestdict.get('interval', 1)} -w {self.requestdict['time']} {ipaddr} -s {self.requestdict['packetsize']} -I {self.requestdict['interface']}"
        self.logMessage(f"Running command: {command}")
        externalCommandStdOutErr(
            command, self.outfiles["stdout"], self.outfiles["stderr"]
        )
        self.jsonout["exitCode"] = 0
