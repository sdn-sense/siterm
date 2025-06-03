#!/usr/bin/env python3
"""
ArpInfo Plugin to report arp information to FE
"""
import pprint

from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getArpVals
from SiteRMLibs.GitConfig import getGitConfig


class ArpInfo:
    """ArpInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = (
            logger if logger else getLoggingObject(config=self.config, service="Agent")
        )

    def get(self, **_kwargs):
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
