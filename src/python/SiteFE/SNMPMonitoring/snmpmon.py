#!/usr/bin/env python3
# pylint: disable=E1101
"""
    SNMPMonitoring gets all information from switches using SNMP and writes to DB.

Config example:
snmp_monitoring:
  session_vars:
    community: mgmt_hep
    hostname: 172.16.1.1
    version: 2
  mac_parser:
    mib: "mib-2.17.7.1.2.2.1.3."
    oid: "1.3.6.1.2.1.17.7.1.2.2.1.3"

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/11/21
"""
import copy
import os
import sys

from easysnmp import Session
from easysnmp.exceptions import EasySNMPTimeoutError, EasySNMPUnknownObjectIDError
from prometheus_client import CollectorRegistry, Enum, Gauge, Info, generate_latest
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.DefaultParams import SERVICE_DEAD_TIMEOUT, SERVICE_DOWN_TIMEOUT
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    contentDB,
    evaldict,
    getActiveDeltas,
    getAllHosts,
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    getVal,
    isValFloat,
    jsondumps,
)
from SiteRMLibs.MemDiskStats import MemDiskStats
from SiteRMLibs.Warnings import Warnings


class Topology:
    """Topology json preparation for visualization"""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="SNMPMonitoring")
        self.dbI = getVal(getDBConn("SNMPMonitoring", self), **{"sitename": self.sitename})
        self.diragent = contentDB()
        self.topodir = os.path.join(self.config.get(sitename, "privatedir"), "Topology")

    @staticmethod
    def _findConnection(workdata, remMac):
        """Find connections based on MAC aaddress"""
        if not remMac:
            return None
        for switch, switchdata in workdata.items():
            if remMac in switchdata["macs"]:
                return {"switch": switch, "id": switchdata["id"]}
        return None

    @staticmethod
    def _getansdata(indata, keys):
        """Get Ansible data from ansible output"""
        if len(keys) == 1:
            return indata.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get(keys[0], {})
        if len(keys) == 2:
            return indata.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get(keys[0], {}).get(keys[1], {})
        return {}

    def getWANLinks(self, incr):
        """Get WAN Links for visualization"""
        wan_links = {}
        sitename = getSiteNameFromConfig(self.config)
        for sw in self.config["MAIN"].get(sitename, {}).get("switch", []):
            if not self.config["MAIN"].get(sw, {}):
                continue
            if not isinstance(self.config["MAIN"].get(sw, {}).get("ports", None), dict):
                continue
            for _, val in self.config["MAIN"].get(sw, {}).get("ports", {}).items():
                if "wanlink" in val and val["wanlink"] and val.get("isAlias", None):
                    wan_links.setdefault(
                        f"wan{incr}",
                        {
                            "_id": incr,
                            "topo": {},
                            "DeviceInfo": {"type": "cloud", "name": val["isAlias"]},
                        },
                    )
                    wan_links[f"wan{incr}"]["topo"].setdefault(val["isAlias"].split(":")[-1], {"device": sw, "port": val})
                    incr += 1
        return wan_links

    def gettopology(self):
        """Return all Switches information"""

        def getHostPortSpeed(netinfo, port):
            """Get Port Speed from Host NetInfo"""
            bw = netinfo.get(port, {}).get("bwParams", {}).get("portSpeed", 0)
            if bw:
                return bw
            return netinfo.get(port, {}).get("bwParams", {}).get("maximumCapacity", 0)

        workdata = {}
        incr = 0
        # Get all Switch information
        for item in self.dbI.get("switch", orderby=["updatedate", "DESC"], limit=100):
            if "output" not in item:
                continue
            tmpdict = evaldict(item["output"])
            workdata[item["device"]] = {"id": incr, "type": "switch"}
            incr += 1
            for dkey, keys in {
                "macs": ["ansible_net_info", "macs"],
                "lldp": ["ansible_net_lldp"],
                "intstats": ["ansible_net_interfaces"],
            }.items():
                workdata[item["device"]][dkey] = self._getansdata(tmpdict, keys)
        # Now that we have specific data; lets loop over it and get nodes/links
        out = {}
        for switch, switchdata in workdata.items():
            swout = out.setdefault(
                switch,
                {
                    "topo": {},
                    "DeviceInfo": {"type": "switch", "name": switch},
                    "_id": switchdata["id"],
                },
            )
            for key, vals in switchdata["lldp"].items():
                remSwitch = self._findConnection(workdata, vals.get("remote_chassis_id", ""))
                remPort = vals.get("remote_port_id", "")
                if remSwitch and remPort:
                    bw = switchdata["intstats"][key].get("bandwidth", 0)
                    swout["topo"].setdefault(key, {"device": remSwitch["switch"], "port": remPort, "bandwidth": bw})
                    print(swout["topo"][key])
        # Now lets get host information
        for host in self.dbI.get("hosts", orderby=["updatedate", "DESC"], limit=100):
            parsedInfo = self.diragent.getFileContentAsJson(host.get("hostinfo", ""))
            hostconfig = parsedInfo.get("Summary", {}).get("config", {})
            netinfo = parsedInfo.get("NetInfo", {}).get("interfaces", {})
            hostname = hostconfig.get("agent", {}).get("hostname", "")
            lldpInfo = parsedInfo.get("NetInfo", {}).get("lldp", {})
            hout = out.setdefault(
                hostname,
                {
                    "topo": {},
                    "DeviceInfo": {
                        "type": "server",
                        "name": hostname,
                    },
                    "_id": incr,
                },
            )
            incr += 1
            if lldpInfo:
                for intf, vals in lldpInfo.items():
                    remSwitch = self._findConnection(workdata, vals.get("remote_chassis_id", ""))
                    remPort = vals.get("remote_port_id", "")
                    if remSwitch and remPort:
                        hout["topo"].setdefault(intf, {"device": remSwitch["switch"], "port": remPort, "bandwidth": getHostPortSpeed(netinfo, intf)})
                        print(hout["topo"][intf])
            else:
                for intf in hostconfig.get("agent", {}).get("interfaces", []):
                    swintf = hostconfig.get(intf, {}).get("port", "")
                    switch = hostconfig.get(intf, {}).get("switch", "")
                    if switch and swintf:
                        hout["topo"].setdefault(intf, {"device": switch, "port": swintf, "bandwidth": getHostPortSpeed(netinfo, intf)})
                        print(hout["topo"][intf])
        out.update(self.getWANLinks(incr))
        # Write new out to file
        fname = os.path.join(self.topodir, "topology.json")
        self.diragent.dumpFileContentAsJson(fname, out)


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
            tmpargs["networkstatus"] = indict["hasService"].get("_params", {}).get("networkstatus", "")
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

    def loopActKey(self, tkey, out):
        """Loop over vsw/rst key"""
        for key, vals in out.get("output", {}).get(tkey, {}).items():
            self._activeLooper(vals, **{"action": tkey, "key0": key, "level": 0})

    def generateReport(self, out):
        """Generate output"""
        self.__clean()
        for key in ["vsw", "rst", "kube", "singleport"]:
            self.loopActKey(key, out)
        result = copy.deepcopy(self.reports)
        self.__clean()
        return result


