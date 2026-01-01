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
from SiteRMLibs.MainUtilities import getArpVals


class ArpTable(BaseDebugAction):
    """Arp Table class. Return arp table for specific vlan."""

    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get("requestdict", {})
        self.service = "ArpTable"
        super().__init__()

    def main(self):
        """Main ArpTable work. Get all arp table from host."""
        self.logMessage(f"Running ArpTable background run. Input requestdict: {self.requestdict}")
        interface = self.requestdict.get("interface", None)
        if interface and interface not in getInterfaces():
            self.logMessage("Interface is not available on the node")
            return
        for arpval in getArpVals():
            self.jsonout["output"].append(arpval)
            resline = list(map(lambda x: x[0] + str(x[1]), arpval.items()))
            self.logMessage(" ".join(resline))
        self.jsonout["exitCode"] = 0
        self.logMessage("ArpTable background run finished successfully.")
