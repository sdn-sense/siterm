from DTNRMLibs.MainUtilities import externalCommand


def rapidping(inputDict):
    """Return arptable for specific vlan"""
    # TODO Checks:
    # Interface is available;
    command = "ping -i 0.001 -w %s %s -s 1024 -I %s" % (inputDict['time'], inputDict['ip'], inputDict['interface'])
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    return out.decode("utf-8"), err.decode("utf-8"), cmdOut.returncode

if __name__ == "__main__":
    testData = {'type': 'rapidping', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'ip': '1.1.1.1', 'interface': 'vlan.3604', 'time': '60'}
    print(rapidping(testData))