class PromOut:
    """Prometheus Output Class"""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="SNMPMonitoring")
        self.dbI = getVal(getDBConn("SNMPMonitoring", self), **{"sitename": self.sitename})
        self.diragent = contentDB()
        self.timenow = int(getUTCnow())
        self.activeAPI = ActiveWrapper()
        self.diskMonitor = {}
        self.memMonitor = {}
        self.arpLabels = {
            "Device": "",
            "Flags": "",
            "HWaddress": "",
            "IPaddress": "",
            "Hostname": "",
        }
        self.snmpdir = os.path.join(self.config.get(sitename, "privatedir"), "SNMPData")

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def refreshTimeNow(self):
        """Refresh timenow"""
        self.timenow = int(getUTCnow())

    def __memStats(self, registry):
        """Refresh all Memory Statistics in FE"""
        memInfo = Gauge(
            "memory_usage",
            "Memory Usage for Service",
            ["servicename", "key", "hostname"],
            registry=registry,
        )
        for hostname, hostDict in self.memMonitor.items():
            for serviceName, vals in hostDict.items():
                for key, val in vals.items():
                    labels = {"servicename": serviceName, "key": key, "hostname": hostname}
                    memInfo.labels(**labels).set(val)

    def __diskStats(self, registry):
        """Refresh all Disk Statistics in FE"""
        diskGauge = Gauge(
            "disk_usage",
            "Disk usage statistics for each filesystem",
            ["filesystem", "key", "hostname"],
            registry=registry,
        )

        for hostname, hostDict in self.diskMonitor.items():
            for fs, stats in hostDict.get("Values", {}).items():
                tmpfs = fs
                if "Mounted_on" in stats and stats["Mounted_on"]:
                    tmpfs = stats["Mounted_on"]
                for key, val in stats.items():
                    labels = {"filesystem": tmpfs, "key": key, "hostname": hostname}
                    if isinstance(val, str):
                        val = val.strip().rstrip("%")
                        try:
                            val = float(val)
                        except ValueError:
                            continue  # skip non-numeric fields
                    diskGauge.labels(**labels).set(val)

    def _addHostArpInfo(self, arpState, host, arpInfo):
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
        arpState = Gauge(
            "arp_state",
            "ARP Address Table for Host",
            labelnames=self.arpLabels.keys(),
            registry=registry,
        )
        for host, hostDict in getAllHosts(self.dbI).items():
            hostDict["hostinfo"] = self.diragent.getFileContentAsJson(hostDict["hostinfo"])
            if int(self.timenow - hostDict["updatedate"]) > SERVICE_DOWN_TIMEOUT:
                self.logger.warning(f"Host {host} did not update in the last {SERVICE_DOWN_TIMEOUT // 60} minutes. Skipping.")
                continue
            if "CertInfo" in hostDict.get("hostinfo", {}).keys():
                for key in ["notAfter", "notBefore"]:
                    keys = {"hostname": host, "Key": key}
                    agentCertValid.labels(**keys).set(hostDict["hostinfo"]["CertInfo"].get(key, 0))
            if "ArpInfo" in hostDict.get("hostinfo", {}).keys() and hostDict["hostinfo"]["ArpInfo"].get("arpinfo"):
                self._addHostArpInfo(arpState, host, hostDict["hostinfo"]["ArpInfo"]["arpinfo"])

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
            out = evaldict(item.get("error", {}))
            if out:
                for errorkey, errors in out.items():
                    labels = {"errortype": errorkey, "hostname": item["device"]}
                    switchErrorsGauge.labels(**labels).set(len(errors))

    def __getSNMPData(self, registry):
        """Add SNMP Data to prometheus output"""
        # Here get info from DB for switch snmp details
        snmpData = self.dbI.get("snmpmon")
        if not snmpData:
            return
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
            if int(self.timenow - item["updatedate"]) > SERVICE_DOWN_TIMEOUT:
                self.logger.warning(f"SNMP {item['hostname']} did not update in the last {SERVICE_DOWN_TIMEOUT // 60} minutes. Skipping.")
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
                                labels = {
                                    "vlan": key1,
                                    "hostname": item["hostname"],
                                    "incr": str(incr),
                                }
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

    def __getActiveQoSStates(self, registry):
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
            states=["activating", "activated", "activate-error", "deactivated", "deactivate-error", "unknown", "unset"],
            registry=registry,
        )
        qosGauge = Gauge("qos_status", "QoS Requests Status", labelqos, registry=registry)

        currentActive = getActiveDeltas(self)
        for item in self.activeAPI.generateReport(currentActive):
            netstatus = item.get("networkstatus", "unset")
            if not netstatus:
                netstatus = "unset"
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
            if service["servicename"] in ["SNMPMonitoring", "ProvisioningService", "LookUpService"] and service.get("hostname", "UNSET") != "default":
                continue
            if int(self.timenow - service["updatedate"]) < SERVICE_DEAD_TIMEOUT:
                # If we are not getting service state for SERVICE_DEAD_TIMEOUT mins, set state as unknown
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
        self.__getActiveQoSStates(registry)

    def metrics(self):
        """Return all available Hosts, where key is IP address."""
        self.refreshTimeNow()
        registry = self.__cleanRegistry()
        self.__getServiceStates(registry)
        data = generate_latest(registry)
        del registry  # Explicit dereference of Collector Registry
        fname = os.path.join(self.snmpdir, "snmpinfo.txt")
        self.diragent.dumpFileContent(fname, data)


