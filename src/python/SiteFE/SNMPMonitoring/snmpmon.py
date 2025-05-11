#!/usr/bin/env python3
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
import os
import sys
import copy
import psutil
from easysnmp import Session
from easysnmp.exceptions import EasySNMPUnknownObjectIDError
from easysnmp.exceptions import EasySNMPTimeoutError
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import contentDB
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import jsondumps
from SiteRMLibs.MainUtilities import getStorageInfo
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.MainUtilities import getAllHosts
from SiteRMLibs.MainUtilities import getActiveDeltas
from SiteRMLibs.MainUtilities import isValFloat
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.GitConfig import getGitConfig
from prometheus_client import (CollectorRegistry, Enum,
                               Gauge, Info, generate_latest)


class Topology:
    """Topology json preparation for visualization"""
    # pylint: disable=E1101
    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service='SNMPMonitoring')
        self.dbI = getVal(getDBConn('SNMPMonitoring', self), **{'sitename': self.sitename})
        self.diragent = contentDB()
        self.topodir = os.path.join(self.config.get(sitename, "privatedir"), "Topology")

    @staticmethod
    def _findConnection(workdata, remMac):
        """Find connections based on MAC aaddress"""
        if not remMac:
            return None
        for switch, switchdata in workdata.items():
            if remMac in switchdata['macs']:
                return {'switch': switch, 'id': switchdata['id']}
        return None

    @staticmethod
    def _getansdata(indata, keys):
        """Get Ansible data from ansible output"""
        if len(keys) == 1:
            return indata.get('event_data', {}).get('res', {}).get(
                              'ansible_facts', {}).get(keys[0], {})
        if len(keys) == 2:
            return indata.get('event_data', {}).get('res', {}).get(
                              'ansible_facts', {}).get(keys[0], {}).get(keys[1], {})
        return {}

    def _getWANLinks(self, incr):
        """Get WAN Links for visualization"""
        wan_links = {}
        for site in self.config['MAIN'].get('general', {}).get('sites', []):
            for sw in self.config['MAIN'].get(site, {}).get('switch', []):
                if not self.config['MAIN'].get(sw, {}):
                    continue
                if not isinstance(self.config['MAIN'].get(sw, {}).get('ports', None), dict):
                    continue
                for _, val in self.config['MAIN'].get(sw, {}).get('ports', {}).items():
                    if 'wanlink' in val and val['wanlink'] and val.get('isAlias', None):
                        wan_links.setdefault(f"wan{incr}", {"_id": incr,
                                                            "topo": {},
                                                            "DeviceInfo": {"type": "cloud",
                                                                           "name": val['isAlias']}})
                        wan_links[f"wan{incr}"]["topo"].setdefault(val['isAlias'].split(':')[-1],
                                                                   {"device": sw, "port": val})
                        incr += 1
        return wan_links

    def gettopology(self):
        """Return all Switches information"""
        workdata = {}
        incr = 0
        # Get all Switch information
        for item in self.dbI.get('switch', orderby=['updatedate', 'DESC'], limit=100):
            if 'output' not in item:
                continue
            tmpdict = evaldict(item['output'])
            workdata[item['device']] = {'id': incr, 'type': 'switch'}
            incr += 1
            for dkey, keys in {'macs': ['ansible_net_info', 'macs'],
                               'lldp': ['ansible_net_lldp'],
                               'intstats': ['ansible_net_interfaces']}.items():
                workdata[item['device']][dkey] = self._getansdata(tmpdict, keys)
        # Now that we have specific data; lets loop over it and get nodes/links
        out = {}
        for switch, switchdata in workdata.items():
            swout = out.setdefault(switch, {'topo': {},
                                            'DeviceInfo': {'type': 'switch', 'name': switch},
                                            '_id': switchdata['id']})
            for key, vals in switchdata['lldp'].items():
                remSwitch = self._findConnection(workdata, vals.get('remote_chassis_id', ""))
                remPort = vals.get('remote_port_id', "")
                if remSwitch and remPort:
                    swout['topo'].setdefault(key, {'device': remSwitch['switch'],
                                                   'port': remPort})
        # Now lets get host information
        for host in self.dbI.get('hosts', orderby=['updatedate', 'DESC'], limit=100):
            parsedInfo = self.diragent.getFileContentAsJson(host.get('hostinfo', ""))
            hostconfig = parsedInfo.get('Summary', {}).get('config', {})
            hostname = hostconfig.get('agent', {}).get('hostname', '')
            lldpInfo = parsedInfo.get('NetInfo', {}).get('lldp', {})
            hout = out.setdefault(hostname, {'topo': {},
                                             'DeviceInfo': {'type': 'server', 'name': hostname, },
                                             '_id': incr})
            incr += 1
            if lldpInfo:
                for intf, vals in lldpInfo.items():
                    remSwitch = self._findConnection(workdata, vals.get('remote_chassis_id', ""))
                    remPort = vals.get('remote_port_id', "")
                    if remSwitch and remPort:
                        hout['topo'].setdefault(intf, {'device': remSwitch['switch'],
                                                       'port': remPort})
            else:
                for intf in hostconfig.get('agent', {}).get('interfaces', []):
                    swintf = hostconfig.get(intf, {}).get('port', '')
                    switch = hostconfig.get(intf, {}).get('switch', '')
                    if switch and swintf:
                        hout['topo'].setdefault(intf, {'device': switch, 'port': swintf})
        out.update(self._getWANLinks(incr))
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
        for key in ["vsw", "rst", "kube", "singleport"]:
            self._loopActKey(key, out)
        result = copy.deepcopy(self.reports)
        self.__clean()
        return result

