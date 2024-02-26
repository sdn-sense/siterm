#!/usr/bin/env python3
"""
Title                   : siterm
Author                  : Justas Balcas
Email                   : juztas (at) gmail (dot) com
@Copyright              : Copyright (C) 2024 Justas Balcas
Date                    : 2024/02/26
"""
import asyncio.exceptions
import pyshark
from SiteRMLibs.MainUtilities import getLoggingObject
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


class TCPDump():
    """TCP Dump class. Run TCP Dump."""
    def __init__(self, config, sitename, backgConfig):
        self.config = config
        self.sitename = sitename
        self.backgConfig = backgConfig
        self.logger = getLoggingObject(config=self.config, service="TCPDump")
        self.logger.info("====== TCPDump Start Work. Config: %s", self.backgConfig)

    def refreshthread(self, *_args):
        """Call to refresh thread for this specific class and reset parameters"""
        self.logger.warning("NOT IMPLEMENTED call {self.backgConfig} to refresh thread")

    def startwork(self):
        """Do TCP Dump"""
        if self.backgConfig['interface'] not in getInterfaces():
            return [], "Interface is not available on the node", 3
        parser = ParsePackets()
        allPackets = parser.sniff(self.backgConfig)
        err, exitCode = "", 0
        if not allPackets:
            err = "No packets were captured during 60 second capture time"
            exitCode = 502
        return allPackets, err, exitCode
