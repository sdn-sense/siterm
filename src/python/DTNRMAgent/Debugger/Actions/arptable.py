from DTNRMLibs.MainUtilities import externalCommand


def arptable(inputDict):
    """Return arptable for specific vlan"""
    command = "ip neigh"
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    retOut = []
    for line in out.decode("utf-8").split('\n'):
        splLine = line.split(' ')
        if len(splLine) > 4:
            if splLine[2] == inputDict['interface']:
                retOut.append(line)
    return retOut, err.decode("utf-8"), cmdOut.returncode

if __name__ == "__main__":
    testData = {'type': 'arptable', 'sitename': 'T2_US_Caltech_Test1', 'dtn': 'sdn-sc-nodea.ultralight.org', 'interface': 'vlan.3610'}
    print(arptable(testData))
