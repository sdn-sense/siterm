#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Validator service to validate host and switch configurations and link mappings.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2025/04/21
"""
import argparse
import os
import sys

from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import ServiceWarning
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    contentDB,
    createDirs,
    getActiveDeltas,
    getAllHosts,
    getDBConn,
    getFileContentAsJson,
    getLoggingObject,
    getUTCnow,
    getVal,
    getTempDir

)


class Validator:
    """Validate Switch and Host configurations and link mappings."""

    def __init__(self, config, sitename):
        self.sitename = sitename
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="Validator")
        self.siteDB = contentDB()
        self.dbI = getVal(getDBConn("Validator", self), **{"sitename": self.sitename})
        self.switch = Switch(config, sitename)
        self.hosts = {}
        workDir = os.path.join(self.config.get(sitename, "privatedir"), "Validator/")
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

    @staticmethod
    def _getMacAddress(nodeDict, interface):
        """Get MAC address from configuration."""
        for entry in nodeDict.get("hostinfo", {}).get("NetInfo", {}).get("interfaces", {}).get(interface, {}).get("17", []):
            if "mac-address" in entry and entry["mac-address"]:
                return entry["mac-address"]
        return None

    @staticmethod
    def _allvaluesDefined(inval):
        """Check if all values are defined and not None"""
        return all(value for value in inval.values())

    @staticmethod
    def _getHostInterfaces(nodeDict):
        """Get Host Interfaces from configuration."""
        return nodeDict.get("hostinfo", {}).get("Summary", {}).get("config", {}).get("agent", {}).get("interfaces", [])

    @staticmethod
    def _getSwitchInterface(nodeDict, interface):
        """Get Switch Interface from configuration."""
        return nodeDict.get("hostinfo", {}).get("Summary", {}).get("config", {}).get(interface, {}).get("port", None)

    @staticmethod
    def _getSwitchName(nodeDict, interface):
        """Get Switch Name from configuration."""
        return nodeDict.get("hostinfo", {}).get("Summary", {}).get("config", {}).get(interface, {}).get("switch", None)

    def getAllHostIntfMacs(self):
        """Get all host and intf mac info"""
        jOut = getAllHosts(self.dbI)
        for _nodeHostname, nodeDict in list(jOut.items()):
            nodeDict["hostinfo"] = getFileContentAsJson(nodeDict["hostinfo"])
            # Get all interfaces in configuration and their mac addresses
            for intf in self._getHostInterfaces(nodeDict):
                hostcheck = {"hostname": nodeDict["hostname"], "intf": intf}
                # Get mac address from configuration
                hostcheck["mac-address"] = self._getMacAddress(nodeDict, intf)
                # Get Switch
                hostcheck["switch"] = self._getSwitchName(nodeDict, intf)
                # Get Switch Port
                hostcheck["port"] = self._getSwitchInterface(nodeDict, intf)
                # Check if none of the values are None
                if self._allvaluesDefined(hostcheck):
                    yield hostcheck

    def _getSwitchLLDPInfo(self, hostcheck):
        """Get Switch LLDP Info for switch and port"""
        return self.switchInfo.get("lldp", {}).get(hostcheck["switch"], {}).get(hostcheck["port"], {})

    def _validateSwichInfo(self):
        """Validate Switch information"""
        # Check first if this is ansible configuration site.
        if self.config.get(self.sitename, "plugin") != "ansible":
            return
        # We check that config switchname is correctly defined under switch, and has full config;
        for swname in self.config.get(self.sitename, "switch"):
            if not self.switchInfo.get("ports", {}).get(swname, {}):
                self.addWarning(f"Switch {swname} defined in configuration, but no output received from Ansible call.")
                self._setwarningstart()
            # Check also all port information, that it is received from Ansible
            if not self.config.get(swname, "ports"):
                continue
            for portname, portinfo in self.config.get(swname, "ports").items():
                if portinfo.get("realportname", ""):
                    portname = portinfo["realportname"]
                if not self.switchInfo.get("ports", {}).get(swname, {}).get(portname, {}):
                    self.addWarning(f"Switch {swname} port {portname} defined in configuration, but no output received from Ansible call.")
                    self._setwarningstart()

    def _validateHostSwitchInfo(self, hostinfo, switchlldp):
        """Validate Host and Switch information"""
        if hostinfo.get("mac-address") == switchlldp.get("remote_port_id"):
            return True
        if hostinfo.get("mac-address") == switchlldp.get("remote_chassis_id"):
            return True
        self.addWarning(f"Host {hostinfo['hostname']} does not match lldp information. Host Info: {hostinfo}, Switch LLDP Info: {switchlldp}")
        self._setwarningstart()
        return False

    def _checkLivenessReadiness(self):
        """Check if liveness and readiness checks are disabled"""
        for name, fname in {"Liveness": getTempDir() / "siterm-liveness-disable", "Readiness": getTempDir() / "siterm-readiness-disable"}.items():
            if os.path.exists(fname):
                msg = f"{name} check is disabled on Frontend. Please enable it to ensure proper operation."
                self.logger.warning(msg)
                self.addWarning(msg)
                self._setwarningstart()

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
        """Check and raise warnings."""
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
        self._validateSwichInfo()
        for hostcheck in self.getAllHostIntfMacs():
            switchlldp = self._getSwitchLLDPInfo(hostcheck)
            if hostcheck and switchlldp:
                self._validateHostSwitchInfo(hostcheck, switchlldp)
        # Raise warnings if any exists
        if self.warningstart and self.warningstart <= getUTCnow() - 3600:  # If warnings raise an hour ago - refresh
            self.warningstart = 0
            self.logger.info("Warnings were raised more than 1hr ago. Informing to renew all devices state")
            self.switch.deviceUpdate(self.sitename)
        self._checkLivenessReadiness()
        self.checkAndRaiseWarnings()


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args and args.sitename:
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
