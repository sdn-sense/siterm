#!/usr/bin/env python3
# pylint: disable=W0212
# pylint: disable=line-too-long
"""Provisioning service is provision everything on the switches;

Copyright 2021 California Institute of Technology
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
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
UpdateDate              : 2022/05/09
"""
import copy
import sys

from SiteFE.ProvisioningService.modules.RoutingService import RoutingService
from SiteFE.ProvisioningService.modules.VirtualSwitchingService import \
    VirtualSwitchingService
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.CustomExceptions import (NoOptionError, NoSectionError,
                                         SwitchException)
from SiteRMLibs.MainUtilities import (createDirs, evaldict, getDBConn,
                                      getLoggingObject, getUTCnow, getVal)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.BWService import BWService
from SiteRMLibs.timing import Timing


class ProvisioningService(RoutingService, VirtualSwitchingService, BWService, Timing):
    """
    Provisioning service communicates with Local controllers and applies
    network changes.
    """

    def __init__(self, config, sitename):
        super().__init__()
        self.config = config
        self.logger = getLoggingObject(config=self.config, service="ProvisioningService")
        self.sitename = sitename
        self.switch = Switch(config, sitename)
        self.dbI = getVal(getDBConn("ProvisioningService", self), **{"sitename": self.sitename})
        workDir = self.config.get("general", "privatedir") + "/ProvisioningService/"
        createDirs(workDir)
        self.yamlconfuuid = {}
        self.yamlconfuuidActive = {}
        self.connID = None
        self.activeOutput = {"output": {}}

    def refreshthread(self):
        """Call to refresh thread for this specific class and reset parameters"""
        self.config = getGitConfig()
        self.switch = Switch(self.config, self.sitename)
        self.yamlconfuuid = {}
        self.yamlconfuuidActive = {}

    def __cleanup(self):
        """Cleanup yaml conf output"""
        self.yamlconfuuid = {}

    def getConfigValue(self, section, option, raiseError=False):
        """Get Config Val"""
        try:
            return self.config.get(section, option)
        except (NoOptionError, NoSectionError) as ex:
            if raiseError:
                raise ex
        return ""

    def prepareYamlConf(self, activeConfig, switches):
        """Prepare yaml config"""
        self.addvsw(activeConfig, switches)
        self.addrst(activeConfig, switches)

    def applyConfig(self, raiseExc=True, hosts=None, subitem=""):
        """Apply yaml config on Switch"""
        ansOut, failures = self.switch.plugin._applyNewConfig(hosts, subitem)
        if not ansOut:
            self.logger.debug("Ansible output is empty for applyConfig")
            return
        if not hasattr(ansOut, "stats"):
            self.logger.debug("Ansible output has no stats attribute")
            return
        if not ansOut.stats:
            self.logger.debug("Ansible output has stats empty")
            return
        if failures and raiseExc:
            # TODO: Would be nice to save in DB and see errors from WEB UI)
            self.logger.error(f"Ansible failures: {failures}")
            raise SwitchException(
                "There was configuration apply issue. Please contact support and provide this log file."
            )
        return

    def __insertDeltaStateDB(self, **kwargs):
        """Write new state to DB"""
        dbOut = {
            "insertdate": getUTCnow(),
            "uuid": kwargs["uuid"],
            "uuidtype": kwargs["acttype"],
            "hostname": kwargs["swname"],
            "hostport": kwargs["hostport"],
            "uuidstate": kwargs["uuidstate"],
        }
        self.dbI.insert("deltatimestates", [dbOut])

    @staticmethod
    def __identifyReportState(items, **kwargs):
        """Identify report state. Default unknown, and will be one of:
        activated, activate-error, deactivated, deactive-error
        """
        nstate = "unknown"
        if items.get('state', None) not in ["present", "error"] or kwargs.get('uuidstate', None) not in ["ok", "error"]:
            nstate = "unknown"
        elif items["state"] == "present" and kwargs["uuidstate"] == "ok":
            # This means it was activated;
            nstate = "activated"
        elif items["state"] == "present" and kwargs["uuidstate"] == "error":
            # This means it was activate-error
            nstate = "activate-error"
        elif items["state"] == "absent" and kwargs["uuidstate"] == "ok":
            # This means it was deactivated
            nstate = "deactivated"
        elif items["state"] == "absent" and kwargs["uuidstate"] == "error":
            # this means it was deactivate-error
            nstate = "deactivate-error"
        return nstate

    def __reportDeltaState(self, **kwargs):
        """Report state to db (requires diff reporting based on vsw/rst)"""
        if kwargs["acttype"] == "vsw" and kwargs.get("applied", None):
            for _key, items in kwargs["applied"].items():
                tmpkwargs = copy.deepcopy(kwargs)
                tmpkwargs["uuidstate"] = self.__identifyReportState(items, **kwargs)
                for intf in items.get("tagged_members"):
                    tmpkwargs["hostport"] = self.switch.getSystemValidPortName(intf)
                    self.__insertDeltaStateDB(**tmpkwargs)
        if kwargs["acttype"] == "rst" and kwargs.get("applied", None):
            kwargs["uuidstate"] = self.__identifyReportState(
                kwargs["applied"], **kwargs
            )
            for key, _items in kwargs["applied"].get("neighbor", {}).items():
                kwargs["hostport"] = key
                self.__insertDeltaStateDB(**kwargs)

    def applyIndvConfig(self, swname, uuid, key, acttype, raiseExc=True):
        """Apply a single delta to network devices and report to DB it's state"""
        # Write new inventory file, based on the currect active(just in case things have changed)
        # or container was restarted
        inventory = self.switch.plugin._getInventoryInfo([swname])
        self.switch.plugin._writeInventoryInfo(inventory, "_singleapply")
        # Get host configuration;
        curActiveConf = self.switch.plugin.getHostConfig(swname)
        # Delete 2 items as we will need everything else
        # For applying into devices
        curActiveConf.pop("interface", None)
        curActiveConf.pop("sense_bgp", None)
        curActiveConf[key] = (
            self.yamlconfuuid.get(acttype, {})
            .get(uuid, {})
            .get(swname, {})
            .get(key, {})
        )
        # Write curActiveConf to single apply dir
        self.switch.plugin._writeHostConfig(swname, curActiveConf, "_singleapply")
        try:
            self.applyConfig(raiseExc, [swname], "_singleapply")
            networkstate = "ok"
        except SwitchException:
            networkstate = "error"
        self.__reportDeltaState(
            **{
                "swname": swname,
                "uuid": uuid,
                "acttype": acttype,
                "key": key,
                "applied": curActiveConf[key],
                "uuidstate": networkstate,
            }
        )

    def compareIndv(self, switches):
        """Compare individual entries and report it's status"""
        changed = False
        for acttype, actcalls in {"vsw": {"interface": self.compareVsw},
                                  "rst": {"sense_bgp": self.compareBGP}}.items():
            uuidDict = self.yamlconfuuidActive.get(acttype, {})
            if not self.yamlconfuuidActive:
                uuidDict = self.yamlconfuuid.get(acttype, {})
            for uuid, ddict in uuidDict.items():
                for swname, swdict in ddict.items():
                    if swname not in switches:
                        continue
                    for key, call in actcalls.items():
                        if key in swdict and call:
                            self.logger.info(f"Comparing {acttype} for {uuid} config with ansible config")
                            curAct = (self.yamlconfuuidActive.get(acttype, {})
                                      .get(uuid, {}).get(swname, {}).get(key, {}))
                            diff = call(swname, curAct, uuid)
                            if diff:
                                changed = True
                                self.applyIndvConfig(swname, uuid, key, acttype)
        return changed


    def _getActive(self):
        """Get Active Output"""
        self.activeOutput = {"output": {}}
        activeDeltas = self.dbI.get("activeDeltas")
        if activeDeltas:
            activeDeltas = activeDeltas[0]
            self.activeOutput["output"] = evaldict(activeDeltas["output"])

    def startwork(self):
        """Start Provisioning Service main worker."""
        # Get current active config;
        self.__cleanup()
        self._getActive()
        self.switch.getinfo()
        switches = self.switch.getAllSwitches()
        self.prepareYamlConf(self.activeOutput["output"], switches)

        # Compare individual requests and report it's states
        configChanged = self.compareIndv(switches)
        # Save individual uuid conf inside memory;
        self.yamlconfuuidActive = copy.deepcopy(self.yamlconfuuid)


        return configChanged


def execute(config=None, args=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    if args:
        provisioner = ProvisioningService(config, args[1])
        provisioner.startwork()
    else:
        for sitename in config.get("general", "sites"):
            provisioner = ProvisioningService(config, sitename)
            provisioner.startwork()


if __name__ == "__main__":
    print(
        "WARNING: ONLY FOR DEVELOPMENT!!!!. Number of arguments:",
        len(sys.argv),
        "arguments.",
    )
    print("1st argument has to be sitename which is configured in this frontend")
    print(sys.argv)
    getLoggingObject(logType="StreamLogger", service="ProvisioningService")
    execute(args=sys.argv)
