#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.ipaddr import getInterfaces, ipVersion
from SiteRMLibs.MainUtilities import externalCommand
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class IperfClient(BaseDebugAction):
    """Iperf Client class. Run Iperf client"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="IperfClient")
        self.logger.info("====== IperfClient Start Work. Config: %s", self.backgConfig)
        super().__init__()

    def main(self):
        """Run TCP IPerf"""
        # TODO: Use python library (iperf3)
        self.jsonout.setdefault('iperf-client', [])
        if self.backgConfig["interface"] not in getInterfaces():
            self.stderr.append("Interface is not available on the node")
            return
        if ipVersion(self.backgConfig["ip"]) == -1:
            self.stderr.append(f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6")
            return
        command = f"iperf3 -c {self.backgConfig['ip']} -P {self.backgConfig['port']} -B {self.backgConfig['interface']} -t {self.backgConfig['time']}"
        self.stdout.append(f"Running command: {command}")
        cmdEx = externalCommand(command, False)
        cmdOut, cmdErr = cmdEx.communicate()
        self.stdout += cmdOut.decode("utf-8").split('\n')
        self.stderr += cmdErr.decode("utf-8").split('\n')