class SNMPMonitoring(Warnings):
    """SNMP Monitoring Class"""

    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="SNMPMonitoring")
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn("SNMPMonitoring", self), **{"sitename": self.sitename})
        self.diragent = contentDB()
        self.switches = {}
        self.session = None
        self.prom = PromOut(config, sitename)
        self.topo = Topology(config, sitename)
        self.hostconf = {}
        self.memdisk = MemDiskStats()

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def _start(self):
        """Start SNMP Monitoring Process"""
        self.runcount += 1
        if self.runcount >= 100:
            self.cleanWarnings()
        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()

    def _getSNMPSession(self, host):
        self.session = None
        self.hostconf.setdefault(host, {})
        self.hostconf[host] = self.switch.plugin.getHostConfig(host)
        if self.config.config["MAIN"].get(host, {}).get("external_snmp", ""):
            snmphost = self.config.config["MAIN"][host]["external_snmp"]
            self.logger.info(f"SNMP Scan skipped for {host}. Remote endpoint defined: {snmphost}")
            return
        if "snmp_monitoring" not in self.hostconf[host]:
            self.logger.info(f"Ansible host: {host} config does not have snmp_monitoring parameters")
            return
        if "session_vars" not in self.hostconf[host]["snmp_monitoring"]:
            self.logger.info(f"Ansible host: {host} config does not have session_vars parameters")
            return
        # easysnmp does not support ipv6 and will fail with ValueError (unable to unpack)
        # To avoid this, we will bypass ipv6 check if error is raised.
        try:
            self.session = Session(**self.hostconf[host]["snmp_monitoring"]["session_vars"])
        except ValueError:
            conf = self.hostconf[host]["snmp_monitoring"]["session_vars"]
            hostname = conf.pop("hostname")
            self.session = Session(**conf)
            self.session.update_session(hostname=hostname)

    def _getSNMPVals(self, key, host=None):
        try:
            allvals = self.session.walk(key)
            return allvals
        except EasySNMPUnknownObjectIDError as ex:
            ex = f"[{host}]: Got SNMP UnknownObjectID Exception for key {key}: {ex}"
            self.logger.warning(ex)
            self.addWarning(ex)
        except EasySNMPTimeoutError as ex:
            ex = f"[{host}]: Got SNMP Timeout Exception: {ex}"
            self.addWarning(ex)
            self.logger.warning(ex)
        return []

    def _ansiblemac(self, host, macs):
        """Custom Mac Parser (custom as it requires to get multiple values)"""
        # Junos uses ansible to get mac addresses
        # mainly because SNMP not always returns vlan id associated with mac address
        # There might be some MIBs/oids which can be used to get this information
        # for now, we will use ansible to get mac addresses (as enabling more features
        # at sites - might be more complex)
        # FRR - runs on top of linux, so we will get mac addresses via ansible
        updatedate = self.switch.switches.get("output", {}).get(host, {}).get("dbinfo", {}).get("updatedate", 0)
        if (getUTCnow() - updatedate) > 1200:
            self.logger.info(f"[{host}]: Forcing ansible to update device information")
            self.switch.deviceUpdate(self.sitename, host)
        self.switch.getinfo()
        mactable = self.switch.output.get("mactable", {}).get(host, {})
        macs.setdefault(host, {"vlans": {}})
        for vlanid, allmacs in mactable.items():
            if not self._isVlanAllowed(host, vlanid):
                continue
            macs[host]["vlans"].setdefault(vlanid, [])
            for mac in allmacs:
                macs[host]["vlans"][vlanid].append(mac)

    def _writeToDB(self, host, output):
        """Write SNMP Data to DB"""
        out = {
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
            "hostname": host,
            "output": jsondumps(output),
        }
        dbOut = self.dbI.get("snmpmon", limit=1, search=[["hostname", host]])
        if dbOut:
            out["id"] = dbOut[0]["id"]
            self.dbI.update("snmpmon", [out])
        else:
            self.dbI.insert("snmpmon", [out])

    def _isVlanAllowed(self, host, vlan):
        try:
            if int(vlan) in self.config.get(host, "vlan_range_list"):
                return True
        except Exception:
            return False
        return False

    def _getMacAddrSession(self, host, macs):
        # Junos does not provide this information via SNMP, we do it via ansible
        # FRR runs on linux, and we get this data via ansible.
        if self.hostconf[host].get("ansible_network_os", "undefined") in ["sense.junos.junos", "sense.frr.frr"]:
            self._ansiblemac(host, macs)
            return
        if not self.session:
            return
        macs.setdefault(host, {"vlans": {}})
        if "mac_parser" in self.hostconf[host]["snmp_monitoring"]:
            oid = self.hostconf[host]["snmp_monitoring"]["mac_parser"]["oid"]
            mib = self.hostconf[host]["snmp_monitoring"]["mac_parser"]["mib"]
            allvals = self._getSNMPVals(oid, host)
            for item in allvals:
                splt = item.oid[(len(mib)) :].split(".")
                vlan = splt.pop(0)
                mac = [format(int(x), "02x") for x in splt]
                if self._isVlanAllowed(host, vlan):
                    macs[host]["vlans"].setdefault(vlan, [])
                    macs[host]["vlans"][vlan].append(":".join(mac))

    def getMemStats(self):
        """Refresh all Memory Statistics in FE"""
        self.memdisk.reset()
        self.memdisk.updateMemStats(["mariadbd", "httpd"], 0)
        self.memdisk.updateMemStats(
            [
                "Config-Fetcher",
                "SNMPMonitoring-update",
                "ProvisioningService-update",
                "LookUpService-update",
                "siterm-debugger",
                "PolicyService-update",
                "DBWorker-update",
                "DBCleaner-service",
                "SwitchWorker",
                "gunicorn",
                "Validator-update",
            ],
            1,
        )
        self._writeToDB("hostnamemem-fe", self.memdisk.getMemMonitor())

    def getDiskStats(self):
        """Get Disk Statistics"""
        self.memdisk.reset()
        self.memdisk.updateStorageInfo()
        self._writeToDB("hostnamedisk-fe", self.memdisk.getStorageInfo())

    def startwork(self):
        """Scan all switches and get snmp data"""
        self._start()
        macs = {}
        for host in self.switches:
            self._getSNMPSession(host)
            if not self.session:
                continue
            self.runcount += 1  # Run count increment for each switch, as we need to track warnings per switch
            out = {}
            self._getMacAddrSession(host, macs)
            for key in self.config["MAIN"]["snmp"]["mibs"]:
                allvals = self._getSNMPVals(key, host)
                if len(self.lastrunwarnings) > 3:
                    self.logger.error(f"[{host}]: Too many SNMP errors ({self.lastrunwarnings}), skipping further SNMP queries")
                    break
                for item in allvals:
                    indx = item.oid_index
                    out.setdefault(indx, {})
                    out[indx][key] = item.value.replace("\x00", "")
            out["macs"] = macs[host]
            self._writeToDB(host, out)
        self.logger.info(f"[{self.sitename}]: SNMP Monitoring finished for {len(self.switches)} switches")
        # Get Memory and Disk Statistics
        self.getMemStats()
        self.logger.info(f"[{self.sitename}]: Memory statistics written to DB")
        self.getDiskStats()
        self.logger.info(f"[{self.sitename}]: Disk statistics written to DB")
        # Set Prometheus output
        self.prom.metrics()
        # Set Topology json
        self.topo.gettopology()
        self.logger.info(f"[{self.sitename}]: Topology map written to DB")


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args and len(args) > 1:
        snmpmon = SNMPMonitoring(config, args[1])
        snmpmon.startwork()
    else:
        sitename = getSiteNameFromConfig(config)
        snmpmon = SNMPMonitoring(config, sitename)
        snmpmon.startwork()


if __name__ == "__main__":
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    print("1st argument has to be sitename which is configured in this frontend")
    print(sys.argv)
    getLoggingObject(logType="StreamLogger", service="SNMPMonitoring")
    execute(args=sys.argv)
