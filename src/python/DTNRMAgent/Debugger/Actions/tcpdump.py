import pyshark
import json

def tcpdump(inputDict):
    # TODO Check
    # Interface exists
    capture = pyshark.LiveCapture(interface=inputDict['interface'])
    capture.sniff(timeout=30)
    count, max = 0, 100
    out, err, exitCode = [], "", 0
    max = len(capture) if len(capture) < max else 100
    if not capture:
        err = "No packets were captured during 60 second capture time"
        exitCode = 502
    else:
        for cap in capture:
            tlayer, hlayer = cap.transport_layer, cap.highest_layer
            packet = str(cap)
            out.append([count, tlayer, hlayer, packet])
            count += 1
            if count  >= max:
                break
    capture.clear()
    capture.close()
    return out, err, exitCode

if __name__ == "__main__":
    testData = {'type': 'tcpdump', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'interface': 'enp4s0f0.43'}
    print(tcpdump(testData))
