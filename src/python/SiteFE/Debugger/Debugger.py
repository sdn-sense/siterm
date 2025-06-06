#!/usr/bin/env python3
"""Debugger component pulls all actions from Site-FE and do tests

   Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2021 California Institute of Technology
Date                    : 2021/03/12
"""
import os
import sys
import argparse
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getDBConn, getVal
from SiteRMLibs.MainUtilities import getFileContentAsJson
from SiteRMLibs.DebugService import DebugService
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.Backends.main import Switch

COMPONENT = "Debugger"


class Debugger(DebugService):
    """Debugger main process"""

    def __init__(self, config, sitename):
        super(Debugger, self).__init__(config, sitename)
        self.config = config if config else getGitConfig()
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="Debugger")
        self.switch = Switch(self.config, self.sitename)
        self.switches = {}
        self.diragent = contentDB()
        self.dbI = getVal(
            getDBConn("DebuggerService", self), **{"sitename": self.sitename}
        )
        self.logger.info("====== Debugger Start Work. Sitename: %s", self.sitename)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def getData(self, hostname, state):
        """Get data from DB."""
        search = [["hostname", hostname], ["state", state]]
        return self.dbI.get(
            "debugrequests", orderby=["updatedate", "DESC"], search=search, limit=50
        )

    def getFullData(self, hostname, item):
        """Get full data from DB."""
        debugdir = os.path.join(
            self.config.get(self.sitename, "privatedir"), "DebugRequests"
        )
        # Get Request JSON
        requestfname = os.path.join(debugdir, hostname, str(item["id"]), "request.json")
        item["requestdict"] = getFileContentAsJson(requestfname)
        return item

    def startwork(self):
        """Start execution and get new requests from FE"""
        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()
        for host in self.switches:
            for wtype in ["new", "active"]:
                self.logger.info(f"Get all {wtype} requests")
                data = self.getData(host, wtype)
                for item in data:
                    if not self.backgroundProcessItemExists(item):
                        self.logger.info(
                            f"Background process item does not exist. ID: {item['id']}"
                        )
                        item = self.getFullData(host, item)
                    self.checkBackgroundProcess(item)


def execute(config=None, sitename=None):
    """Execute main script for Debugger execution."""
    debugger = Debugger(config, sitename)
    debugger.startwork()


def get_parser():
    """Returns the argparse parser."""
    # pylint: disable=line-too-long
    oparser = argparse.ArgumentParser(
        description="This daemon is used for delta reduction, addition parsing",
        prog=os.path.basename(sys.argv[0]),
        add_help=True,
    )
    oparser.add_argument(
        "--sitename",
        dest="sitename",
        default="",
        required=True,
        help="Sitename. Must be present in configuration and database.",
    )

    return oparser


if __name__ == "__main__":
    argparser = get_parser()
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    if len(sys.argv) == 1:
        argparser.print_help()
    inargs = argparser.parse_args(sys.argv[1:])
    getLoggingObject(logType="StreamLogger", service="Debugger")
    execute(sitename=inargs.sitename)
