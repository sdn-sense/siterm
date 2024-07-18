#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.CustomExceptions import SwitchException
from SiteRMLibs.Backends.main import Switch
from SiteRMLibs.ipaddr import ipVersion


class RapidPingNet(BaseDebugAction):
    """RapidPing class"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "RapidPingNet"
        self.switch = Switch(config, sitename)
        super().__init__()

    def _logStats(self, ansOut, hosts):
        """Log stats from ansible output"""
        for host in hosts:
            for host_events in ansOut.host_events(host):
                if 'stdout' in host_events and host_events['stdout']:
                    for line in host_events['stdout'].split("\n"):
                        self.logMessage(line)
                    for line in host_events.get('event_data', {}).get('res', {}).get('stdout', []):
                        for lline in line.split("\n"):
                            self.logMessage(lline)

    def applyConfig(self, raiseExc=True, hosts=None, subitem=""):
        """Apply yaml config on Switch (issue Ping Request)"""
        ansOut, failures = self.switch.plugin._applyNewConfig(hosts, subitem, templateName="ping.yaml")
        if not ansOut:
            self.logMessage("Ansible output is empty for ping request")
            return
        if not hasattr(ansOut, "stats"):
            self.logMessage("Ansible output has no stats attribute")
            return
        if not ansOut.stats:
            self.logMessage("Ansible output has stats empty")
            return
        # log all stats
        self._logStats(ansOut, hosts)
        if failures and raiseExc:
            self.logMessage(f"Ansible failures: {failures}")
            raise SwitchException("There was configuration apply issue. Please contact support and provide this log file.")
        self.logMessage(f"Ansible output: {ansOut.stats}")
        return

    def _getPingTemplate(self):
        """Prepare ping template"""
        ipv = ipVersion(self.requestdict['ip'])
        out = {"count": self.requestdict['count'],
               "timeout": self.requestdict['timeout'],
               "type": f"ipv{ipv}",
               f"ipv{ipv}_address": self.requestdict['ip']}
        vrf = self.config.config["MAIN"].get(self.requestdict['hostname'], {}).get("vrf", "")
        if vrf:
            out["vrf"] = vrf
        return out

    def main(self):
        """Main RapidPing work. Run RapidPing on switches."""
        swname = self.requestdict['hostname']
        inventory = self.switch.plugin._getInventoryInfo([swname])
        self.switch.plugin._writeInventoryInfo(inventory, "_debug")
        curActiveConf = self.switch.plugin.getHostConfig(swname)
        # Pop out configuration (for configuring devices)
        curActiveConf.pop("interface", None)
        curActiveConf.pop("sense_bgp", None)
        curActiveConf.pop("qos", None)
        curActiveConf.pop("ping", None)
        curActiveConf.pop("traceroute", None)
        # Prepare ping template and attach to new ansible request
        curActiveConf["ping"] = self._getPingTemplate()
        # Write curActiveConf to single apply dir
        self.logMessage(f"Execute Ping Request for {swname}. Full request: {self.requestdict}")
        self.switch.plugin._writeHostConfig(swname, curActiveConf, "_debug")
        try:
            self.applyConfig(True, [swname], "_debug")
            self.logMessage(f"Ping Request was successful for {swname}.")
            self.jsonout['exitCode'] = 0
        except SwitchException as ex:
            self.logMessage(f"Received an error to issue ping for {swname}")
            self.logMessage(f"Exception: {ex}")
            self.jsonout['exitCode'] = -1
