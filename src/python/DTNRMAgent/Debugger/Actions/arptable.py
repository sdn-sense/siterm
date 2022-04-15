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


def arptable(inputDict):
    """Return arptable for specific vlan"""
    command = "ip neigh"
    cmdOut = externalCommand(command, False)
    out, err = cmdOut.communicate()
    retOut = []
    for line in out.decode("utf-8").split("\n"):
        splLine = line.split(" ")
        if len(splLine) > 4 and splLine[2] == inputDict["interface"]:
            retOut.append(line)
    return retOut, err.decode("utf-8"), cmdOut.returncode


if __name__ == "__main__":
    testData = {
        "type": "arptable",
        "sitename": "T2_US_Caltech_Test1",
        "dtn": "sdn-sc-nodea.ultralight.org",
        "interface": "vlan.3610",
    }
    print(arptable(testData))
