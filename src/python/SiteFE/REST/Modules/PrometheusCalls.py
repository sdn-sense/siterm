#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Prometheus API Output Calls.

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
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2023 California Institute of Technology
Date                    : 2023/01/03
"""
import copy

import psutil
from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Enum,
                               Gauge, Info, generate_latest)
from SiteRMLibs.MainUtilities import (evaldict, getActiveDeltas, getAllHosts,
                                      getUTCnow, isValFloat)


class PrometheusCalls:
    """Prometheus Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.timenow = int(getUTCnow())
        self.__defineRoutes()
        self.__urlParams()
        self.memMonitor = {}
        self.activeAPI = ActiveWrapper()
        self.arpLabels = {'Device': '', 'Flags': '', 'HWaddress': '',
                          'HWtype': '', 'IPaddress': '', 'Mask': '',
                          'Hostname': ''}

    def __urlParams(self):
        """Define URL Params for this class"""
        urlParams = {"prometheus": {"allowedMethods": ["GET"]}}
        self.urlParams.update(urlParams)

    def __defineRoutes(self):
        """Define Routes for this class"""
        self.routeMap.connect(
            "prometheus", "/json/frontend/metrics", action="prometheus"
        )

    def __refreshTimeNow(self):
        """Refresh timenow"""
        self.timenow = int(getUTCnow())

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __processStats(self, proc, services, lookupid):
        """Get Process Stats - memory"""
        procList = proc.cmdline()
        if len(procList) > lookupid:
            for serviceName in services:
                if procList[lookupid].endswith(serviceName):
                    self.memMonitor.setdefault(
                        serviceName,
                        {
                            "rss": 0,
                            "vms": 0,
                            "shared": 0,
                            "text": 0,
                            "lib": 0,
                            "data": 0,
                            "dirty": 0,
                        },
                    )
                    for key in self.memMonitor[serviceName].keys():
                        if hasattr(proc.memory_info(), key):
                            self.memMonitor[serviceName][key] += getattr(
                                proc.memory_info(), key
                            )

    def __memStats(self, registry, **kwargs):
        """Refresh all Memory Statistics in FE"""

        def procWrapper(proc, services, lookupid):
            """Process Wrapper to catch exited process or zombie process"""
            try:
                self.__processStats(proc, services, lookupid)
            except psutil.NoSuchProcess:
                pass
            except psutil.ZombieProcess:
                pass

        self.memMonitor = {}
        for proc in psutil.process_iter(attrs=None, ad_value=None):
            procWrapper(proc, ["mariadbd", "httpd"], 0)
            procWrapper(
                proc,
                [
                    "Config-Fetcher",
                    "SNMPMonitoring-update",
                    "ProvisioningService-update",
                    "LookUpService-update",
                ],
                1,
            )
        memInfo = Gauge(
            "memory_usage",
            "Memory Usage for Service",
            ["servicename", "key"],
            registry=registry,
        )
        for serviceName, vals in self.memMonitor.items():
            for key, val in vals.items():
                labels = {"servicename": serviceName, "key": key}
                memInfo.labels(**labels).set(val)

    def _addHostArpInfo(self, arpState,  host, arpInfo):
        """Add Host Arp Info"""
        self.arpLabels["Hostname"] = host
        for arpEntry in arpInfo:
            self.arpLabels.update(arpEntry)
            arpState.labels(**self.arpLabels).set(1)


    def __getAgentData(self, registry, **kwargs):
        """Add Agent Data (Cert validity) to prometheus output"""
        agentCertValid = Gauge(
            "agent_cert",
            "Agent Certificate Validity",
            ["hostname", "Key"],
            registry=registry,
        )
        arpState = Gauge('arp_state', 'ARP Address Table for Host',
                         labelnames=self.arpLabels.keys(),
                         registry=registry)
        for host, hostDict in getAllHosts(self.dbI).items():
            hostDict["hostinfo"] = evaldict(hostDict["hostinfo"])
            if int(self.timenow - hostDict["updatedate"]) > 300:
                continue
            if "CertInfo" in hostDict.get("hostinfo", {}).keys():
                for key in ["notAfter", "notBefore"]:
                    keys = {"hostname": host, "Key": key}
                    agentCertValid.labels(**keys).set(
                        hostDict["hostinfo"]["CertInfo"].get(key, 0)
                    )
            if "ArpInfo" in hostDict.get("hostinfo", {}).keys() and hostDict["hostinfo"]["ArpInfo"].get('arpinfo'):
                self._addHostArpInfo(arpState, host, hostDict["hostinfo"]["ArpInfo"]['arpinfo'])

    def __getSwitchErrors(self, registry, **kwargs):
        """Add Switch Errors to prometheus output"""
        dbOut = self.dbI.get("switches")
        switchErrorsGauge = Gauge(
            "switch_errors",
            "Switch Errors",
            ["hostname", "errortype"],
            registry=registry,
        )
        for item in dbOut:
            if int(self.timenow - item["updatedate"]) > 300:
                continue
            out = evaldict(item.get("error", {}))
            for hostname, hostitems in out.items():
                for errorkey, errors in hostitems.items():
                    labels = {"errortype": errorkey, "hostname": hostname}
                    switchErrorsGauge.labels(**labels).set(len(errors))

    def __getSNMPData(self, registry, **kwargs):
        """Add SNMP Data to prometheus output"""
        # Here get info from DB for switch snmp details
        snmpData = self.dbI.get("snmpmon")
        snmpGauge = Gauge(
            "interface_statistics",
            "Interface Statistics",
            ["ifDescr", "ifType", "ifAlias", "hostname", "Key"],
            registry=registry,
        )
        macState = Info(
            "mac_table",
            "Mac Address Table",
            labelnames=["vlan", "hostname"],
            registry=registry,
        )
        for item in snmpData:
            if int(self.timenow - item["updatedate"]) > 300:
                continue
            out = evaldict(item.get("output", {}))
            for key, val in out.items():
                if key == "macs":
                    if "vlans" in val:
                        for key1, macs in val["vlans"].items():
                            for macaddr in macs:
                                labels = {"vlan": key1,"hostname": item["hostname"]}
                                macState.labels(**labels).info({"macaddress": macaddr})
                    continue
                keys = {
                    "ifDescr": val.get("ifDescr", ""),
                    "ifType": val.get("ifType", ""),
                    "ifAlias": val.get("ifAlias", ""),
                    "hostname": item["hostname"],
                }
                for key1 in self.config["MAIN"]["snmp"]["mibs"]:
                    if key1 in val and isValFloat(val[key1]):
                        keys["Key"] = key1
                        snmpGauge.labels(**keys).set(val[key1])

    def __getActiveQoSStates(self, registry, **kwargs):
        """Report in prometheus NetworkStatus and QoS Params"""
        labelnames = ["action", "tag", "key0", "key1", "key2", "vlan", "uri"]
        labelqos = [
            "action",
            "tag",
            "key0",
            "key1",
            "key2",
            "vlan",
            "uri",
            "unit",
            "type",
            "valuetype",
        ]

        def genStatusLabels(item):
            """Generate Status Labels"""
            out = {}
            for key in labelnames:
                out[key] = item.get(key, "")
            return out

        def getQoSLabels(item):
            """Generate QoS Labels"""
            out = {}
            for key in labelqos:
                out[key] = item.get(key, "")
            return out

        netState = Enum(
            "network_status",
            "Network Status information",
            labelnames=labelnames,
            states=[
                "activated",
                "activate-error",
                "deactivated",
                "deactivate-error",
                "unknown",
            ],
            registry=registry,
        )
        qosGauge = Gauge(
            "qos_status", "QoS Requests Status", labelqos, registry=registry
        )

        currentActive = getActiveDeltas(self)
        for item in self.activeAPI.generateReport(currentActive):
            netstatus = item.get("networkstatus", "unknown")
            if not netstatus:
                netstatus = "unknown"
            netState.labels(**genStatusLabels(item)).state(netstatus)
            if "uri" in item and item["uri"]:
                for key in [
                    "availableCapacity",
                    "granularity",
                    "maximumCapacity",
                    "priority",
                    "reservableCapacity",
                ]:
                    labels = getQoSLabels(item)
                    labels["valuetype"] = key
                    qosGauge.labels(**labels).set(item.get(key, 0))

    def __getServiceStates(self, registry, **kwargs):
        """Get all Services states."""
        serviceState = Enum(
            "service_state",
            "Description of enum",
            labelnames=["servicename", "hostname"],
            states=["OK", "UNKNOWN", "FAILED", "KEYBOARDINTERRUPT", "UNSET"],
            registry=registry,
        )
        runtimeInfo = Gauge(
            "service_runtime",
            "Service Runtime",
            ["servicename", "hostname"],
            registry=registry,
        )
        infoState = Info(
            "running_version",
            "Running Code Version.",
            labelnames=["servicename", "hostname"],
            registry=registry,
        )
        services = self.dbI.get("servicestates")
        for service in services:
            state = "UNKNOWN"
            runtime = -1
            if (
                service["servicename"]
                in ["SNMPMonitoring", "ProvisioningService", "LookUpService"]
                and service.get("hostname", "UNSET") != "default"
            ):
                continue
            if int(self.timenow - service["updatedate"]) < 600:
                # If we are not getting service state for 10 mins, set state as unknown
                state = service["servicestate"]
                runtime = service["runtime"]
            labels = {
                "servicename": service["servicename"],
                "hostname": service.get("hostname", "UNSET"),
            }
            serviceState.labels(**labels).state(state)
            infoState.labels(**labels).info({"version": service["version"]})
            runtimeInfo.labels(**labels).set(runtime)
        self.__getSNMPData(registry, **kwargs)
        self.__getAgentData(registry, **kwargs)
        self.__memStats(registry, **kwargs)
        self.__getSwitchErrors(registry, **kwargs)
        self.__getActiveQoSStates(registry, **kwargs)

    def __metrics(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        self.__refreshTimeNow()
        registry = self.__cleanRegistry()
        self.__getServiceStates(registry, **kwargs)
        data = generate_latest(registry)
        self.httpresp.ret_200(CONTENT_TYPE_LATEST, kwargs["start_response"], None)
        return iter([data])

    def prometheus(self, environ, **kwargs):
        """Return prometheus stats."""
        return self.__metrics(**kwargs)


class ActiveWrapper:
    """Active State and QoS Wrapper to report in prometheus format"""

    def __init__(self):
        self.reports = []

    def __clean(self):
        """Clean Reports"""
        self.reports = []

    def _addStats(self, indict, **kwargs):
        """Get all Stats and add to list"""
        kwargs["tag"] = indict.get("_params", {}).get("tag", "")
        kwargs["networkstatus"] = indict.get("_params", {}).get("networkstatus", "")
        if "hasLabel" in indict and indict["hasLabel"].get("value", ""):
            kwargs["vlan"] = f"Vlan {indict['hasLabel']['value']}"
        self.reports.append(kwargs)

        if "hasService" in indict and indict["hasService"].get("uri", ""):
            tmpargs = copy.deepcopy(kwargs)
            tmpargs["uri"] = indict["hasService"]["uri"]
            tmpargs["networkstatus"] = (
                indict["hasService"].get("_params", {}).get("networkstatus", "")
            )
            for key in [
                "availableCapacity",
                "granularity",
                "maximumCapacity",
                "priority",
                "reservableCapacity",
                "type",
                "unit",
            ]:
                tmpargs[key] = indict["hasService"].get(key, "")
            self.reports.append(tmpargs)

    def _activeLooper(self, indict, **kwargs):
        """Loop over nested dictionary of activatestates up to level 3"""
        kwargs["level"] += 1
        if kwargs["level"] == 3:
            self._addStats(indict, **kwargs)
            return
        for key, vals in indict.items():
            if key == "_params":
                kwargs["tag"] = vals.get("tag", "")
                kwargs["networkstatus"] = vals.get("networkstatus", "")
                self.reports.append(kwargs)
                continue
            if isinstance(vals, dict) and kwargs["level"] < 3:
                kwargs[f"key{kwargs['level']}"] = key
                self._activeLooper(vals, **kwargs)
        return

    def _loopActKey(self, tkey, out):
        """Loop over vsw/rst key"""
        for key, vals in out.get("output", {}).get(tkey, {}).items():
            self._activeLooper(vals, **{"action": tkey, "key0": key, "level": 0})

    def generateReport(self, out):
        """Generate output"""
        self.__clean()
        for key in ["vsw", "rst"]:
            self._loopActKey(key, out)
        return self.reports
