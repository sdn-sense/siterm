#!/usr/bin/env python3
"""Plugin which executes df command and prepares output about mounted storages.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/01/29
"""
import pprint

from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MemDiskStats import MemDiskStats


class StorageInfo:
    """Storage Info parser"""
    # pylint: disable=too-few-public-methods

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service="Agent")
        self.memDiskStats = MemDiskStats()

    def get(self, **_kwargs):
        """Get storage mount points information."""
        self.memDiskStats.reset()
        self.memDiskStats.updateStorageInfo()
        return self.memDiskStats.getStorageInfo()


if __name__ == "__main__":
    obj = StorageInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
