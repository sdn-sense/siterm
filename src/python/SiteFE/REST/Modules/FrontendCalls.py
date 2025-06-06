#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Frontend API Calls (config, db interface)

Copyright 2023 California Institute of Technology
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
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
from SiteRMLibs.MainUtilities import evaldict, getFileContentAsJson
from SiteRMLibs.MainUtilities import getUTCnow, read_input_data
from SiteRMLibs.CustomExceptions import NotFoundError


class FrontendCalls:
    """Frontend Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.__defineRoutes()
        self.__urlParams()

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {
            "feconfig": {"allowedMethods": ["GET"]},
            "getdata": {"allowedMethods": ["GET"]},
            "gethosts": {"allowedMethods": ["GET"]},
            "getswitchdata": {"allowedMethods": ["GET"]},
            "getactivedeltas": {"allowedMethods": ["GET"]},
            "getqosdata": {"allowedMethods": ["GET"]},
            "getservicestates": {"allowedMethods": ["GET"]},
            "setinstancestartend": {"allowedMethods": ["POST"]},
        }
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect(
            "feconfig", "/json/frontend/configuration", action="feconfig"
        )
        self.routeMap.connect("getdata", "/json/frontend/getdata", action="getdata")
        self.routeMap.connect("gethosts", "/json/frontend/gethosts", action="gethosts")
        self.routeMap.connect(
            "getswitchdata", "/json/frontend/getswitchdata", action="getswitchdata"
        )
        self.routeMap.connect(
            "getactivedeltas",
            "/json/frontend/getactivedeltas",
            action="getactivedeltas",
        )
        self.routeMap.connect(
            "getqosdata", "/json/frontend/getqosdata", action="getqosdata"
        )
        self.routeMap.connect(
            "getservicestates",
            "/json/frontend/getservicestates",
            action="getservicestates",
        )
        self.routeMap.connect(
            "setinstancestartend",
            "/json/frontend/setinstancestartend",
            action="setinstancestartend",
        )

    def feconfig(self, environ, **kwargs):
        """Returns Frontend configuration"""
        self.responseHeaders(environ, **kwargs)
        return self.config["MAIN"]

    def gethosts(self, environ, **kwargs):
        """Return all available Hosts, where key is IP address."""
        hosts = self.dbI.get("hosts", orderby=["updatedate", "DESC"], limit=50)
        out = []
        for host in hosts:
            host["hostinfo"] = getFileContentAsJson(host.get("hostinfo", ""))
            out.append(host)
        self.responseHeaders(environ, **kwargs)
        return out

    def getdata(self, environ, **kwargs):
        """Return all available Hosts data, where key is IP address."""
        hosts = self.dbI.get("hosts", orderby=["updatedate", "DESC"], limit=50)
        out = []
        for host in hosts:
            host["hostinfo"] = getFileContentAsJson(host.get("hostinfo", ""))
            out.append(host)
        self.responseHeaders(environ, **kwargs)
        return out

    def getswitchdata(self, environ, **kwargs):
        """Return all Switches information"""
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get("switch", orderby=["updatedate", "DESC"], limit=50)

    def getactivedeltas(self, environ, **kwargs):
        """Return all Active Deltas"""
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get("activeDeltas", orderby=["updatedate", "DESC"], limit=1)

    def getqosdata(self, environ, **kwargs):
        """Return QoS Stats for all IPv6 Ranges"""
        self.responseHeaders(environ, **kwargs)
        hosts = self.dbI.get("hosts", orderby=["updatedate", "DESC"], limit=50)
        out = {}
        for host in hosts:
            tmpH = getFileContentAsJson(host.get("hostinfo", ""))
            tmpInf = (
                tmpH.get("Summary", {})
                .get("config", {})
                .get("qos", {})
                .get("interfaces", {})
            )
            if not tmpInf:
                continue
            for _intf, intfDict in tmpInf.items():
                maxThrg = (
                    tmpH.get("Summary", {})
                    .get("config", {})
                    .get(intfDict["master_intf"], {})
                    .get("bwParams", {})
                    .get("maximumCapacity", None)
                )
                if maxThrg:
                    for ipkey in ["ipv4", "ipv6"]:
                        tmpIP = intfDict.get(f"{ipkey}_range", None)
                        if isinstance(tmpIP, list):
                            for ipaddr in tmpIP:
                                out.setdefault(ipaddr, 0)
                                out[ipaddr] += maxThrg
                        elif tmpIP:
                            out.setdefault(tmpIP, 0)
                            out[tmpIP] += maxThrg
                else:
                    print(
                        f"QoS Configure for {intfDict['master_intf']}, but it is not defined in agent config. Misconfig."
                    )
        return [out]

    def getservicestates(self, environ, **kwargs):
        """Return Service states"""
        self.responseHeaders(environ, **kwargs)
        return self.dbI.get("servicestates", orderby=["updatedate", "DESC"], limit=100)

    def setinstancestartend(self, environ, **kwargs):
        """Set Instance Start and End time"""
        inputDict = read_input_data(environ)
        # Check if instance ID provided
        instanceID = inputDict.get("instanceid", None)
        if not instanceID:
            raise NotFoundError("Instance ID is not provided.")
        # Validate that these entries are known...
        activeDeltas = self.dbI.get(
            "activeDeltas", orderby=["updatedate", "DESC"], limit=1
        )
        if not activeDeltas:
            raise NotFoundError("No Active Deltas found.")

        activeDeltas = activeDeltas[0]
        activeDeltas["output"] = evaldict(activeDeltas["output"])
        found = False
        if instanceID in activeDeltas.get("output", {}).get("vsw", {}):
            found = True
        if instanceID in activeDeltas.get("output", {}).get("rst", {}):
            found = True
        if not found:
            raise NotFoundError(
                f"Instance ID {instanceID} is not found in activeDeltas."
            )

        # Insert start and end time in instancestartend table
        out = {
            "instanceid": instanceID,
            "insertdate": getUTCnow(),
            "endtimestamp": inputDict.get("endtimestamp", 0),
            "starttimestamp": inputDict.get("starttimestamp", 0),
        }
        insOut = self.dbI.insert("instancestartend", [out])
        self.responseHeaders(environ, **kwargs)
        return {"Status": insOut[0], "ID": insOut[2]}
