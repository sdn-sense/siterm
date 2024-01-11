#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Host API SubCalls

Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
Date                    : 2024/01/03
"""
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.MainUtilities import getUTCnow


class HostSubCalls:
    """Host Info/Add/Update Calls API Sub Module"""

    def _host_supportedService(self, servicename):
        """Check if service is supported."""
        if servicename == "ALL":
            return True
        if servicename in self.host_services:
            return True
        return False

    def _host_reportServiceStatus(self, **kwargs):
        """Report service state to DB."""
        reported = True
        try:
            dbOut = {
                "hostname": kwargs.get("hostname", "default"),
                "servicestate": kwargs.get("servicestate", "UNSET"),
                "servicename": kwargs.get("servicename", "UNSET"),
                "runtime": kwargs.get("runtime", -1),
                "version": kwargs.get("version", runningVersion),
                "updatedate": getUTCnow(),
            }
            services = self.dbI.get(
                "servicestates",
                search=[
                    ["hostname", dbOut["hostname"]],
                    ["servicename", dbOut["servicename"]],
                ],
            )
            if services:
                self.dbI.update("servicestates", [dbOut])
            else:
                self.dbI.insert("servicestates", [dbOut])
        except NoOptionError:
            reported = False
        except Exception as ex:
            raise Exception("Error details in reportServiceStatus.") from ex
        return reported

    def _host_recordServiceAction(self, **kwargs):
        """Record service action to DB."""
        services = []
        if kwargs["servicename"] != "ALL":
            services.append(kwargs["servicename"])
        else:
            services = self.host_services
        runningServices = self.dbI.get("servicestates")
        dbOuts = []
        for service in runningServices:
            add = False
            if service["servicename"] in services:
                if kwargs.get("hostname", "") != "ALL" and service[
                    "hostname"
                ] == kwargs.get("hostname", ""):
                    add = True
                elif kwargs.get("hostname", "") == "ALL":
                    add = True
                else:
                    statein = self.dbI.get(
                        "serviceaction",
                        search=[
                            ["hostname", service["hostname"]],
                            ["servicename", service["servicename"]],
                            ["serviceaction", kwargs["action"]],
                        ],
                    )
                    if statein:
                        add = True
            if add:
                dbOut = {
                    "hostname": service["hostname"],
                    "servicename": service["servicename"],
                    "serviceaction": kwargs["action"],
                    "insertdate": getUTCnow(),
                }
                self.dbI.insert("serviceaction", [dbOut])
                dbOuts.append(dbOut)
        if not dbOuts:
            raise Exception(f"No Services identified for params: {kwargs}")
        return dbOuts

    def _host_deleteServiceAction(self, **kwargs):
        """Delete service action from DB."""
        dbOut = []
        for key in ['id', 'hostname', 'servicename']:
            if key in kwargs:
                dbOut.append([key, kwargs[key]])
        self.dbI.delete("serviceaction", dbOut)
