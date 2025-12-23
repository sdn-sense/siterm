#!/usr/bin/env python3
# pylint: disable=W0613
"""
    Switch class of RAW Plugin.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""
import os

import yaml
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import createDirs


class Switch:
    """RAW Switch plugin. All info comes from yaml files."""

    def __init__(self, config, sitename):
        self.config = config
        self.sitename = sitename
        self.defVlans = []
        self.name = "RAW"
        self.workDir = os.path.join(
            self.config.get(sitename, "privatedir"), "RAW-Switch-Config/"
        )
        createDirs(self.workDir)

    @staticmethod
    def activate(_inputDict, _actionState):
        """Activating state actions."""
        return True

    def getAnsErrors(self, ansOut):
        """Get Ansible errors. Dummy Call for RAW"""
        return

    def _writeInventoryInfo(self, out, subitem=""):
        """Write Ansible Inventory file (used only in a single apply)"""
        return

    def _getInventoryInfo(self, hosts=None, subitem=""):
        """Get Inventory Info. If hosts specified, only return for specific hosts"""
        return

    def getHostConfig(self, host, subitem=""):
        """Get config of RAW local file."""
        out = {}
        confFName = f"{self.workDir}/{host}.yaml"
        if os.path.isfile(confFName):
            with open(confFName, "r", encoding="utf-8") as fd:
                out = yaml.safe_load(fd.read())
        return out

    def _writeHostConfig(self, host, out, subitem=""):
        """It saves locally all configuration.
        RAW plugin does not apply anything on switches."""
        confFName = f"{self.workDir}/{host}.yaml"
        with open(confFName, "w", encoding="utf-8") as fd:
            fd.write(yaml.dump(out))

    @staticmethod
    def _applyNewConfig(hosts=None, subitem=""):
        """RAW Plugin does not apply anything."""
        return {}, {}

    @staticmethod
    def _executeAnsible(playbook, hosts=None, subitem=""):
        """Execute Ansible playbook. RAW Does nothing"""
        return None

    def getAnsNetworkOS(self, host, subitem=""):
        """Get Ansible network o`s from hosts file"""
        return self.getHostConfig(host).get("ansible_network_os", "")

    def _getFacts(self, hosts=None, subitem=""):
        """Get Facts for RAW plugin"""
        self.config = getGitConfig()
        out = {}
        for switchn in self.config.get(self.sitename, "switch"):
            hOut = out.setdefault(switchn, {})
            for port in self.config.get(switchn, "ports"):
                portOut = (
                    hOut.setdefault("event_data", {})
                    .setdefault("res", {})
                    .setdefault("ansible_facts", {})
                    .setdefault("ansible_net_interfaces", {})
                )
                portOut[port] = {}
        return out, {}

    @staticmethod
    def getports(inData):
        """Get ports from ansible output"""
        return inData["event_data"]["res"]["ansible_facts"][
            "ansible_net_interfaces"
        ].keys()

    @staticmethod
    def getPortMembers(inData, port):
        """RAW device does not support port members"""
        return []

    @staticmethod
    def getportdata(inData, port):
        """Get port data from output"""
        # In RAW plugin - there is no data on port details
        return {"switchport": "yes"}

    @staticmethod
    def getvlans(inData):
        """Get vlans from output"""
        # In RAW plugin - there is no vlans
        return []

    @staticmethod
    def getfactvalues(inData, key):
        """Get custom command output from ansible output, like routing, lldp, mac"""
        # In RAW plugin - this does not exists and returns empty
        return inData["event_data"]["res"]["ansible_facts"].get(key, {})

    def getvlandata(self, inData, vlan):
        """Get vlan data from ansible output"""
        return self.getportdata(inData, vlan)

    @staticmethod
    def getVlanKey(port):
        """Get Vlan Key. Normalize betwen diff switches"""
        if port.startswith("Vlan_"):
            return int(port[5:])
        if port.startswith("Vlan "):
            return int(port[5:])
        if port.startswith("Vlan"):
            return int(port[4:])
        return port

    @staticmethod
    def nametomac(inData, key):
        """Return all mac's associated to that host. Not in use for RAW plugin"""
        return []
