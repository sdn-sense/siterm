#!/usr/bin/env python3
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.MainUtilities import externalCommand
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.ipaddr import getInterfaces

class ArpTable():
    """Arp Table class. Return arp table for specific vlan."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="ArpTable")
        self.logger.info("====== ArpTable Start Work. Config: %s", self.backgConfig)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        return

    def startwork(self):
        """"""
        if self.backgConfig['interface'] not in getInterfaces():
            return [], "Interface is not available on the node", 3
        command = "ip neigh"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        retOut = []
        for line in out.decode("utf-8").split('\n'):
            splLine = line.split(' ')
            if len(splLine) > 4 and splLine[2] == self.backgConfig['interface']:
                retOut.append(line)
        return retOut, err.decode("utf-8"), cmdOut.returncode
