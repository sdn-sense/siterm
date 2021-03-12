import pyshark
import json
import concurrent.futures._base


class ParsePackets():
    def __init__(self):
        self.out = []
        self.stored = 0

    def Packet_Process(self, pkt):
        """Directive for each received packet."""
        if self.stored <= 100:
            tlayer, hlayer = pkt.transport_layer, pkt.highest_layer
            packet = str(pkt)
            self.out.append([self.stored, tlayer, hlayer, packet])
            self.stored += 1


    def sniff(self, inputDict):
        self.stored = 0
        capture = pyshark.LiveCapture(interface=inputDict['interface'])
        try:
            for packet in capture.apply_on_packets(self.Packet_Process,timeout=10):
                allPackets.append(packet)
        except concurrent.futures._base.TimeoutError:
            pass
        capture.clear()
        capture.close()
        return self.out


def tcpdump(inputDict):
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
    testData = {'type': 'tcpdump', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'interface': 'enp4s0f0.43'}
    print(tcpdump(testData))
