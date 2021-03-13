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
    testData = {'type': 'rapidping', 'sitename': 'T2_US_Caltech_Test1',
                'dtn': 'sdn-sc-nodea.ultralight.org', 'ip': '1.1.1.1',
                'interface': 'vlan.3604', 'time': '60'}
    print(rapidping(testData))
