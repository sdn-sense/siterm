#!/usr/bin/env python3
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.MainUtilities import getLoggingObject

''
class ArpTable():
    """ArpTable class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="ArpTable")
        self.logger.info("====== ArpTable Start Work. Config: %s", self.backgConfig)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def startwork(self):
        """Main ArpTable work. Get all arp table from switches."""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to get arp table")
        raise Exception("NOT IMPLEMENTED! -1")
