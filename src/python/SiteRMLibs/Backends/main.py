#!/usr/bin/env python3
# pylint: disable=C0301
"""
Main Switch class called by all modules.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from SiteRMLibs.Backends.Ansible import Switch as Ansible
from SiteRMLibs.Backends.generalFunctions import (checkConfig, cleanupEmpty,
                                                  getConfigParams,
                                                  getValFromConfig)
from SiteRMLibs.Backends.NodeInfo import Node
from SiteRMLibs.Backends.Raw import Switch as Raw
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (evaldict, getDBConn, getLoggingObject, getUTCnow, jsondumps)


class Switch(Node):
    """Main Switch Class. It will load module based on config"""

    def __init__(self, config, site):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="SwitchBackends")
        self.site = site
        self.switches = {}
        checkConfig(self.config, self.site)
        self.dbI = getDBConn("Switch", self)[self.site]
        self.output = {
            "switches": {},
            "ports": {},
            "vlans": {},
            "routes": {},
            "lldp": {},
            "info": {},
            "portMapping": {},
            "nametomac": {},
        }
        self.plugin = None
        if self.config[site]["plugin"] == "ansible":
            self.plugin = Ansible(self.config, self.site)
        elif self.config[site]["plugin"] == "raw":
            self.plugin = Raw(self.config, self.site)
        else:
            raise Exception(
                f"Plugin {self.config[site]['plugin']} is not supported. Contact Support"
            )

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
        self.output = {
            "switches": {},
            "ports": {},
            "vlans": {},
            "routes": {},
            "lldp": {},
            "info": {},
            "portMapping": {},
            "nametomac": {},
        }

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
        if tmpData["switchport"] != "yes":
            return True
        return False

    def _getDBOut(self):
        """Get Database output of all switches configs for site"""
        tmp = self.dbI.get("switches", limit=1, search=[["sitename", self.site]])
        if tmp:
            self.switches = tmp[0]
            self.switches["output"] = evaldict(self.switches["output"])
        if not self.switches:
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
                    realportname = switchDict.get(portKey, {}).get("realportname", None)
                    if not realportname:
                        continue
                    if portKey.startswith("Vlan") and switchDict.get(portKey, {}).get(
                        "value", {}
                    ):
                        # This is mainly a hack to list all possible options
                        # For vlan to interface mapping. Why? Ansible switches
                        # Return very differently vlans, like Vlan XXXX, VlanXXXX or vlanXXXX
                        # And we need to map this back with correct name to ansible for provisioning
                        vlankey = switchDict[portKey]["value"]
                        self.output["portMapping"][switch][
                            f"Vlan {vlankey}"
                        ] = realportname
                        self.output["portMapping"][switch][
                            f"Vlan{vlankey}"
                        ] = realportname
                        self.output["portMapping"][switch][
                            f"vlan{vlankey}"
                        ] = realportname
                    else:
                        self.output["portMapping"][switch][portKey] = realportname
                        self.output["portMapping"][switch][
                            self.getSystemValidPortName(realportname)
                        ] = realportname

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

    def getAllSwitches(self, switchName=None):
        """Get All Switches"""
        if switchName:
            return [switchName] if switchName in self.output["switches"] else []
        return self.output["switches"].keys()

    def _insertToDB(self, data):
        """Insert to database new switches data"""
        self._getDBOut()
        out = {
            "sitename": self.site,
            "updatedate": getUTCnow(),
            "output": jsondumps(data),
            "error": "{}",
        }
        if not self.switches:
            out["insertdate"] = getUTCnow()
            self.logger.debug("No switches in database. Calling add")
            self.dbI.insert("switches", [out])
        else:
            out["id"] = self.switches["id"]
            self.logger.debug("Update switches in database.")
            self.dbI.update("switches", [out])
        # Once updated, inserted. Update var from db
        self._getDBOut()

    def _insertErrToDB(self, err):
        """Insert Error from switch to database"""
        self._getDBOut()
        out = {
            "sitename": self.site,
            "updatedate": getUTCnow(),
            "error": jsondumps(err),
        }
        if self.switches:
            out["id"] = self.switches["id"]
            self.logger.debug("Update switches in database.")
            self.dbI.update("switches_error", [out])
        else:
            self.logger.info("No switches in DB. Will not update errors in database.")
        # Once updated, inserted. Update var from db
        self._getDBOut()

    def _addyamlInfoToPort(self, switch, portName, defVlans, out):
        """Add Yaml info to specific port"""
        for key, defval in {"hostname": "",
                            "isAlias": "",
                            "vlan_range_list": defVlans,
                            "desttype": "",
                            "destport": "",
                            "capacity": "",
                            "granularity": "",
                            "availableCapacity": "",
                            "rate_limit": False}.items():
            tmpval = getValFromConfig(self.config, switch, portName, key)
            if not tmpval:
                if defval:
                    out[key] = defval
                continue
            out[key] = tmpval
            if key == "isAlias":
                spltAlias = tmpval.split(":")
                out["isAlias"] = out[key]
                out["desttype"] = "switch"
                out["destport"] = spltAlias[-1]
                out["hostname"] = spltAlias[-2]

    def _mergeYamlAndSwitch(self, switch):
        """Merge yaml and Switch Info. Yaml info overwrites
        any parameter in switch  configuration."""
        ports, defVlans, portsIgn = getConfigParams(self.config, switch, self)
        if switch not in self.switches["output"]:
            return
        vlans = self.plugin.getvlans(self.switches["output"][switch])
        for port in list(list(ports) + list(vlans)):
            if port in portsIgn:
                self.logger.debug(
                    f"Port {switch}{port} ignored. It is under site configuration to ignore this port"
                )
                self._delPortFromOut(switch, port)
                continue
            tmpData = self.plugin.getportdata(self.switches["output"][switch], port)
            confPort = self.config.config["MAIN"].get(switch, {}).get("ports", {}).get(port, {})
            if self._notSwitchport(tmpData) and confPort:
                # This port only defined in RM Config (fake switch port)
                portDict = self.output["ports"][switch].setdefault(port, confPort)
                continue
            elif self._notSwitchport(tmpData) and port not in vlans:
                self.logger.debug(
                    f"Warning. Port {switch}{port} not added into model. Its status not switchport."
                )
                self._delPortFromOut(switch, port)
                continue
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
                # if destType not defined, check if switchport available in switch config.
                # Then set it to switch
                if "switchport" in portDict.keys() and portDict["switchport"]:
                    portDict["desttype"] = "switch"
        # Add route information and lldp information to output dictionary

        self.output["info"][switch] = self.plugin.getfactvalues(
            self.switches["output"][switch], "ansible_net_info"
        )
        self.output["routes"][switch]["ipv4"] = self.plugin.getfactvalues(
            self.switches["output"][switch], "ansible_net_ipv4"
        )
        self.output["routes"][switch]["ipv6"] = self.plugin.getfactvalues(
            self.switches["output"][switch], "ansible_net_ipv6"
        )
        self.output["lldp"][switch] = self.plugin.getfactvalues(
            self.switches["output"][switch], "ansible_net_lldp"
        )
        self.output["nametomac"][switch] = self.plugin.nametomac(
            self.switches["output"][switch], switch
        )

    def getinfo(self, renew=False, hosts=None):
        """Get info about Network Devices using plugin defined in configuration."""
        # If renew or switches var empty - get latest
        # And update in DB
        out, err = {}, {}
        if renew or not self.switches:
            out, err = self.plugin._getFacts(hosts)
            if err:
                self._insertErrToDB(err)
                raise Exception(f"Failed ANSIBLE Runtime. See Error {str(err)}")
            self._insertToDB(out)
        self._getDBOut()
        # Clean and prepare output which is returned to caller
        self._cleanOutput()
        switch = self.config.get(self.site, "switch")
        for switchn in switch:
            if switchn in err:
                continue
            self._setDefaults(switchn)
            self._mergeYamlAndSwitch(switchn)
        self.output = cleanupEmpty(self.nodeinfo())
        self._getPortMapping()
        return self.output


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for siteName in config.get("general", "sites"):
        switchM = Switch(config, siteName)
        out = switchM.getinfo()
        print(out)


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="SwitchBackends")
    execute()