class PromOut():
    """Prometheus Output Class"""
    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service='SNMPMonitoring')
        self.dbI = getVal(getDBConn('SNMPMonitoring', self), **{'sitename': self.sitename})
        self.diragent = contentDB()
        self.timenow = int(getUTCnow())
        self.activeAPI = ActiveWrapper()
        self.memMonitor = {}
        self.diskMonitor = {}
        self.arpLabels = {'Device': '', 'Flags': '', 'HWaddress': '',
                          'IPaddress': '', 'Hostname': ''}
        self.snmpdir = os.path.join(self.config.get(sitename, "privatedir"), "SNMPData")

    @staticmethod
    def __cleanRegistry():
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __refreshTimeNow(self):
        """Refresh timenow"""
        self.timenow = int(getUTCnow())

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
            hostDict["hostinfo"] = self.diragent.getFileContentAsJson(hostDict["hostinfo"])
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
            states=[
                "activating",
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
            # pylint: disable=E1101
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
            # pylint: disable=E1101
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
        self.__refreshTimeNow()
        registry = self.__cleanRegistry()
        self.__getServiceStates(registry)
        data = generate_latest(registry)
        del registry # Explicit dereference of Collector Registry
        fname = os.path.join(self.snmpdir, "snmpinfo.txt")
        self.diragent.dumpFileContent(fname, data)


class SNMPMonitoring():
    """SNMP Monitoring Class"""
    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='SNMPMonitoring')
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn('SNMPMonitoring', self), **{'sitename': self.sitename})
        self.diragent = contentDB()
        self.switches = {}
        self.session = None
        self.prom = PromOut(config, sitename)
        self.topo = Topology(config, sitename)
        self.err = []
        self.hostconf = {}
        self.memMonitor = {}

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)

    def _start(self):
        self.switch.getinfo()
        self.switches = self.switch.getAllSwitches()

    def _getSNMPSession(self, host):
        self.session = None
        self.hostconf.setdefault(host, {})
        self.hostconf[host] = self.switch.plugin.getHostConfig(host)
        if self.config.config['MAIN'].get(host, {}).get('external_snmp', ''):
            snmphost = self.config.config['MAIN'][host]['external_snmp']
            self.logger.info(f'SNMP Scan skipped for {host}. Remote endpoint defined: {snmphost}')
            return
        if 'snmp_monitoring' not in self.hostconf[host]:
            self.logger.info(f'Ansible host: {host} config does not have snmp_monitoring parameters')
            return
        if 'session_vars' not in self.hostconf[host]['snmp_monitoring']:
            self.logger.info(f'Ansible host: {host} config does not have session_vars parameters')
            return
        # easysnmp does not support ipv6 and will fail with ValueError (unable to unpack)
        # To avoid this, we will bypass ipv6 check if error is raised.
        try:
            self.session = Session(**self.hostconf[host]['snmp_monitoring']['session_vars'])
        except ValueError:
            conf = self.hostconf[host]['snmp_monitoring']['session_vars']
            hostname = conf.pop('hostname')
            self.session = Session(**conf)
            self.session.update_session(hostname=hostname)


    def _getSNMPVals(self, key, host=None):
        try:
            allvals = self.session.walk(key)
            return allvals
        except EasySNMPUnknownObjectIDError as ex:
            ex = f'[{host}]: Got SNMP UnknownObjectID Exception for key {key}: {ex}'
            self.logger.warning(ex)
            self.err.append(ex)
        except EasySNMPTimeoutError as ex:
            ex = f'[{host}]: Got SNMP Timeout Exception: {ex}'
            self.logger.warning(ex)
            self.err.append(ex)
        return []

    def _junosmac(self, host, macs):
        """Junos Mac Parser (custom as it requires to get multiple values)"""
        # Junos uses ansible to get mac addresses
        # mainly because SNMP not always returns vlan id associated with mac address
        # There might be some MIBs/oids which can be used to get this information
        # for now, we will use ansible to get mac addresses (as enabling more features
        # at sites - might be more complex)
        updatedate = self.switch.switches.get('output', {}).get(host, {}).get('dbinfo', {}).get('updatedate', 0)
        if (getUTCnow() - updatedate) > 600:
            self.logger.info(f'[{host}]: Forcing ansible to update device information')
            self.switch.deviceUpdate(self.sitename, host)
        self.switch.getinfo()
        mactable = self.switch.output.get('mactable', {}).get(host, {})
        macs.setdefault(host, {'vlans': {}})
        for vlanid, allmacs in mactable.items():
            if not self._isVlanAllowed(host, vlanid):
                continue
            macs[host]['vlans'].setdefault(vlanid, [])
            for mac in allmacs:
                macs[host]['vlans'][vlanid].append(mac)


    def _writeToDB(self, host, output):
        """Write SNMP Data to DB"""
        out = {'insertdate': getUTCnow(), 'updatedate': getUTCnow(),
               'hostname': host, 'output': jsondumps(output)}
        dbOut = self.dbI.get('snmpmon', limit=1, search=[['hostname', host]])
        if dbOut:
            out['id'] = dbOut[0]['id']
            self.dbI.update('snmpmon', [out])
        else:
            self.dbI.insert('snmpmon', [out])

    def _isVlanAllowed(self, host, vlan):
        try:
            if int(vlan) in self.config.get(host, 'vlan_range_list'):
                return True
        except Exception:
            return False
        return False

    def _getMacAddrSession(self, host, macs):
        if not self.session:
            return
        if self.hostconf[host].get('ansible_network_os', 'undefined') == 'sense.junos.junos':
            self._junosmac(host, macs)
            return
        macs.setdefault(host, {'vlans': {}})
        if 'mac_parser' in self.hostconf[host]['snmp_monitoring']:
            oid = self.hostconf[host]['snmp_monitoring']['mac_parser']['oid']
            mib = self.hostconf[host]['snmp_monitoring']['mac_parser']['mib']
            allvals = self._getSNMPVals(oid, host)
            for item in allvals:
                splt = item.oid[(len(mib)):].split('.')
                vlan = splt.pop(0)
                mac = [format(int(x), '02x') for x in splt]
                if self._isVlanAllowed(host, vlan):
                    macs[host]['vlans'].setdefault(vlan, [])
                    macs[host]['vlans'][vlan].append(":".join(mac))

    def _processStats(self, proc, services, lookupid):
        """Get Process Stats - memory"""
        procList = proc.cmdline()
        if len(procList) > lookupid:
            for serviceName in services:
                if procList[lookupid].endswith(serviceName):
                    self.memMonitor.setdefault(
                        serviceName,
                        {"rss": 0, "vms": 0, "shared": 0, "text": 0,
                         "lib": 0, "data": 0, "dirty": 0})
                    for key in self.memMonitor[serviceName].keys():
                        if hasattr(proc.memory_info(), key):
                            self.memMonitor[serviceName][key] += getattr(
                                proc.memory_info(), key)

    def getMemStats(self):
        """Refresh all Memory Statistics in FE"""

        def procWrapper(proc, services, lookupid):
            """Process Wrapper to catch exited process or zombie process"""
            try:
                self._processStats(proc, services, lookupid)
            except psutil.NoSuchProcess:
                pass
            except psutil.ZombieProcess:
                pass

        self.memMonitor = {}
        for proc in psutil.process_iter(attrs=None, ad_value=None):
            procWrapper(proc, ["mariadbd", "httpd"], 0)
            procWrapper(proc, ["Config-Fetcher", "SNMPMonitoring-update",
                               "ProvisioningService-update", "LookUpService-update",
                               "siterm-debugger", "PolicyService-update",
                               "DBWorker-update", "DBCleaner-service",
                               "SwitchWorker", "gunicorn", "Validator-update"], 1)
        # Write to DB
        self._writeToDB('hostnamemem-fe', self.memMonitor)

    def getDiskStats(self):
        """Get Disk Statistics"""
        self._writeToDB('hostnamedisk-fe', getStorageInfo())

    def startwork(self):
        """Scan all switches and get snmp data"""
        self.err = []
        self._start()
        macs = {}
        for host in self.switches:
            self._getSNMPSession(host)
            if not self.session:
                continue
            out = {}
            self._getMacAddrSession(host, macs)
            for key in self.config['MAIN']['snmp']['mibs']:
                allvals = self._getSNMPVals(key, host)
                for item in allvals:
                    indx = item.oid_index
                    out.setdefault(indx, {})
                    out[indx][key] = item.value.replace('\x00', '')
            out['macs'] = macs[host]
            self._writeToDB(host, out)
        self.logger.info(f'[{self.sitename}]: SNMP Monitoring finished for {len(self.switches)} switches')
        self.getMemStats()
        self.logger.info(f'[{self.sitename}]: Memory statistics written to DB')
        self.getDiskStats()
        self.logger.info(f'[{self.sitename}]: Disk statistics written to DB')
        if self.err:
            raise Exception(f'SNMP Monitoring Errors: {self.err}')
        # We could do delete and re-init everytime, or at refresh.
        # Need to track memory usage and see what is best
        self.prom.metrics()
        # Get Topology json
        self.topo.gettopology()
        self.logger.info(f'[{self.sitename}]: Topology map written to DB')


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args and len(args) > 1:
        snmpmon = SNMPMonitoring(config, args[1])
        snmpmon.startwork()
    else:
        for sitename in config.get('general', 'sites'):
            snmpmon = SNMPMonitoring(config, sitename)
            snmpmon.startwork()


if __name__ == '__main__':
    print('WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:', len(sys.argv), 'arguments.')
    print('1st argument has to be sitename which is configured in this frontend')
    print(sys.argv)
    getLoggingObject(logType='StreamLogger', service='SNMPMonitoring')
    execute(args=sys.argv)
