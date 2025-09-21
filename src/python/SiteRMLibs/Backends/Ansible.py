#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Ansible Backend
Calls Ansible Runnner to get Switch configs, Apply configs,
Calls Parser if available to parse additional Info from switch Out

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""
import os
import random
import time

import ansible_runner
import yaml
from SiteRMLibs.Backends import parsers
from SiteRMLibs.CustomExceptions import ConfigException
from SiteRMLibs.MainUtilities import getLoggingObject, withTimeout


class Switch:
    """Ansible Switch Module"""

    def __init__(self, config, sitename):
        self.parsers = parsers.ALL
        self.defVlans = parsers.MAPPING
        self.config = config
        self.sitename = sitename
        self.logger = getLoggingObject(config=self.config, service="SwitchBackends")
        self.ansibleErrs = {}
        self.verbosity = 0

    @staticmethod
    def activate(_inputDict, _actionState):
        """Activating state actions."""
        return True

    def getAnsErrors(self, ansOut):
        """Get Ansible errors"""
        failures = False
        if not ansOut or not ansOut.stats:
            return failures
        for fkey in ["dark", "failures"]:
            for host, _ in ansOut.stats.get(fkey, {}).items():
                for hostEvents in ansOut.host_events(host):
                    err = hostEvents.get("event_data", {}).get("res", {})
                    if hostEvents.get("event") in ["runner_on_ok", "runner_on_start"]:
                        continue
                    if not err:
                        continue
                    self.ansibleErrs.setdefault(host, {}).setdefault(fkey, [])
                    self.ansibleErrs[host][fkey].append(err)
                    self.logger.info("Ansible Error for %s: %s", host, err)
                    failures = True
        return failures

    def _writeInventoryInfo(self, out, subitem=""):
        """Write Ansible Inventory file (used only in a single apply)"""
        fname = f"{self.config.get('ansible', 'inventory' + subitem)}"
        with open(fname, "w", encoding="utf-8") as fd:
            fd.write(yaml.dump(out))

    def _getInventoryInfo(self, hosts=None, subitem=""):
        """Get Inventory Info. If hosts specified, only return for specific hosts"""
        with open(self.config.get("ansible", "inventory" + subitem), "r", encoding="utf-8") as fd:
            out = yaml.safe_load(fd.read())
        if hosts:
            tmpOut = {}
            for osName, oshosts in out.items():
                for hostname, hostdict in oshosts.get("hosts", {}).items():
                    if hostname in hosts:
                        tmpOut.setdefault(osName, {"hosts": {}})
                        tmpOut[osName]["hosts"].setdefault(hostname, hostdict)
            return tmpOut
        return out

    def _getRotateArtifacts(self, playbook, subitem=""):
        """Get Rotate Artifacts Counter"""
        # This is a hack to make sure we have unique artifacts count.
        # And also that cleanup process is dony only by getfacts playbook.
        if playbook == "getfacts.yaml":
            return self.config.get("ansible", "rotate_artifacts" + subitem) + random.randint(1, 50)
        # If we are not running getfacts playbook, we should not rotate artifacts.
        # Just in case - increase it 200 times.
        return self.config.get("ansible", "rotate_artifacts" + subitem) + 200

    def __getVerbosity(self, subitem):
        """Get Verbosity level for Ansible Runner"""
        if self.verbosity != 0:
            return self.verbosity
        verbosity = self.config.getint("ansible", "verbosity" + subitem)
        return min(verbosity, 7)

    def __logAnsibleOutput(self, ansOut):
        """Log Ansible Output"""
        if ansOut and hasattr(ansOut, "stdout") and ansOut.stdout:
            for line in ansOut.stdout:
                self.logger.debug(f"[STDOUT] {line}")
        else:
            self.logger.debug("No stdout available from ansible_runner.")
        if ansOut and hasattr(ansOut, "stderr") and ansOut.stderr:
            for line in ansOut.stderr:
                self.logger.debug(f"[STDERR] {line}")
        else:
            self.logger.debug("No stderr available from ansible_runner.")
        if ansOut and hasattr(ansOut, "stats") and ansOut.stats:
            for key, value in ansOut.stats.items():
                self.logger.debug(f"[STATS] {key}: {value}")

    @withTimeout(120)
    def _executeAnsible(self, playbook, hosts=None, subitem=""):
        """Execute Ansible playbook"""
        # As we might be running multiple workers, we need to make sure
        # cleanup process is done correctly.
        retryCount = self.config.getint("ansible", "ansible_runtime_retry")
        while retryCount > 0:
            try:
                ansOut = ansible_runner.run(
                    private_data_dir=self.config.get("ansible", "private_data_dir" + subitem),
                    inventory=self.config.get("ansible", "inventory" + subitem),
                    playbook=playbook,
                    rotate_artifacts=self._getRotateArtifacts(playbook, subitem),
                    debug=self.config.getboolean("ansible", "debug" + subitem),
                    verbosity=self.__getVerbosity(subitem),
                    ignore_logging=self.config.getboolean("ansible", "ignore_logging" + subitem),
                    envvars={
                        "ANSIBLE_RUNNER_IDLE_TIMEOUT": str(self.config.getint("ansible", "ansible_runtime_idle_timeout")),
                        "ANSIBLE_RUNNER_TIMEOUT": str(self.config.getint("ansible", "ansible_runtime_job_timeout")),
                    },
                )
                self.__logAnsibleOutput(ansOut)
                return ansOut
            except FileNotFoundError as ex:
                self.logger.error(f"Ansible playbook got FileNotFound (usually cleanup. Will retry in 5sec): {ex}")
                self.logger.debug(f"Exception happened for {playbook} on hosts {hosts} with subitem {subitem}")
                retryCount -= 1
                time.sleep(self.config.getint("ansible", "ansible_runtime_retry_delay"))
            except Exception as ex:
                self.logger.error(f"Ansible playbook got unexpected Exception: {ex}")
                self.logger.debug(f"Exception happened for {playbook} on hosts {hosts} with subitem {subitem}", exc_info=True)
                retryCount -= 1
                time.sleep(self.config.getint("ansible", "ansible_runtime_retry_delay"))
        raise Exception("Ansible playbook execution failed after 3 retries. Check logs for more details.")

    def getAnsNetworkOS(self, host, subitem=""):
        """Get Ansible network os from hosts file"""
        return self.getHostConfig(host, subitem).get("ansible_network_os", "")

    def getHostConfig(self, host, subitem=""):
        """Get Ansible Host Config"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir'+ subitem)}/{host}.yaml"
        if not os.path.isfile(fname):
            raise Exception(f"Ansible config file for {host} not available.")
        with open(fname, "r", encoding="utf-8") as fd:
            out = yaml.safe_load(fd.read())
        return out

    def _writeHostConfig(self, host, out, subitem=""):
        """Write Ansible Host config file"""
        fname = f"{self.config.get('ansible', 'inventory_host_vars_dir' + subitem)}/{host}.yaml"
        if not subitem and not os.path.isfile(fname):
            raise Exception(f"Ansible config file for {host} not available.")
        with open(fname, "w", encoding="utf-8") as fd:
            fd.write(yaml.dump(out))

    def _applyNewConfig(self, hosts=None, subitem="", templateName="applyconfig.yaml"):
        """Apply new config and run ansible playbook"""
        self.verbosity = 0
        retries = 3
        self.ansibleErrs = {}
        while retries > 0:
            try:
                ansOut = self._executeAnsible(templateName, hosts, subitem)
            except ValueError as ex:
                raise ConfigException(f"Got Value Error. Ansible configuration exception {ex}") from ex
            failures = self.getAnsErrors(ansOut)
            if failures:
                self.logger.error(f"Ansible applyconfig failed. Retrying (out of {retries}) after 5sec sleep")
                retries -= 1
                time.sleep(5)
                self.verbosity = 7
                continue
            retries = 0
        return ansOut, self.ansibleErrs

    def _getFacts(self, hosts=None, subitem=""):
        """Get All Facts for all Ansible Hosts"""
        self.ansibleErrs = {}
        try:
            ansOut = self._executeAnsible("getfacts.yaml", hosts, subitem)
        except ValueError as ex:
            raise ConfigException(f"Got Value Error. Ansible configuration exception {ex}") from ex
        out = {}
        for host, _ in ansOut.stats["ok"].items():
            out.setdefault(host, {})
            for host_events in ansOut.host_events(host):
                if host_events["event"] != "runner_on_ok":
                    continue
                action = host_events["event_data"]["task_action"]
                if action not in self.parsers.keys():
                    self.logger.warning("Unsupported NOS. There might be issues. Contact dev team")
                out[host] = host_events
                host_events.setdefault("event_data", {}).setdefault("res", {}).setdefault("ansible_facts", {})
                # If it still remains empty, we report error
                if not host_events["event_data"]["res"]["ansible_facts"]:
                    msg = f"No facts available for {host}. There might be issues."
                    self.logger.error(f"{msg}. Run ansible-runner manually and inform dev team.")
                    self.ansibleErrs.setdefault(host, {}).setdefault("failures", [])
                    self.ansibleErrs[host]["failures"].append({"msg": msg})
        self.getAnsErrors(ansOut)
        return out, self.ansibleErrs

    @staticmethod
    def getports(inData):
        """Get ports from ansible output"""
        return inData.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get("ansible_net_interfaces", {}).keys()

    @staticmethod
    def getPortMembers(inData, port):
        """Get port members from ansible output"""
        return inData.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get("ansible_net_interfaces", {}).get(port, {}).get("channel-member", [])

    @staticmethod
    def getportdata(inData, port):
        """Get port data from ansible output"""
        return inData.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get("ansible_net_interfaces", {}).get(port, {})

    def getvlans(self, inData):
        """Get vlans from ansible output"""
        swname = inData.get("event_data", {}).get("host", "")
        ports = self.getports(inData)
        tmpout = [vlan for vlan in ports if vlan.startswith("Vlan")]
        if self.config.has_option(swname, "allvlans") and self.config.get(swname, "allvlans"):
            return tmpout
        # If we reach here, means allvlans flag is false. It should include into model only SENSE Vlans.
        out = []
        if self.config.has_option(swname, "all_vlan_range_list") and self.config.get(swname, "all_vlan_range_list"):
            for item in tmpout:
                vlanid = self.getVlanKey(item)
                if isinstance(vlanid, int):
                    if vlanid in self.config.get(swname, "all_vlan_range_list"):
                        out.append(item)
                else:
                    self.logger.warning(f"Issue with vlan name {item}. Not able to make integer")
                    out.append(item)
        else:
            # This point to an issue in SiteRM configuration. In this case we return all vlans
            self.logger.warning("There is an issue with all vlans range configuration. Contact DEV Team")
            return tmpout
        return out

    @staticmethod
    def getVlanKey(port):
        """Normalize Vlan Key between diff switches"""
        if port.startswith("Vlan_"):
            return int(port[5:])
        if port.startswith("Vlan "):
            return int(port[5:])
        if port.startswith("Vlan"):
            return int(port[4:])
        return port

    def getvlandata(self, inData, vlan):
        """Get vlan data from ansible output"""
        return self.getportdata(inData, vlan)

    @staticmethod
    def getfactvalues(inData, key):
        """Get custom command output from ansible output, like routing, lldp, mac"""
        return inData.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get(key, {})

    def nametomac(self, inData, key):
        """Return all mac's associated to that host. Not in use for RAW plugin"""
        macs = inData.get("event_data", {}).get("res", {}).get("ansible_facts", {}).get("ansible_net_info", {}).get("macs", [])
        if macs and isinstance(macs, str):
            return [macs]
        if macs and isinstance(macs, list):
            return macs
        self.logger.debug(f"Warning. Mac info not available for switch {key}. Path links might be broken.")
        return []
