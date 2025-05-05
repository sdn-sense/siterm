#!/usr/bin/env python3
# pylint: disable=E1101
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
import asyncio.exceptions
import pyshark
from SiteRMLibs.BaseDebugAction import BaseDebugAction
from SiteRMLibs.ipaddr import getInterfaces

class ParsePackets():
    """Packet Parser"""
    def __init__(self):
        self.out = []
        self.stored = 0

    def packetProcess(self, pkt):
        """Directive for each received packet."""
        if self.stored <= 100:
            tlayer, hlayer = pkt.transport_layer, pkt.highest_layer
            packet = str(pkt)
            self.out.append([self.stored, tlayer, hlayer, packet])
            self.stored += 1

    def sniff(self, inputDict):
        """Sniff packets on interface for 30 seconds."""
        self.stored = 0
        capture = pyshark.LiveCapture(interface=inputDict['interface'])
        try:
            capture.apply_on_packets(self.packetProcess, timeout=30)
        except asyncio.exceptions.TimeoutError:
            pass
        capture.clear()
        capture.close()
        return self.out


class TCPDump(BaseDebugAction):
    """TCP Dump class. Run TCP Dump."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.requestdict = backgConfig.get('requestdict', {})
        self.service = "TCPDump"
        super().__init__()

    def main(self):
        """Do TCP Dump"""
        if self.requestdict['interface'] not in getInterfaces():
            self.logMessage("Interface is not available on the node")
            return
        parser = ParsePackets()
        allPackets = parser.sniff(self.requestdict)
        if not allPackets:
            self.logMessage("No packets captured")
        self.jsonout['output'] = allPackets
        self.jsonout['exitCode'] = 0
