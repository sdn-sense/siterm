#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import ipVersion
from SiteRMLibs.MainUtilities import externalCommand
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.ipaddr import getInterfaces


class RapidPing(BaseDebugAction):
    """Rapid Ping class. Run ping with specific interval and time."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="RapidPing")
        self.logger.info("====== RapidPing Start Work. Config: %s", self.backgConfig)
        super().__init__()

    def main(self):
        """Return arptable for specific vlan"""
        self.jsonout.setdefault('rapid-ping', [])
        if self.backgConfig['interface'] not in getInterfaces():
            self.stderr.append("Interface is not available on the node")
            return
        if ipVersion(self.backgConfig['ip']) == -1:
            self.stderr.append(f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6")
            return

        command = f"ping -i {self.backgConfig.get('interval', 1)} -w {self.backgConfig['time']} {self.backgConfig['ip']} -s {self.backgConfig['packetsize']} -I {self.backgConfig['interface']}"
        cmdEx = externalCommand(command, False)
        cmdOut, cmdErr = cmdEx.communicate()
        self.stdout += cmdOut.decode("utf-8").split('\n')
        self.stderr += cmdErr.decode("utf-8").split('\n')
