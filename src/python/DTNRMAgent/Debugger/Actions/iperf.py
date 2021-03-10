from DTNRMLibs.MainUtilities import externalCommand


def iperf(inputDict):
    """Run TCP IPerf """
    # TODO Checks:
    # IP Is valid;
    # Ping works;
    # Telnet to default port works (5201)
    command = "iperf3 -c %s -B %s -t %s" % (inputDict['ip'], inputDict['interface'], inputDict['time'])
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    return out.decode("utf-8"), err.decode("utf-8"), cmdOut.returncode

if __name__ == "__main__":
    testData = {'type': 'iperf', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'ip': '1.2.3.4', 'interface': 'vlan.3604', 'time': '120'}
    print(iperf(testData))

