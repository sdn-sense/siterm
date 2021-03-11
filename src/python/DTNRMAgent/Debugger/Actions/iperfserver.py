from DTNRMLibs.MainUtilities import externalCommand


def iperfserver(inputDict):
    """Run IPerf Server """
    # TODO Checks:
    # Port is not used
    # Use python library (iperf3 pip)
    command = "timeout %s iperf3 --server -p %s --bind %s %s" % (inputDict['time'], inputDict['port'], inputDict['ip'], '-1' if eval(inputDict['onetime']) else '')
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    return out.decode("utf-8"), err.decode("utf-8"), cmdOut.returncode

if __name__ == "__main__":
    testData = {'type': 'iperfserver', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'port': '1234', 'ip': '198.32.43.7', 'time': '10', 'onetime': 'True'}
    print(iperfserver(testData))
