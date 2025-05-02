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
from prometheus_client import (CONTENT_TYPE_LATEST, CollectorRegistry, Enum,
                               Gauge, Info, generate_latest)
from SiteRMLibs.MainUtilities import (evaldict, getAllHosts,
                                      getUTCnow, isValFloat, getFileContentAsJson)


class PrometheusCalls:
    """Prometheus Calls API Module"""

    # pylint: disable=E1101
    def __init__(self):
        self.timenow = int(getUTCnow())
        self.__defineRoutes()
        self.__urlParams()
        self.memMonitor = {}
        self.diskMonitor = {}
        self.arpLabels = {'Device': '', 'Flags': '', 'HWaddress': '',
                          'IPaddress': '', 'Hostname': ''}

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

    def __memStats(self, registry):
        """Refresh all Memory Statistics in FE"""
        memInfo = Gauge(
            "memory_usage",
            "Memory Usage for Service",
            ["servicename", "key"],
            registry=registry,
        )
        # TODO: In future pass agent memory mon usage also, and record it
        for _, hostDict in self.memMonitor.items():
            for serviceName, vals in hostDict.items():
                for key, val in vals.items():
                    labels = {"servicename": serviceName, "key": key}
                    memInfo.labels(**labels).set(val)

    def __diskStats(self, registry):
        """Refresh all Disk Statistics in FE"""
        diskGauge = Gauge("disk_usage",
                          "Disk usage statistics for each filesystem",
                          ["filesystem", "key"],
                          registry=registry)

        for _, hostDict in self.diskMonitor.items():
            for fs, stats in hostDict.get("Values", {}).items():
                tmpfs = fs
                if 'Mounted_on' in stats and stats['Mounted_on']:
                    tmpfs = stats['Mounted_on']
                for key, val in stats.items():
                    labels = {"filesystem": tmpfs, "key": key}
                    if isinstance(val, str):
                        val = val.strip().rstrip('%')
                        try:
                            val = float(val)
                        except ValueError:
                            continue  # skip non-numeric fields
                    diskGauge.labels(**labels).set(val)

    def _addHostArpInfo(self, arpState,  host, arpInfo):
        """Add Host Arp Info"""
        self.arpLabels["Hostname"] = host
        for arpEntry in arpInfo:
            self.arpLabels.update(arpEntry)
            arpState.labels(**self.arpLabels).set(1)


    def __getAgentData(self, registry):
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
            hostDict["hostinfo"] = getFileContentAsJson(hostDict["hostinfo"])
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

    def __getSwitchErrors(self, registry):
        """Add Switch Errors to prometheus output"""
        dbOut = self.dbI.get("switch")
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
            if out:
                for errorkey, errors in out.items():
                    labels = {"errortype": errorkey, "hostname": item['device']}
                    switchErrorsGauge.labels(**labels).set(len(errors))

    def __getSNMPData(self, registry):
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
            labelnames=["vlan", "hostname", "incr"],
            registry=registry,
        )
        for item in snmpData:
            if int(self.timenow - item["updatedate"]) > 300:
                continue
            out = evaldict(item.get("output", {}))
            # Skip hostnamemem- and hostnamedisk- devices. This is covered in __memStats/__diskStats
            if item["hostname"].startswith("hostnamemem-"):
                self.memMonitor[item["hostname"]] = out
                continue
            if item["hostname"].startswith("hostnamedisk-"):
                self.diskMonitor[item["hostname"]] = out
                continue
            for key, val in out.items():
                if key == "macs":
                    if "vlans" in val:
                        for key1, macs in val["vlans"].items():
                            incr = 0
                            for macaddr in macs:
                                labels = {"vlan": key1,"hostname": item["hostname"], "incr": str(incr)}
                                macState.labels(**labels).info({"macaddress": macaddr})
                                incr += 1
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



    def __getServiceStates(self, registry):
        """Get all Services states."""
        serviceState = Enum(
            "service_state",
            "Description of enum",
            labelnames=["servicename", "hostname"],
            states=["OK", "WARNING", "UNKNOWN", "FAILED", "KEYBOARDINTERRUPT", "UNSET"],
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
        self.__getSNMPData(registry)
        self.__getAgentData(registry)
        self.__memStats(registry)
        self.__diskStats(registry)
        self.__getSwitchErrors(registry)

    def __metrics(self, **kwargs):
        """Return all available Hosts, where key is IP address."""
        self.__refreshTimeNow()
        registry = self.__cleanRegistry()
        self.__getServiceStates(registry)
        data = generate_latest(registry)
        del registry # Explicit dereference of Collector Registry
        self.httpresp.ret_200(CONTENT_TYPE_LATEST, kwargs["start_response"], None)
        return iter([data])

    def prometheus(self, _environ, **kwargs):
        """Return prometheus stats."""
        return self.__metrics(**kwargs)
