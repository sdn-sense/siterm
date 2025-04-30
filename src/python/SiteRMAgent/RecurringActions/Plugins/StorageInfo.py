#!/usr/bin/env python3
"""Plugin which executes df command and prepares output about mounted storages.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import pprint

from SiteRMLibs.MainUtilities import getStorageInfo
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.GitConfig import getGitConfig


class StorageInfo:
    """Storage Info parser"""
    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service="Agent")

    def get(self, **_kwargs):
        """Get storage mount points information."""
        return getStorageInfo()


if __name__ == "__main__":
    obj = StorageInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
