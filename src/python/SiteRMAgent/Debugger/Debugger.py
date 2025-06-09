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
import socket
import subprocess
import ipaddress
import argparse
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import publishToSiteFE
from SiteRMLibs.DebugService import DebugService
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.CustomExceptions import FailedGetDataFromFE, PluginException

COMPONENT = "Debugger"


def getAllIps():
    """Get all visible IPs of this host."""
    result = {}
    output = subprocess.check_output(["ip", "-o", "addr"], encoding="utf-8")
    for line in output.strip().split("\n"):
        parts = line.split()
        iface = parts[1]
        family = parts[2]
        ipCidr = parts[3]

        # Skip loopback interface and link-local addresses
        if iface == "lo":
            continue

        if family == "inet6":
            ip = ipCidr.split("/")[0]
            if ipaddress.IPv6Address(ip).is_link_local:
                continue

        result.setdefault(family, {})
        result[family].setdefault(ipCidr, iface)
    return result


class Debugger(DebugService):
    """Debugger main process"""

    def __init__(self, config, sitename):
        super(Debugger, self).__init__(config, sitename)
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service="Debugger")
        self.fullURL = getFullUrl(self.config, sitename)
        self.sitename = sitename
        self.hostname = socket.getfqdn()
        self.diragent = contentDB()
        self.logger.info("====== Debugger Start Work. Hostname: %s", self.hostname)

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.fullURL = getFullUrl(self.config, self.sitename)
        self.hostname = socket.getfqdn()

    def registerService(self):
        """Register this service in SiteFE."""
        out = {"hostname": self.hostname, "servicename": COMPONENT}
        out["serviceinfo"] = getAllIps()
        self.logger.debug(f"Service report: {out}")
        self.logger.info("Will try to publish information to SiteFE")
        outVals = publishToSiteFE(out, self.fullURL, "/sitefe/json/frontend/updateservice")
        self.logger.info("Update Service result %s", outVals)
        if outVals[2] != "OK" or outVals[1] != 200 and outVals[3]:
            excMsg = " Could not publish to SiteFE Frontend."
            excMsg += f"Update to FE: Error: {outVals[2]} HTTP Code: {outVals[1]}"
            self.logger.error(excMsg)
        if excMsg:
            raise PluginException(excMsg)

    def getData(self, url):
        """Get data from FE."""
        self.logger.info(f"Query: {self.fullURL}{url}")
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != "OK":
            msg = f"Received a failure getting information from Site Frontend {str(out)}"
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
        return evaldict(out[0])

    def startwork(self):
        """Main start work function."""
        self.logger.info("Starting Debugger service")
        self.registerService()
        self.logger.info("Will get requests from FE")
        self._startwork()

    def _startwork(self):
        """Start execution and get new requests from FE"""
        for wtype in ["new", "active"]:
            self.logger.info(f"Get all {wtype} requests")
            data = self.getData(f"/sitefe/json/frontend/getalldebughostname/{self.hostname}/{wtype}")
            for item in data:
                # Do we need to get full data from FE? E.G. Request info?
                if not self.backgroundProcessItemExists(item):
                    self.logger.info(f"Background process item does not exist. ID: {item['id']}")
                try:
                    ditem = self.getData(f"/sitefe/json/frontend/getdebug/{item['id']}")
                    if ditem:
                        self.checkBackgroundProcess(ditem)
                except FailedGetDataFromFE as ex:
                    self.logger.error(f"Failed to get data from FE: {ex}")
                    continue


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
