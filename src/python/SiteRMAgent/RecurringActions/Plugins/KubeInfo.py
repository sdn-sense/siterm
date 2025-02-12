#!/usr/bin/env python3
"""Plugin which gathers information about certificate

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/12/23
"""
import pprint
from kubernetes import client
from kubernetes import config as k8sconfig
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.CustomExceptions import PluginFatalException

class KubeInfo:
    """KubeInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service='Agent')
        self.hostname = self.config.get('agent', 'hostname')
        self.allLabels = {}
        self.failedLabels = {}

    def _getAllLabels(self, hostname):
        # Load kubeconfig from default location or in-cluster configuration
        k8sconfig.load_incluster_config()
        # Create Kubernetes API client
        v1 = client.CoreV1Api()
        # Get node object
        node = v1.read_node(hostname)
        # Extract and return node labels
        self.allLabels = node.metadata.labels

    def _identifyKubeLabelsisAlias(self, interface):
        """Identify which kubelabels are defined"""
        errormsg = ""
        if self.failedLabels.get('isAlias'):
            # Find all labels that start with isAlias
            isAliasLabel = self.config.get(interface, "kubeLabels").get('isAlias')
            if isAliasLabel:
                for label, labelval in self.allLabels.items():
                    if label.startswith(isAliasLabel):
                        errormsg += f"Kube Labels: Label {label} | Value {labelval}"
        return errormsg


    def postProcess(self, data):
        """Post process data"""
        for key, val in data.get('KubeInfo', {}).get('isAlias', {}).items():
            # Split it to get switch and port
            switch, port = val.split(':')[-2:]
            # Check if we have this interface in NetInfo
            if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}):
                # if isAlias is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('isAlias'):
                    alarm = f"Interface {key} already has isAlias in git config (and we get it from Kube Labels. Which one is right?"
                    alarm += f"NetInfo: {data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('isAlias')}"
                    alarm += f"KubeInfo: {self._identifyKubeLabelsisAlias(key)}"
                    raise PluginFatalException(alarm)
                data['NetInfo']['interfaces'][key]['isAlias'] = val
                # if switch_port is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch_port'):
                    alarm = f"Interface {key} already has switch port in git config (and we get it from Kube Labels. Which one is right?"
                    alarm += f"NetInfo: {data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch_port')}"
                    alarm += f"KubeInfo: {self._identifyKubeLabelsisAlias(key)}"
                    raise PluginFatalException(alarm)
                data['NetInfo']['interfaces'][key]['switch_port'] = replaceSpecialSymbols(port, reverse=True)
                # if port is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch'):
                    alarm = f"Interface {key} already has switch in git config (and we get it from Kube Labels. Which one is right?"
                    alarm += f"NetInfo: {data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch')}"
                    alarm += f"KubeInfo: {self._identifyKubeLabelsisAlias(key)}"
                    raise PluginFatalException(alarm)
                data['NetInfo']['interfaces'][key]['switch'] = switch
            else:
                alarm = f"Interface {key} not found in Host. Either interface does not exist or NetInfo Plugin failed."
                alarm += "Please make sure that interface exists and same interface name defined in git configuration file."
                raise PluginFatalException(alarm)
        # And finally, check if all info now is present for all Interfaces
        for key, intfData in data.get('NetInfo', {}).get('interfaces', {}).items():
            if not intfData.get('switch_port'):
                alarm = f"Interface {key} has no switch port defined, nor was available from Kube (in case Kube install)!"
                alarm += "Please make sure that interface exists and same interface name defined in git configuration file."
                alarm += "If you are using Kube, make sure that Kube Labels are defined correctly."
                alarm += f"KubeInfo: {self._identifyKubeLabelsisAlias(key)}"
                raise PluginFatalException(alarm)
            if not intfData.get('switch'):
                alarm = f"Interface {key} has no switch defined, nor was available from Kube (in case Kube install)!"
                alarm += "Please make sure that interface exists and same interface name defined in git configuration file."
                alarm += "If you are using Kube, make sure that Kube Labels are defined correctly."
                alarm += f"KubeInfo: {self._identifyKubeLabelsisAlias(key)}"
                raise PluginFatalException(alarm)
        return data

    def get(self, **_kwargs):
        """Get certificate info."""
        # Check if kubernetes is configured in configuration
        receivedLabels = False
        out = {}
        for intf in self.config.get("agent", "interfaces"):
            if not self.config.has_option(intf, "kubeLabels"):
                continue
            kubeLabels = self.config.get(intf, "kubeLabels")
            if not kubeLabels:
                continue
            if not receivedLabels:
                self._getAllLabels(self.hostname)
                receivedLabels = True
            # Now we have all labels from Kubernetes and we can check if any of them is in kubeLabels
            # Currently we support only isAlias and multus labels
            if 'isAlias' in kubeLabels:
                isAliasLabel = f"{kubeLabels['isAlias']}.{intf}"
                if isAliasLabel in self.allLabels:
                    # Kubernetes does not allow label's to have :.+ in the value, so we use -- for : and --- for +
                    # In future - we might need to allow this to be controlled via config file.
                    newlabel = self.allLabels[isAliasLabel].replace("---", "+")
                    newlabel = newlabel.replace("--", ":")
                    out.setdefault('isAlias', {}).setdefault(intf, newlabel)
                else:
                    self.failedLabels['isAlias'] = True
            if 'multus' in kubeLabels:
                multusLabel = f"{kubeLabels['multus']}"
                if multusLabel in self.allLabels:
                    out.setdefault('multus', {}).setdefault(intf, self.allLabels[multusLabel])
            else:
                self.failedLabels['multus'] = True
        return out

if __name__ == "__main__":
    obj = KubeInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
