#!/usr/bin/env python3
"""
    Push Daemon for Prometheus stats.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
import csv
from prometheus_client import Gauge
from prometheus_client import CollectorRegistry, push_to_gateway
from DTNRMLibs.MainUtilities import getWebContentFromURL
from DTNRMLibs.MainUtilities import postWebContentToURL
from DTNRMLibs.MainUtilities import getLoggingObject

# From https://github.com/torvalds/linux/blob/master/include/uapi/linux/if_arp.h
HW_FLAGS = {'0x1': 'ETHER', '0x32': 'INFINIBAND'}
ARP_FLAGS = {'0x0': 'I',
             '0x2': 'C',
             '0x4': 'M',
             '0x6': 'CM',
             '0x8': 'PUB',
             '0x10': 'PROXY',
             '0x20': 'NETMASK',
             '0x40': 'DONTPUB'}

def _getArpVals():
    with open('/proc/net/arp', encoding='utf-8') as arpfd:
        arpKeys = ['IP address', 'HW type', 'Flags', 'HW address', 'Mask', 'Device']
        reader = csv.DictReader(arpfd,
                                fieldnames=arpKeys,
                                skipinitialspace=True,
                                delimiter=' ')
        skippedHeader = False
        for block in reader:
            if not skippedHeader:
                skippedHeader = True
                continue
            if block['HW type'] in HW_FLAGS:
                block['HW type'] = HW_FLAGS[block['HW type']]
            if block['Flags'] in ARP_FLAGS:
                block['Flags'] = ARP_FLAGS[block['Flags']]
            print(block)
            yblock = {x.replace(' ', ''): v for x, v in block.items()}
            yield yblock

class PromPush():
    """Prom Push class loops over"""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service=f"PromPush")
        self.logger.info("====== PromPush Start Work. Config: %s", self.backgConfig)

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
        postWebContentToURL(self.backgConfig['requestdict']['gateway'],
                            data=nodeOut.content, headers=headers)

    def __cleanRegistry(self):
        """Get new/clean prometheus registry."""
        registry = CollectorRegistry()
        return registry

    def __pushToGateway(self, registry):
        push_to_gateway(self.backgConfig['requestdict']['gateway'],
                        job=f"job-{self.backgConfig['id']}",
                        registry=registry)

    def arpPush(self):
        """Push ARP Output to Push Gateway"""
        registry = self.__cleanRegistry()
        arpState = Gauge('arp_state', 'ARP Address Table',
                         labelnames=['Device', 'Flags', 'HWaddress', 'HWtype', 'IPaddress', 'Mask'],
                         registry=registry)
        for arpEntry in _getArpVals():
            arpState.labels(**arpEntry).set(1)
        self.__pushToGateway(registry)

    def startwork(self):
        """Start Prometheus Push Daemon thread work"""
        if self.backgConfig['requestdict']['type'] == 'prometheus-push':
            self.nodeExporterPush()
        elif self.backgConfig['requestdict']['type'] == 'arp-push':
            self.arpPush()
        else:
            raise Exception(f"Unsupported push method. Submitted request: {self.backgConfig}")