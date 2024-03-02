#!/usr/bin/env python3
# pylint: disable=E1101
"""
    Push Daemon for Prometheus stats.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
from prometheus_client import Gauge
from prometheus_client import CollectorRegistry, push_to_gateway
from SiteRMLibs.MainUtilities import getWebContentFromURL
from SiteRMLibs.MainUtilities import postWebContentToURL
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getArpVals
from SiteRMLibs.BaseDebugAction import BaseDebugAction

class PromPush(BaseDebugAction):
    """Prom Push class loops over"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="PromPush")
        self.arpLabels = {'Device': '', 'Flags': '', 'HWaddress': '',
                          'HWtype': '', 'IPaddress': '', 'Mask': ''}
        self.arpLabels.update(self.__getMetadataParams())
        self.logger.info("====== PromPush Start Work. Config: %s", self.backgConfig)
        super().__init__()

    def __getMetadataParams(self):
        """Get metadata parameters"""
        if 'metadata' in self.backgConfig['requestdict']:
            return self.backgConfig['requestdict']['metadata']
        return {}

    def __generatePromPushUrl(self):
        """For posting node_exporter data, we need to generate full URL."""
        postUrl = self.backgConfig['requestdict']['gateway']
        if not postUrl.startswith('http'):
            postUrl = f"http://{postUrl}"
        postUrl += f"/metrics/job/job-{self.backgConfig['id']}"
        if self.__getMetadataParams():
            joinedLabels = '/'.join('/'.join((key, val)) for (key, val) in self.__getMetadataParams().items())
            postUrl += f"/{joinedLabels}"
        return postUrl

    def nodeExporterPush(self):
        """Push Node Exporter Output to Push Gateway"""
        # Get parameter of node_exporter from config
        nodeExporterUrl = self.config.get('general', 'node_exporter')
        if not nodeExporterUrl:
            return
        if not nodeExporterUrl.startswith('http'):
            nodeExporterUrl = f'http://{nodeExporterUrl}'
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        nodeOut = getWebContentFromURL(f'{nodeExporterUrl}/metrics')
        if 'status_code' in nodeOut and nodeOut['status_code'] == -1:
            self.stderr.append(f"Failed to get node_exporter data. Error: {nodeOut.get('error', 'Unknown')}")
            return
        response = postWebContentToURL(self.__generatePromPushUrl(),
                                       data=nodeOut.content,
                                       headers=headers)
        if 'status_code' in response and response['status_code'] == -1:
            self.stderr.append(f"Failed to push node_exporter data. Error: {response.get('error', 'Unknown')}")
            return
        self.logger.info(f"Pushed Node Exporter data. Return code: {response.status_code}")
        self.stdout.append(f"Pushed Node Exporter data. Return code: {response.status_code}")

    def __cleanRegistry(self):
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __pushToGateway(self, registry):
        """Push registry to remote gateway"""
        push_to_gateway(self.backgConfig['requestdict']['gateway'],
                        job=f"job-{self.backgConfig['id']}",
                        registry=registry,
                        grouping_key=self.__getMetadataParams())

    def arpPush(self):
        """Push ARP Output to Push Gateway"""
        registry = self.__cleanRegistry()
        arpState = Gauge('arp_state', 'ARP Address Table',
                         labelnames=self.arpLabels.keys(),
                         registry=registry)
        for arpEntry in getArpVals():
            self.arpLabels.update(arpEntry)
            arpState.labels(**self.arpLabels).set(1)
        self.__pushToGateway(registry)

    def main(self):
        """Start Prometheus Push Daemon thread work"""
        if self.backgConfig['requestdict']['type'] == 'prometheus-push':
            self.jsonout.setdefault('prometheus-push', [])
            self.nodeExporterPush()
        elif self.backgConfig['requestdict']['type'] == 'arp-push':
            self.jsonout.setdefault('arp-push', [])
            self.arpPush()
        else:
            self.stderr.append(f"Unsupported push method. Submitted request: {self.backgConfig}")
            raise Exception(f"Unsupported push method. Submitted request: {self.backgConfig}")
