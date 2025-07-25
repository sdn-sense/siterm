#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Everything goes here when they do not fit anywhere else.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/01/20
"""
import copy
import os
import os.path
import time

from SiteRMLibs.CustomExceptions import NoOptionError, NoSectionError

# Custom exceptions imports
from SiteRMLibs.MainUtilities import generateMD5, getHostname
from yaml import safe_load as yload


class GitConfig:
    """Git based configuration class."""

    def __init__(self):
        self.config = {}
        self.defaults = {
            "SITENAME": {"optional": False},
            "GIT_REPO": {"optional": True, "default": "sdn-sense/rm-configs"},
            "GIT_URL": {
                "optional": True,
                "default": "https://raw.githubusercontent.com/",
            },
            "GIT_BRANCH": {"optional": True, "default": "master"},
            "MD5": {"optional": True, "default": generateMD5(getHostname())},
        }

    @staticmethod
    def gitConfigCache(name, raiseEx=False):
        """Get Config file from tmp dir"""
        filename = f"/tmp/siterm-link-{name}.yaml"
        output = {}
        retries = 3
        while retries > 0:
            if os.path.isfile(filename):
                with open(filename, "r", encoding="utf-8") as fd:
                    output = yload(fd.read())
                break
            if retries < 0 and raiseEx:
                raise Exception(f"Config file {filename} does not exist.")
            retries -= 1
            time.sleep(5)
        return output

    def getFullGitUrl(self, customAdds=None):
        """Get Full Git URL."""
        urlJoinList = [
            self.config["GIT_URL"],
            self.config["GIT_REPO"],
            self.config["GIT_BRANCH"],
            self.config["SITENAME"],
        ]
        if customAdds:
            for item in customAdds:
                urlJoinList.append(item)
        return "/".join(urlJoinList)

    def getLocalConfig(self):
        """Get local config for info where all configs are kept in git."""
        if not os.path.isfile("/etc/siterm.yaml"):
            print("Config file /etc/siterm.yaml does not exist.")
            raise Exception("Config file /etc/siterm.yaml does not exist.")
        with open("/etc/siterm.yaml", "r", encoding="utf-8") as fd:
            self.config = yload(fd.read())
        for key, requirement in list(self.defaults.items()):
            if key not in list(self.config.keys()):
                # Check if it is optional or not;
                if not requirement["optional"]:
                    print(
                        "Configuration /etc/siterm.yaml missing non optional config parameter %s",
                        key,
                    )
                    raise Exception(f"Configuration /etc/siterm.yaml missing non optional config parameter {key}")
                self.config[key] = requirement["default"]

    def __addDefaults(self, defaults):
        """Add default config parameters"""
        for key1, val1 in defaults.items():
            self.config.setdefault(key1, {})
            for key2, val2 in val1.items():
                self.config[key1].setdefault(key2, {})
                for key3, val3 in val2.items():
                    self.config[key1][key2].setdefault(key3, val3)

    def __addSiteDefaults(self, defaults):
        """Add default site config parameters"""
        for sitename in self.config.get("MAIN", {}).get("general", {}).get("sites", []):
            if sitename not in self.config["MAIN"]:
                raise Exception(f"Site {sitename} is not available in configuration. Will not start services")
            self.config["MAIN"][sitename].setdefault("default_params", {})
            for key1, val1 in defaults["default_params"].items():
                self.config["MAIN"][sitename]["default_params"].setdefault(key1, {})
                for key2, val2 in val1.items():
                    self.config["MAIN"][sitename]["default_params"][key1].setdefault(key2, val2)

    def __addSwitchDefaults(self, defaults):
        """Add default switch config parameters"""
        for sitename in self.config.get("MAIN", {}).get("general", {}).get("sites", []):
            for switch in self.config["MAIN"][sitename].get("switch", []):
                for key1, val1 in defaults.items():
                    self.config["MAIN"].setdefault(switch, {})
                    self.config["MAIN"][switch].setdefault(key1, {})
                    if isinstance(val1, dict):
                        for key2, val2 in val1.items():
                            self.config["MAIN"][switch][key1].setdefault(key2, val2)
                    else:
                        self.config["MAIN"][switch][key1] = val1

    def presetAgentDefaultConfigs(self):
        """Preset default config parameters for Agent"""
        defConfig = {
            "MAIN": {
                "general": {
                    "logDir": "/var/log/siterm-agent/",
                    "logLevel": "INFO",
                    "privatedir": "/opt/siterm/config/",
                },
                "agent": {
                    "norules": False,
                    "rsts_enabled": "ipv4,ipv6",
                    "noqos": False,
                },
                "qos": {
                    "policy": "default-not-set",
                    "qos_params": "mtu 9000 mpu 9000 quantum 200000 burst 300000 cburst 300000 qdisc sfq balanced",
                    "class_max": True,
                    "interfaces": [],
                },
            }
        }
        self.__addDefaults(defConfig)
        self.__generatevlaniplists()

    def __generatevlaniplists(self):
        """Generate list for vlans and ips. config might have it in str"""
        for key, _ in list(self.config["MAIN"].items()):
            for subkey, subval in list(self.config["MAIN"][key].items()):
                self.generateIPList(key, subkey, subval)
                self.generateVlanList(key, subkey, subval)

    def getGitAgentConfig(self):
        """Get Git Agent Config."""
        if self.config["MAPPING"]["type"] == "Agent":
            self.config["MAIN"] = self.gitConfigCache("Agent-main")
            self.presetAgentDefaultConfigs()

    @staticmethod
    def __genValFromItem(inVal):
        """Generate int value from vlan range item"""
        if isinstance(inVal, int):
            return [inVal]
        retVals = []
        tmpvals = inVal.split("-")
        if len(tmpvals) == 2:
            # Need to loop as it is range;
            # In case second val is bigger than 1st - raise Exception
            if int(tmpvals[0]) >= int(tmpvals[1]):
                raise Exception(f"Configuration Error. Vlan Range equal or lower. Vals: {tmpvals}")
            for i in range(int(tmpvals[0]), int(tmpvals[1]) + 1):
                retVals.append(i)
        else:
            retVals.append(int(tmpvals[0]))
        return retVals

    def __genVlansRange(self, vals):
        """Generate Vlans Range"""
        retVals = []
        tmpVals = vals
        if isinstance(vals, int):
            return [vals]
        if not isinstance(vals, list):
            tmpVals = vals.split(",")
        for val in tmpVals:
            for lval in self.__genValFromItem(val):
                retVals.append(int(lval))
        return list(set(retVals))

    def generateVlanList(self, key1, key2, _vals):
        """Generate Vlan List. which can be separated by comma, dash"""

        def _addToAll(vlanlist):
            """Add to all vlan list"""
            self.config["MAIN"][key1].setdefault("all_vlan_range_list", [])
            for vlanid in vlanlist:
                if vlanid not in self.config["MAIN"][key1].get("all_vlan_range_list", []):
                    self.config["MAIN"][key1].setdefault("all_vlan_range_list", []).append(vlanid)

        # Default list is a must! Will be done checked at config preparation/validation
        if "vlan_range" not in self.config["MAIN"][key1]:
            return
        if "vlan_range_list" not in self.config["MAIN"][key1]:
            newvlanlist = self.__genVlansRange(self.config["MAIN"][key1]["vlan_range"])
            self.config["MAIN"][key1]["vlan_range_list"] = newvlanlist
            _addToAll(newvlanlist)
        if key2 == "ports":
            for portname, portvals in self.config["MAIN"][key1][key2].items():
                if "vlan_range" in portvals:
                    newvlanlist = self.__genVlansRange(portvals["vlan_range"])
                    self.config["MAIN"][key1][key2][portname]["vlan_range_list"] = newvlanlist
                    _addToAll(newvlanlist)
                # Else we set default
                else:
                    self.config["MAIN"][key1][key2][portname]["vlan_range"] = self.config["MAIN"][key1]["vlan_range"]
                    self.config["MAIN"][key1][key2][portname]["vlan_range_list"] = self.config["MAIN"][key1]["vlan_range_list"]

    def generateIPList(self, key1, key2, vals):
        """Split by command and return list"""
        if key2 in [
            "ipv4-address-pool",
            "ipv6-address-pool",
            "ipv4-subnet-pool",
            "ipv6-subnet-pool",
        ]:
            if isinstance(vals, list) and vals:
                self.config["MAIN"][key1][f"{key2}-list"] = vals
                self.config["MAIN"][key1][key2] = ",".join(vals)
            else:
                vals = list(set(list(filter(None, vals.split(",")))))
                self.config["MAIN"][key1][f"{key2}-list"] = vals

    def presetFEDefaultConfigs(self):
        """Preset default config parameters for FE"""
        defConfig = {
            "MAIN": {
                "general": {
                    "logDir": "/var/log/siterm-site-fe/",
                    "logLevel": "INFO",
                    "privatedir": "/opt/siterm/config/",
                },
                "ansible": {
                    "private_data_dir": "/opt/siterm/config/ansible/sense/",
                    "inventory": "/opt/siterm/config/ansible/sense/inventory/inventory.yaml",
                    "inventory_host_vars_dir": "/opt/siterm/config/ansible/sense/inventory/host_vars/",
                    "rotate_artifacts": 100,
                    "ignore_logging": False,
                    "verbosity": 0,
                    "debug": False,
                    "private_data_dir_singleapply": "/opt/siterm/config/ansible/sense/",
                    "inventory_singleapply": "/opt/siterm/config/ansible/sense/inventory_singleapply/inventory.yaml",
                    "inventory_host_vars_dir_singleapply": "/opt/siterm/config/ansible/sense/inventory_singleapply/host_vars/",
                    "rotate_artifacts_singleapply": 100,
                    "ignore_logging_singleapply": False,
                    "verbosity_singleapply": 0,
                    "debug_singleapply": False,
                    "private_data_dir_debug": "/opt/siterm/config/ansible/sense/",
                    "inventory_debug": "/opt/siterm/config/ansible/sense/inventory_debug/inventory.yaml",
                    "inventory_host_vars_dir_debug": "/opt/siterm/config/ansible/sense/inventory_debug/host_vars/",
                    "rotate_artifacts_debug": 100,
                    "ignore_logging_debug": False,
                    "verbosity_debug": 0,
                    "debug_debug": False,
                },
                "debuggers": {
                    "iperf-server": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True, "port": 5201},
                    },
                    "iperf-client": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "minstreams": 1,
                        "maxstreams": 16,
                        "defaults": {"onetime": True, "streams": 1},
                    },
                    "fdt-client": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "minstreams": 1,
                        "maxstreams": 16,
                        "defaults": {"onetime": True, "streams": 1},
                    },
                    "fdt-server": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True, "port": 54321},
                    },
                    "rapid-ping": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "maxmtu": 9000,
                        "mininterval": 0.2,
                        "maxtimeout": 30,
                    },
                    "rapid-pingnet": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "maxtimeout": 30,
                        "maxcount": 100,
                        "defaults": {"onetime": True},
                    },
                    "arp-table": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True},
                    },
                    "tcpdump": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True},
                    },
                    "traceroute": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True},
                    },
                    "traceroutenet": {
                        "defruntime": 600,
                        "maxruntime": 86400,
                        "defaults": {"onetime": True},
                    },
                },
                "prefixes": {
                    "mrs": "http://schemas.ogf.org/mrs/2013/12/topology#",
                    "nml": "http://schemas.ogf.org/nml/2013/03/base#",
                    "owl": "http://www.w3.org/2002/07/owl#",
                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                    "schema": "http://schemas.ogf.org/nml/2012/10/ethernet",
                    "sd": "http://schemas.ogf.org/nsi/2013/12/services/definition#",
                    "site": "urn:ogf:network",
                    "xml": "http://www.w3.org/XML/1998/namespace#",
                    "xsd": "http://www.w3.org/2001/XMLSchema#",
                },
                "servicedefinitions": {
                    "debugip": "http://services.ogf.org/nsi/2019/08/descriptions/config-debug-ip",
                    "globalvlan": "http://services.ogf.org/nsi/2019/08/descriptions/global-vlan-exclusion",
                    "multipoint": "http://services.ogf.org/nsi/2018/06/descriptions/l2-mp-es",
                    "l3bgpmp": "http://services.ogf.org/nsi/2019/08/descriptions/l3-bgp-mp",
                },
                "snmp": {
                    "mibs": [
                        "ifDescr",
                        "ifType",
                        "ifMtu",
                        "ifAdminStatus",
                        "ifOperStatus",
                        "ifHighSpeed",
                        "ifAlias",
                        "ifHCInOctets",
                        "ifHCOutOctets",
                        "ifInDiscards",
                        "ifOutDiscards",
                        "ifInErrors",
                        "ifOutErrors",
                        "ifHCInUcastPkts",
                        "ifHCOutUcastPkts",
                        "ifHCInMulticastPkts",
                        "ifHCOutMulticastPkts",
                        "ifHCInBroadcastPkts",
                        "ifHCOutBroadcastPkts",
                    ]
                },
            }
        }
        siteDefaults = {
            "default_params": {
                "starttime": {
                    "seconds": 10,
                    "minutes": 0,
                    "hours": 0,
                    "days": 0,
                    "weeks": 0,
                    "months": 0,
                    "years": 0,
                },
                "endtime": {
                    "seconds": 0,
                    "minutes": 0,
                    "hours": 0,
                    "days": 0,
                    "weeks": 0,
                    "months": 3,
                    "years": 0,
                },
                "bw": {"type": "bestEffort", "unit": "mbps", "minCapacity": "100"},
            }
        }
        switchDefaults = {"qos_policy": {"default": 1, "bestEffort": 2, "softCapped": 4, "guaranteedCapped": 7}, "rate_limit": False}
        self.__addDefaults(defConfig)
        self.__addSiteDefaults(siteDefaults)
        self.__addSwitchDefaults(switchDefaults)
        # Generate list vals - not in a str format. Needed in delta checks
        self.__generatevlaniplists()

    def getGitFEConfig(self):
        """Get Git FE Config."""
        if self.config["MAPPING"]["type"] == "FE":
            self.config["MAIN"] = self.gitConfigCache("FE-main")
            self.config["AUTH"] = self.gitConfigCache("FE-auth")
            self.config["AUTH_RE"] = self.gitConfigCache("FE-auth-re", False)
            self.presetFEDefaultConfigs()

    def getGitConfig(self):
        """Get git config from configured github repo."""
        if not self.config:
            self.getLocalConfig()
        mapping = self.gitConfigCache("mapping")
        if self.config["MD5"] not in list(mapping.keys()):
            msg = f"Configuration is not available for this MD5 {self.config['MD5']} tag in GIT REPO {self.config['GIT_REPO']}"
            print(msg)
            raise Exception(msg)
        self.config["MAPPING"] = copy.deepcopy(mapping[self.config["MD5"]])
        self.getGitFEConfig()
        self.getGitAgentConfig()

    def __getitem__(self, item):
        """Subscripable item lookup"""
        if item in ["MAIN", "AUTH"]:
            return self.config[item]
        return self.config["MAIN"][item]

    def get(self, key, subkey, default=None):
        """Custom get from dictionary in a way like configparser"""
        try:
            if key not in self.config["MAIN"]:
                if default:
                    return default
                raise NoSectionError(f"{key} is not available in configuration.")
            if subkey not in self.config["MAIN"][key]:
                if default:
                    return default
                raise NoOptionError(f"{subkey} is not available under {key} section in configuration.")
            return self.config["MAIN"].get(key, {}).get(subkey, {})
        except AttributeError as ex:
            if default:
                return default
            raise ex

    def getraw(self, key):
        """Get RAW DICT of key"""
        return self.config.get(key, {})

    def getboolean(self, key, subkey):
        """Return boolean"""
        val = self.get(key, subkey)
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("yes", "true", "1")

    def getint(self, key, subkey):
        """Return int from config"""
        return int(self.get(key, subkey))

    def has_section(self, key):
        """Check if section available"""
        if self.config["MAIN"].get(key, {}):
            return True
        return False

    def has_option(self, key, subkey):
        """Check if option available"""
        if not self.config["MAIN"].get(key, {}):
            return False
        if subkey in self.config["MAIN"][key]:
            return True
        return False


def getGitConfig():
    """Wrapper before git config class. Returns dictionary."""
    gitConf = GitConfig()
    gitConf.getGitConfig()
    return gitConf
