#!/usr/bin/env python3
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


class IperfClient():
    """Iperf Client class. Run Iperf client"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="IperfClient")
        self.logger.info("====== IperfClient Start Work. Config: %s", self.backgConfig)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def startwork(self):
        """Run TCP IPerf"""
        if self.backgConfig["interface"] not in getInterfaces():
            return [], "Interface is not available on the node", 3
        if ipVersion(self.backgConfig["ip"]) == -1:
            return [], f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6", 4

        command = f"iperf3 -c {self.backgConfig['ip']} -P {self.backgConfig['port']} -B {self.backgConfig['interface']} -t {self.backgConfig['time']}"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        return out.decode("utf-8"), err.decode("utf-8"), cmdOut.returncode
