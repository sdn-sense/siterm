#!/usr/bin/env python3
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


class IperfServer():
    """Iperf Server class. Run Iperf server."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="IperfServer")
        self.logger.info("====== IperfServer Start Work. Config: %s", self.backgConfig)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def startwork(self):
        """Run IPerf Server"""
        # TODO: Use python library (iperf3 pip)
        if ipVersion(self.backgConfig['ip']) == -1:
            return [], f"IP {self.backgConfig['ip']} does not appear to be an IPv4 or IPv6", 4
        command = "timeout %s iperf3 --server -p %s --bind %s %s" % (self.backgConfig['time'],
                                                                     self.backgConfig['port'],
                                                                     self.backgConfig['ip'],
                                                                     '-1' if self.backgConfig['onetime'] == 'True' else '')
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        return out.decode("utf-8"), err.decode("utf-8"), cmdOut.returncode
