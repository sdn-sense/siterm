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

class KubeInfo:
    """KubeInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service='Agent')
        self.hostname = self.config.get('agent', 'hostname')
        self.allLabels = {}

    def _getAllLabels(self, hostname):
        # Load kubeconfig from default location or in-cluster configuration
        k8sconfig.load_incluster_config()
        # Create Kubernetes API client
        v1 = client.CoreV1Api()
        # Get node object
        node = v1.read_node(hostname)
        # Extract and return node labels
        self.allLabels = node.metadata.labels

    def postProcess(self, data):
        """Post process data"""
        for key, val in data.get('KubeInfo', {}).get('isAlias', {}).items():
            # Split it to get switch and port
            switch, port = val.split(':')[-2:]
            # Check if we have this interface in NetInfo
            if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}):
                # if isAlias is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('isAlias'):
                    self.logger.error(f"Interface {key} already has isAlias (and we get it from Kube Labels. Which one is right?")
                else:
                    data['NetInfo']['interfaces'][key]['isAlias'] = val
                # if switch_port is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch_port'):
                    self.logger.error(f"Interface {key} already has switch port (and we get it from Kube Labels. Which one is right?")
                else:
                    data['NetInfo']['interfaces'][key]['switch_port'] = replaceSpecialSymbols(port, reverse=True)
                # if port is defined - than it is an issue which one to use. Leave one from NetInfo
                if data.get('NetInfo', {}).get('interfaces', {}).get(key, {}).get('switch'):
                    self.logger.error(f"Interface {key} already has switch (and we get it from Kube Labels. Which one is right?")
                else:
                    data['NetInfo']['interfaces'][key]['switch'] = switch
            else:
                self.logger.error(f"Interface {key} not found in NetInfo. Failed NetInfo plugin?")
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
                    # Kubernetes does not allow label's to have :. in the value, so we use --
                    # In future - we might need to allow this to be controlled via config file.
                    out.setdefault('isAlias', {}).setdefault(intf, self.allLabels[isAliasLabel].replace("--", ":"))
            if 'multus' in kubeLabels:
                multusLabel = f"{kubeLabels['multus']}"
                if multusLabel in self.allLabels:
                    out.setdefault('multus', {}).setdefault(intf, self.allLabels[multusLabel])
        return out

if __name__ == "__main__":
    obj = KubeInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
