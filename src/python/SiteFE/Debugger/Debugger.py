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
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.ipaddr import ipVersion, checkoverlap
from SiteRMLibs.DebugService import DebugService
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.Validator import Validator
from SiteRMLibs.CustomExceptions import BadRequestError

COMPONENT = "Debugger"


# pylint: disable=R0902,R1725
# R0902 - too many instance attributes
# R1725 - super with arguments
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
        self.debugdir = os.path.join(
            self.config.get(self.sitename, "privatedir"), "DebugRequests"
        )
        self.dbI = getVal(
            getDBConn("DebuggerService", self), **{"sitename": self.sitename}
        )
        self.logger.info("====== Debugger Start Work. Sitename: %s", self.sitename)
        self.validator = Validator(self.config)

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

    def updateDebugWorker(self, **kwargs):
        "Update hostname/workername for debug request"
        out = {
            "id": kwargs["id"],
            "state": kwargs["state"],
            "hostname": kwargs["hostname"],
            "updatedate": getUTCnow(),
        }
        self.dbI.update("debugrequestsworker", [out])

    def getFullData(self, hostname, item):
        """Get full data from DB."""
        debugdir = os.path.join(
            self.config.get(self.sitename, "privatedir"), "DebugRequests"
        )
        # Get Request JSON
        requestfname = os.path.join(debugdir, hostname, str(item["id"]), "request.json")
        item["requestdict"] = getFileContentAsJson(requestfname)
        return item

    def loadAllWorkers(self):
        """Load all workers from DB not older than 1 minute."""
        services = self.dbI.get("services", orderby=["updatedate", "DESC"], limit=100)
        workers = {}
        for service in services:
            if service["hostname"] not in workers:
                # Check if service is not older than 2 minutes
                if service.get("updatedate", 0) > getUTCnow() - 120:
                    workers[service["hostname"]] = {
                        "hostname": service["hostname"],
                        "servicename": service["servicename"],
                        "updatedate": service["updatedate"],
                    }
                    # Load service information from file
                    if service.get("serviceinfo"):
                        if os.path.exists(service["serviceinfo"]):
                            workers[service["hostname"]]["serviceinfo"] = (
                                getFileContentAsJson(service["serviceinfo"])
                            )
                        else:
                            self.logger.warning(
                                "Service info file does not exist: {service}"
                            )
        self.logger.debug("Loaded workers: %s", workers)
        return workers

    def _findRangeOverlap(self, item, workers):
        """Find range overlap for the item."""
        dynamicfrom = item.get("requestdict", {}).get("dynamicfrom", None)
        if not dynamicfrom:
            return None, None, f"Input has no dynamicfrom value. Input: {item}"
        iptype = ipVersion(dynamicfrom)
        if iptype == "-1":
            return None, None, f"Unable to identify ipVersion for {input}"
        iptype = "inet" if iptype == "4" else "inet6"
        for workername, workerd in workers.items():
            if iptype not in workerd:
                self.logger.debug(f"Worker {workername} has no {iptype}")
                continue
            for ipval in workerd.get(iptype):
                if checkoverlap(dynamicfrom, ipval):
                    self.logger.info(f"Found overlap for {item} with {workername}")
                    return workername, ipval, ""
        return None, None, f"After all checks, no worker found suitable for {item}"

    def identifyWorker(self):
        """Identify worker for a third party service, e.g. hostname not defined"""
        data = self.getData("undefined", "new")
        if not data:
            self.logger.info("No new requests for unknown worker")
        workers = self.loadAllWorkers()
        for item in data:
            item = self.getFullData("undefined", item)
            # Load request information;
            item["requestdict"] = getFileContentAsJson(item["debuginfo"])
            workername, ipf, errmsg = self._findRangeOverlap(item, workers)
            if not errmsg:
                item["requestdict"]["selectedip"] = ipf
                item["requestdict"]["hostname"] = workername
                try:
                    item["requestdict"] = self.validator.validate(item["requestdict"])
                    self.dumpFileContentAsJson(item["debuginfo"], item["requestdict"])
                    self.updateDebugWorker(
                        **{"id": item["id"], "state": "new", "hostname": workername}
                    )
                except BadRequestError as ex:
                    errmsg = f"Received error during validate: {str(ex)}"
            if errmsg:
                retOut = {
                    "processOut": [],
                    "stdout": [],
                    "stderr": [errmsg],
                    "jsonout": {},
                    "exitCode": -1,
                }
                self.dumpFileContentAsJson(item["outputinfo"], retOut)
                self.logger.error(f"Received an error to identify worker: {errmsg}")
                self.updateDebugWorker(
                    **{
                        "id": item["id"],
                        "state": "failed",
                        "hostname": workername if workername else "notfound",
                    }
                )
                continue

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
