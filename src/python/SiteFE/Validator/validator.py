#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Validator service to validate host and switch configurations and link mappings.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2025/04/21
"""
import os
import sys
import argparse

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.MainUtilities import (
    contentDB, createDirs,  getFileContentAsJson, getAllHosts,
    getDBConn, getLoggingObject, getVal, getUTCnow, getActiveDeltas)
from SiteRMLibs.GitConfig import getGitConfig


class Validator():
    """Validate Switch and Host configurations and link mappings."""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="Validator")
        self.siteDB = contentDB()
        self.dbI = getVal(getDBConn("Validator", self), **{"sitename": self.sitename})
        self.switch = Switch(config, sitename)
        self.hosts = {}
        for siteName in self.config.get("general", "sites"):
            workDir = os.path.join(self.config.get(siteName, "privatedir"), "Validator/")
            createDirs(workDir)
        self.switchInfo = {}
        self.activeDeltas = {}
        self.warnings = []
        self.warningstart = 0
        self.runcount = 0
        self.warningscounters = {}


    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)
        self.switchInfo = {}
        self.warnings = []
        self.warningstart = 0
        self.runcount = 0
        self.warningscounters = {}

    def _getMacAddress(self, nodeDict, interface):
        """Get MAC address from configuration."""
        for entry in nodeDict.get("hostinfo",{}).get('NetInfo', {}).get('interfaces', {}).get(interface, {}).get('17', []):
            if 'mac-address' in entry and entry['mac-address']:
                return entry['mac-address']
        return None

    def _allvaluesDefined(self, inval):
        """Check if all values are defined and not None"""
        for _key, value in inval.items():
            if not value:
                return False
        return True

    def _getHostInterfaces(self, nodeDict):
        """Get Host Interfaces from configuration."""
        return nodeDict.get("hostinfo", {}).get('Summary', {}).get('config', {}).get('agent', {}).get('interfaces', [])

    def _getSwitchInterface(self, nodeDict, interface):
        """Get Switch Interface from configuration."""
        return nodeDict.get("hostinfo", {}).get('Summary', {}).get('config', {}).get(interface, {}).get('port', None)

    def _getSwitchName(self, nodeDict, interface):
        """Get Switch Name from configuration."""
        return nodeDict.get("hostinfo", {}).get('Summary', {}).get('config', {}).get(interface, {}).get('switch', None)

    def getAllHostIntfMacs(self):
        """Get all host and intf mac info"""
        jOut = getAllHosts(self.dbI)
        for _nodeHostname, nodeDict in list(jOut.items()):
            nodeDict["hostinfo"] = getFileContentAsJson(nodeDict["hostinfo"])
            # Get all interfaces in configuration and their mac addresses
            for intf in self._getHostInterfaces(nodeDict):
                hostcheck = {'hostname': nodeDict['hostname'], 'intf': intf}
                # Get mac address from configuration
                hostcheck['mac-address'] = self._getMacAddress(nodeDict, intf)
                # Get Switch
                hostcheck['switch'] = self._getSwitchName(nodeDict, intf)
                # Get Switch Port
                hostcheck['port'] = self._getSwitchInterface(nodeDict, intf)
                # Check if none of the values are None
                if self._allvaluesDefined(hostcheck):
                    yield hostcheck

    def _getSwitchLLDPInfo(self, hostcheck):
        """Get Switch LLDP Info for switch and port"""
        # TODO: Raise warnings if switch not available or port not available.
        # LLDP info is not required to provide, but useful for our debugging.
        return self.switchInfo.get('lldp', {}).get(hostcheck['switch'], {}).get(hostcheck['port'], {})

    def _validateHostSwitchInfo(self, hostinfo, switchlldp):
        """
        {'hostname': 'transfer-14.ultralight.org', 'intf': 'bondpublic', 'mac-address': 'b8:59:9f:ed:2a:fa', 'switch': 'dellos10_s1', 'port': 'Ethernet 1/1/2:5'}
{'local_port_id': 'Ethernet 1/1/2:5', 'remote_system_name': 'transfer-14.ultralight.org', 'remote_port_id': 'b8:59:9f:ed:2a:fa', 'remote_chassis_id': '04:32:01:04:94:8c'}
        """
        if hostinfo['mac-address'] == switchlldp['remote_port_id']:
            return True
        self.addWarning(f"Host {hostinfo['hostname']} does not match lldp information. Host Info: {hostinfo}, Switch LLDP Info: {switchlldp}")
        self._setwarningstart()
        return False

    def _setwarningstart(self):
        """Set warning start timestamp if not set"""
        if not self.warningstart:
            self.warningstart = getUTCnow()

    def _cleanWarningCounters(self):
        """Clean errors after 100 cycles"""
        self.runcount += 1
        if self.runcount >= 100:
            self.warningscounters = {}
            self.runcount = 0

    def countWarnings(self, warning):
        """Warning Counter"""
        self.warningscounters.setdefault(warning, 0)
        self.warningscounters[warning] += 1

    def addWarning(self, warning):
        """Record Alarm."""
        self.countWarnings(warning)
        if self.warningscounters[warning] >= 5:
            self.warnings.append(warning)

    def checkAndRaiseWarnings(self):
        """Check and raise warnings in case some vlans are used/configured manually."""
        # Check that for all vlan range, if it is on system usedVlans - it should be on deltas too;
        # otherwise it means vlan is configured manually (or deletion did not happen)
        # Get all active here and use everything from Active
        
        for host, vlans in self.activeDeltas['output']['usedVlans']['system'].items():
            if host in self.config.config.get('MAIN', {}):
                # Means it is a switch (host check remains for Agents itself)
                all_vlan_range_list = self.config.config.get('MAIN', {}).get(host, {}).get('all_vlan_range_list', [])
                for vlan in vlans:
                    if vlan in all_vlan_range_list and vlan not in self.usedVlans['deltas'].get(host, []):
                        self.addWarning(f"Vlan {vlan} is configured manually on {host}. It comes not from delta."
                                         "Either deletion did not happen or was manually configured.")
        # Add switchwarnings (in case any exists)
        self.warnings += self.switch.getWarnings()
        if self.warnings:
            self.warningstart = self.warningstart if self.warningstart else getUTCnow()
            self.logger.warning("Warnings: %s", self.warnings)
            warnings = "\n".join(self.warnings)
            self.warnings = []
            raise ServiceWarning(warnings)



    def startwork(self):
        """Main run"""
        self._cleanWarningCounters()
        self.activeDeltas = getActiveDeltas(self)
        self.switchInfo = self.switch.getinfo()
        for hostcheck in self.getAllHostIntfMacs():
            print(hostcheck)
            switchlldp = self._getSwitchLLDPInfo(hostcheck)
            if hostcheck and switchlldp:
                self._validateHostSwitchInfo(hostcheck, switchlldp)
        # Raise warnings if any exists
        if self.warningstart and self.warningstart <= getUTCnow() + 3600 : # If warnings raise an hour ago - refresh
            self.warningstart = 0
            self.logger.info("Warnings were raised more than 1hr ago. Informing to renew all devices state")
            self.switch.deviceUpdate(self.sitename)
        self.checkAndRaiseWarnings()


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args:
        if args.sitename:
            validator = Validator(config, args.sitename)
            validator.startwork()

def get_parser():
    """Returns the argparse parser."""
    # pylint: disable=line-too-long
    oparser = argparse.ArgumentParser(
        description="This daemon is used for validating host and switch configurations.",
        prog=os.path.basename(sys.argv[0]),
        add_help=True,
    )
    # Main arguments
    oparser.add_argument(
        "--sitename",
        dest="sitename",
        default="",
        help="Sitename of FE. Must be present in configuration and database.",
    )
    return oparser

if __name__ == "__main__":
    argparser = get_parser()
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    if len(sys.argv) == 1:
        argparser.print_help()
    inargs = argparser.parse_args(sys.argv[1:])
    getLoggingObject(logType="StreamLogger", service="PolicyService")
    execute(args=inargs)
