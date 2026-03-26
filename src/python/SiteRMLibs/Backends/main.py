#!/usr/bin/env python3
# pylint: disable=C0301
"""
Main Switch class called by all modules.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""

import time

from SiteRMLibs.Backends.Ansible import Switch as Ansible
from SiteRMLibs.Backends.generalFunctions import (
    checkConfig,
    cleanupEmpty,
    getConfigParams,
    getValFromConfig,
)
from SiteRMLibs.Backends.NodeInfo import Node
from SiteRMLibs.Backends.Raw import Switch as Raw
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.MainUtilities import (
    evaldict,
    getDBConn,
    getLoggingObject,
    getSiteNameFromConfig,
    getUTCnow,
    jsondumps,
)


class Switch(Node):
    """Main Switch Class. It will load module based on config"""

    def __init__(self, config, site):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="SwitchBackends")
        self.site = site
        self.switches = {"output": {}}
        checkConfig(self.config, self.site)
        self.dbI = getDBConn("Switch", self)[self.site]
        self.warnings = []
        self.output = {
            "switches": {},
            "ports": {},
            "vlans": {},
            "routes": {},
            "lldp": {},
            "info": {},
            "portMapping": {},
            "nametomac": {},
            "mactable": {},
        }
        self.plugin = None
        if self.config[site]["plugin"] == "ansible":
            self.plugin = Ansible(self.config, self.site)
        elif self.config[site]["plugin"] == "raw":
            self.plugin = Raw(self.config, self.site)
        else:
            raise Exception(f"Plugin {self.config[site]['plugin']} is not supported. Contact Support")

    def getWarnings(self):
        """Get Warnings"""
        return self.warnings

    def mainCall(self, stateCall, inputDict, actionState):
        """Main caller function which calls specific state."""
        if stateCall == "activate":
            out = self.activate(inputDict, actionState)
        else:
            raise Exception(f"Unknown State {stateCall}")
        return out

    def _setDefaults(self, switchName):
        """Set Default vals inside output"""
        for key in self.output.keys():
            self.output[key].setdefault(switchName, {})

    def _cleanOutput(self):
        """Clean output"""
        self.warnings = []
        self.output = {
            "switches": {},
            "ports": {},
            "vlans": {},
            "routes": {},
            "lldp": {},
            "info": {},
            "portMapping": {},
            "nametomac": {},
            "mactable": {},
        }

    def deviceUpdate(self, site=None, device=None):
        """Update all devices information."""
        self.logger.info("Forcefully update all device information")
        sitename = getSiteNameFromConfig(self.config)
        if site and sitename != site:
            return
        for dev in self.config.get(sitename, "switch"):
            if device and dev != device:
                continue
            fname = f"{self.config.get(sitename, 'privatedir')}/SwitchWorker/{dev}.update"
            self.logger.info(f"Set Update flag for device {dev} {sitename}, {fname}")
            success = False
            while not success:
                try:
                    with open(fname, "w", encoding="utf-8") as fd:
                        fd.write(str(getUTCnow()))
                        success = True
                except OSError as ex:
                    self.logger.error(f"Got OS Error writing {fname}. {ex}")
                    time.sleep(1)

    def _delPortFromOut(self, switch, portname):
        """Delete Port from Output"""
        for key in self.output.keys():
            if switch in self.output[key] and portname in self.output[key][switch]:
                del self.output[key][switch][portname]

    @staticmethod
    def _notSwitchport(tmpData):
        """Check if port is not switchport"""
        if "switchport" not in tmpData:
            return True
        if tmpData["switchport"] not in ["yes", True, "true"]:
            return True
        return False

    def _getDBOut(self):
        """Get Database output of all switches configs for site"""
        self.switches = {"output": {}}
        tmp = self.dbI.get("switch", search=[["sitename", self.site]])
        for item in tmp:
            self.switches["output"][item["device"]] = evaldict(item["output"])
            self.switches["output"][item["device"]].setdefault("dbinfo", {})
            for key in item.keys():
                if key != "output":
                    self.switches["output"][item["device"]]["dbinfo"][key] = item[key]
        if not self.switches.get("output"):
            self.logger.debug("No switches in database.")

    @staticmethod
    def getSystemValidPortName(port):
        """Get Systematic port name. MRML expects it without spaces"""
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Also - sometimes lldp reports multiple quotes for interface name from ansible out
        return replaceSpecialSymbols(port)

    def _getPortMapping(self):
        """Get Port Mapping. Normalizing diff port representations"""
        for key in ["ports", "vlans"]:
            for switch, switchDict in self.output[key].items():
                if switch not in self.switches["output"]:
                    continue
                for portKey in switchDict.keys():
                    self.output["portMapping"].setdefault(switch, {})
                    realportname = switchDict.get(portKey, {}).get("realportname")
                    if not realportname:
                        continue
                    if portKey.startswith("Vlan") and switchDict.get(portKey, {}).get("value", {}):
                        # This is mainly a hack to list all possible options
                        # For vlan to interface mapping. Why? Ansible switches
                        # Return very differently vlans, like Vlan XXXX, VlanXXXX or vlanXXXX
                        # And we need to map this back with correct name to ansible for provisioning
                        vlankey = switchDict[portKey]["value"]
                        self.output["portMapping"][switch][f"Vlan {vlankey}"] = realportname
                        self.output["portMapping"][switch][f"Vlan{vlankey}"] = realportname
                        self.output["portMapping"][switch][f"vlan{vlankey}"] = realportname
                    else:
                        self.output["portMapping"][switch][portKey] = realportname
                        self.output["portMapping"][switch][self.getSystemValidPortName(realportname)] = realportname

    def getSwitchPort(self, switchName, portName):
        """Get Switch Port data"""
        return self.output.get("ports", {}).get(switchName, {}).get(portName, {})

    def getSwitchPortName(self, switchName, portName, vlanid=None):
        """Get Switch Port Name"""
        # Get the portName which is uses in Switch
        # as you can see in getSystemValidPortName -
        # Port name from Orchestrator will come modified.
        # We need a way to revert it back to systematic switch port name
        if vlanid:
            netOS = self.plugin.getAnsNetworkOS(switchName)
            if netOS in self.plugin.defVlans:
                return self.plugin.defVlans[netOS] % vlanid
        sysPort = self.output["portMapping"].get(switchName, {}).get(portName, "")
        if not sysPort:
            sysPort = portName
        return sysPort

    def getAnsibleParams(self, switchName):
        """Get additional ansible parameters from configuration"""
        return getConfigParams(self.config, switchName, self)[3]

    def getAllSwitches(self, switchName=None):
        """Get All Switches"""
        if switchName:
            return [switchName] if switchName in self.output["switches"] else []
        return self.output["switches"].keys()

    def getAllAllowedPorts(self, switchName):
        """Get All Allowed Ports for switch"""
        ports, _, portIgnore, _ = getConfigParams(self.config, switchName, self)
        return ports if not portIgnore else [x for x in ports if x not in portIgnore]

    def getPortMembers(self, switchName, portName):
        """Get Port Members"""
        return self.plugin.getPortMembers(self.switches["output"][switchName], portName)

    def _insertToDB(self, data):
        """Insert to database new switches data"""
        self._getDBOut()
        for switch, vals in data.items():
            if not vals:
                continue
            out = {
                "sitename": self.site,
                "device": switch,
                "updatedate": getUTCnow(),
                "output": jsondumps(vals),
                "error": "{}",
            }
            if switch not in self.switches["output"]:
                out["insertdate"] = getUTCnow()
                self.logger.debug(f"No switches {switch} in database. Calling add")
                self.dbI.insert("switch", [out])
            else:
                # Get ID from DB and update
                out["id"] = self.switches["output"][switch]["dbinfo"]["id"]
                self.logger.debug(f"Update switch {switch} in database.")
                self.dbI.update("switch", [out])
        self._getDBOut()

    def _insertErrToDB(self, err):
        """Insert Error from switch to database"""
        self._getDBOut()
        for switch, errmsg in err.items():
            out = {
                "sitename": self.site,
                "device": switch,
                "updatedate": getUTCnow(),
                "error": jsondumps(errmsg),
            }
            if switch not in self.switches["output"]:
                out["insertdate"] = getUTCnow()
                self.logger.debug(f"No switches {switch} in database. Calling to add error.")
                self.logger.debug(f"Error: {errmsg}")
                self.dbI.insert("switch_error", [out])
            else:
                # Get ID from DB and update
                out["id"] = self.switches["output"][switch]["dbinfo"]["id"]
                self.logger.debug(f"Update switch {switch} in database with error.")
                self.logger.debug(f"Error: {errmsg}")
                self.dbI.update("switch_error", [out])
        # Once updated, inserted. Update var from db
        self._getDBOut()

    def _addyamlInfoToPort(self, switch, portName, defVlans, out):
        """Add Yaml info to specific port"""
        for key, defval in {
            "hostname": "",
            "isAlias": "",
            "vlan_range_list": defVlans,
            "destport": "",
            "capacity": "",
            "granularity": "",
            "availableCapacity": "",
        }.items():
            tmpval = getValFromConfig(self.config, switch, portName, key)
            if not tmpval:
                if defval:
                    out[key] = defval
                continue
            out[key] = tmpval
            if key == "isAlias":
                spltAlias = tmpval.split(":")
                out["isAlias"] = out[key]
                out["destport"] = spltAlias[-1]
                out["hostname"] = spltAlias[-2]

    def _checkPortChannel(self, switch, port, portData):
        """Check if port is part of a port channel"""
        if not portData:
            return
        if portData.get("channel-member", ""):
            self.logger.debug(f"Port {switch}{port} have channel members: {portData['channel-member']}")
            for member in portData["channel-member"]:
                self.logger.debug(f"Port {switch}{port} channel member: {member}")
                # Get port data for the channel member
                memberData = self.plugin.getportdata(self.switches["output"][switch], member)
                if not memberData:
                    self.logger.debug(f"Channel member {member} data not found for port {switch}{port}")
                    continue
                if memberData.get("lineprotocol", "") != "up" or memberData.get("operstatus", "") not in ["up", "connected"]:
                    msg = f"Channel member {member} of port {switch}{port} is not up. Line protocol: {memberData.get('lineprotocol', '')}, Oper status: {memberData.get('operstatus', '')}"
                    self.logger.warning(msg)
                    self.warnings.append(msg)

    def _mergeYamlAndSwitch(self, switch):
        """Merge yaml and Switch Info. Yaml info overwrites
        any parameter in switch  configuration."""
        ports, defVlans, portsIgn, _ = getConfigParams(self.config, switch, self)
        if switch not in self.switches["output"]:
            return
        vlans = self.plugin.getvlans(self.switches["output"][switch])
        for port in list(list(ports) + list(vlans)):
            if port in portsIgn:
                self.logger.debug(f"Port {switch}{port} ignored. It is under site configuration to ignore this port")
                self._delPortFromOut(switch, port)
                continue
            tmpData = self.plugin.getportdata(self.switches["output"][switch], port)
            confPort = self.config.config["MAIN"].get(switch, {}).get("ports", {}).get(port, {})
            if not tmpData and confPort:
                # This port only defined in RM Config (fake switch port)
                self.output["ports"][switch].setdefault(port, confPort)
                continue
            if self._notSwitchport(tmpData) and port not in vlans and not port.lower().startswith("vlan"):
                warning = f"Warning. Port {switch}{port} not added into model. Its status not switchport. Ansible runner returned: {tmpData}."
                self.logger.debug(warning)
                # Only add warning if allports flag is False.
                if not self.config.config["MAIN"].get(switch, {}).get("allports", False):
                    self.warnings.append(warning)
                self._delPortFromOut(switch, port)
                continue
            # Do check for port Members
            self._checkPortChannel(switch, port, tmpData)
            if port in vlans:
                tmpData = self.plugin.getvlandata(self.switches["output"][switch], port)
                vlansDict = self.output["vlans"][switch].setdefault(port, tmpData)
                vlansDict["realportname"] = port
                vlansDict["value"] = self.plugin.getVlanKey(port)
                self._addyamlInfoToPort(switch, port, defVlans, vlansDict)
            else:
                portDict = self.output["ports"][switch].setdefault(port, tmpData)
                portDict["realportname"] = port
                self._addyamlInfoToPort(switch, port, defVlans, portDict)
                switchesDict = self.output["switches"][switch].setdefault(port, tmpData)
                switchesDict["realportname"] = port
                self._addyamlInfoToPort(switch, port, defVlans, switchesDict)
        # Add route information and lldp information to output dictionary

        self.output["info"][switch] = self.plugin.getfactvalues(self.switches["output"][switch], "ansible_net_info")
        self.output["routes"][switch]["ipv4"] = self.plugin.getfactvalues(self.switches["output"][switch], "ansible_net_ipv4")
        self.output["routes"][switch]["ipv6"] = self.plugin.getfactvalues(self.switches["output"][switch], "ansible_net_ipv6")
        self.output["lldp"][switch] = self.plugin.getfactvalues(self.switches["output"][switch], "ansible_net_lldp")
        self.output["nametomac"][switch] = self.plugin.nametomac(self.switches["output"][switch], switch)
        self.output["mactable"][switch] = self.plugin.getfactvalues(self.switches["output"][switch], "ansible_net_mactable")

    def getinfo(self):
        """Get info about Network Devices using database."""
        self._getDBOut()
        # Clean and prepare output which is returned to caller
        self._cleanOutput()
        switch = self.config.get(self.site, "switch")
        for switchn in switch:
            self._setDefaults(switchn)
            self._mergeYamlAndSwitch(switchn)
        self.output = cleanupEmpty(self.nodeinfo())
        self._getPortMapping()
        return self.output

    def getinfoNew(self, hosts=None):
        """Get information from network devices."""
        out, err = self.plugin._getFacts(hosts)
        if err:
            self._insertErrToDB(err)
            raise Exception(f"Failed ANSIBLE Runtime. See Error {str(err)}")
        self._insertToDB(out)


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    sitename = getSiteNameFromConfig(config)
    switchM = Switch(config, sitename)
    out = switchM.getinfo()
    print(out)


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="SwitchBackends")
    execute()
