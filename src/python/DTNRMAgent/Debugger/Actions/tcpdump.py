#!/usr/bin/env python3
"""
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
Email                   : jbalcas (at) caltech (dot) edu
@Copyright              : Copyright (C) 2021 California Institute of Technology
Date                    : 2021/03/12
"""
from asyncio.exceptions import TimeoutError
import pyshark


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
        except TimeoutError:
            pass
        capture.clear()
        capture.close()
        return self.out


def tcpdump(inputDict):
    """Do TCP Dump"""
    # TODO Check
    # Interface exists
    parser = ParsePackets()
    allPackets = parser.sniff(inputDict)
    err, exitCode = "", 0
    if not allPackets:
        err = "No packets were captured during 60 second capture time"
        exitCode = 502
    return allPackets, err, exitCode

if __name__ == "__main__":
    testData = {'type': 'tcpdump', 'sitename': 'T2_US_Caltech_Test1',
                'dtn': 'sdn-sc-nodea.ultralight.org', 'interface': 'enp4s0f0.43'}
    print(tcpdump(testData))
