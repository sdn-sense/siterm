#!/usr/bin/env python3
"""
ArpInfo Plugin to report arp information to FE
"""

import pprint

from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getArpVals, getLoggingObject


class ArpInfo:
    """ArpInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service="Agent")

    @staticmethod
    def get(**_kwargs):
        """Get lscpu information"""
        out = {}
        out.setdefault("arpinfo", [])
        for item in getArpVals():
            out["arpinfo"].append(item)
        return out


if __name__ == "__main__":
    obj = ArpInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
