#!/usr/bin/env python3
"""
    Info comes from switch. yaml has only basic info, like:
    s0: # Switch name
      vsw: s0 # VirtualSwitchingName
      ports:
        - 'hundredGigE 1/15'
        - 'hundredGigE 1/16'
      allports: True # if True - ports list is ignored and all are added;
      port1_1vlan_range: '1000-2000' # spaces in port name replaced with _
      vlans: '1000-1010,2000-2010' # default vlans if port<Intf_name>vlan_range not defined;
      port1_1isAlias: 'urn:ogf:network:lsanca...'

    Security configs (IP, Username, Password) come from secrets and is not stored
    in any form of database.

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
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2021 California Institute of Technology
Date              : 2021/11/08
UpdateDate        : 2021/11/08
"""
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.Backends.generalFunctions import getValFromConfig
from DTNRMLibs.Backends.generalFunctions import validIPAddress
from DTNRMLibs.Backends.Commands import Force10
from DTNRMLibs.RemoteConn import RemoteConn
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger, getSwitchLoginDetails

# =======================
#  Functions for parsing Force10 config
# =======================
def getIntfName(inLine):
    """ Get Interface Name """
    return " ".join(inLine.split(" ")[1:])

def portSplitter(portName, inPorts):
    """ Port splitter for dellos9
    example:
     tagged fortyGigE 1/29/1-1/30/1
     tagged hundredGigE 1/6,1/10,1/22-1/23,1/27,1/31-1/32
     tagged Port-channel 101-102
     untagged fortyGigE 1/21/1
     untagged hundredGigE 1/5,1/24
    """
    outPorts = []
    for splPorts in inPorts.split(','):
        print(splPorts)
        splRange = splPorts.split('-')
        print(splRange)
        if len(splRange) == 2:
            start = splRange[0].split('/')
            end = splRange[1].split('/')
            vCh = 1  # Which value changes, usually it is 2nd, otherwise changed on intf Name
            apnd = ""
            if portName == "fortyGigE":
                apnd = "%s/%%s/%s" % (start[0], start[2])
            elif portName == "hundredGigE":
                apnd = "%s/%%s" % (start[0])
            elif portName == "Port-channel":
                vCh = 0
                apnd = "%s"
            else:
                print("UNSUPPORTED!")
            for i in range(int(start[vCh]), int(end[vCh]) + 1):
                outPorts.append(apnd % i)
        else:
            outPorts.append(splRange[0])
    return outPorts

def parseRouteLine(splLine):
    """
    ip route 0.0.0.0/0 192.168.1.1
    ipv6 route vrf lhcone ::/0 2600:dddd:0:ffff::
    ip route vrf lhcone 0.0.0.0/0 192.1.1.1
    ipv6 route vrf lhcone 2600:dddd:0::/48 NULL 0
    """
    tmpRoute = {}
    tmpSplit = []
    skip = False
    for index, val in enumerate(splLine):
        if skip:
            skip = False
        elif splLine[index] in ['vrf', 'weight', 'tag', 'distance']:
            tmpRoute[val] = splLine[index+1]
            skip = True
        elif splLine[index] == 'permanent':
            tmpRoute[val] = True
        else:
            tmpSplit.append(val)
    valId = 0
    if len(tmpSplit[valId].split('/')) == 2:
        # Means it is with mask
        tmpRoute['ip'] = tmpSplit[valId]
        valId += 1
    else:
        tmpRoute['ip'] = "%s/%s" % (tmpSplit[valId], tmpSplit[valId+1])
        valId += 2
    tmpVal = tmpSplit[valId]
    print(tmpVal)
    if validIPAddress(tmpVal) in ["IPv4", "IPv6"]:
        tmpRoute['routerIP'] = tmpVal
        valId += 1
    else:
        tmpRoute['routerIntf'] = "%s %s" % (tmpVal, tmpSplit[valId+1])
        valId += 2
    if tmpSplit[valId:]:
        tmpRoute['unparsed'] = tmpSplit[valId:]
    return tmpRoute

# =======================
#  Main caller - calls are done only by Provisioning Service
# =======================

class mainCaller():
    """ Main caller """
    def mainCall(self, stateCall, inputDict, actionState):
        """Main caller function which calls specific state."""
        out = {}
        if stateCall == 'accepting':
            out = self.accepting(inputDict, actionState)
        elif stateCall == 'accepted':
            out = self.accepted(inputDict, actionState)
        elif stateCall == 'committing':
            out = self.committing(inputDict, actionState)
        elif stateCall == 'committed':
            out = self.committed(inputDict, actionState)
        elif stateCall == 'activating':
            out = self.activating(inputDict, actionState)
        elif stateCall == 'active':
            out = self.active(inputDict, actionState)
        elif stateCall == 'activated':
            out = self.activated(inputDict, actionState)
        elif stateCall == 'failed':
            out = self.failed(inputDict, actionState)
        elif stateCall == 'remove':
            out = self.remove(inputDict, actionState)
        else:
            raise Exception('Unknown State %s' % stateCall)
        return out

    def accepting(self, inputDict, actionState):
        """Accepting state actions."""
        return True

    def accepted(self, inputDict, actionState):
        """Accepted state actions."""
        return True

    def committing(self, inputDict, actionState):
        """Committing state actions."""
        return True

    def committed(self, inputDict, actionState):
        """Committed state actions."""
        return True

    def activating(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def active(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def activated(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def failed(self, inputDict, actionState):
        """Failed state actions."""
        return True

    def remove(self, inputDict, actionState):
        """Remove state actions."""
        return True

########################################
# Specific configuration parser for Dell Force 10
# It parses switch config to a json format.
# Tested on Z9100
# It only get's all which start by:
# interface *
# ip route *
# ipv6 route *
########################################

class DellOs9():
    """ Dell 9 config parser """
    def __init__(self):
        super().__init__()
        self.jsonOut = {'ports': {}, 'routes': {}}

    def _clean(self):
        self.jsonOut = {'ports': {}, 'routes': {}}

    def getMappedInterfaces(self, inLine, intfName):
        """ Get all Mapped interfaces """
        splLine = inLine.split(" ")
        portType = splLine[0]
        if portType == '!untagged':
            portType = 'untagged'
        portName = splLine[1]
        self.jsonOut['ports'][intfName].setdefault(portType, {})
        self.jsonOut['ports'][intfName][portType].setdefault(portName, [])
        nPorts = portSplitter(portName, splLine[2])
        self.jsonOut['ports'][intfName][portType][portName] = nPorts

    def parseIntfLine(self, inLine, intfName):
        """ Parse Intf Line """
        print(inLine)
        if inLine == 'no shutdown':
            self.jsonOut['ports'][intfName]['shutdown'] = False
        elif inLine == 'shutdown':
            self.jsonOut['ports'][intfName]['shutdown'] = True
        elif inLine == 'no ip address':
            self.jsonOut['ports'][intfName]['ipv4_address'] = None
        elif inLine == 'switchport':
            self.jsonOut['ports'][intfName]['switchport'] = True
        elif inLine == 'no switchport':
            self.jsonOut['ports'][intfName]['switchport'] = False
        elif inLine.startswith('ip address'):
            self.jsonOut['ports'][intfName]['ipv4_address'] = inLine[len('ip address '):]
        elif inLine == 'no ipv6 address':
            # Does it have this statement at all?
            self.jsonOut['ports'][intfName]['ipv6_address'] = None
        elif inLine.startswith('ipv6 address'):
            self.jsonOut['ports'][intfName]['ipv6_address'] = inLine[len('ipv6 address '):]
        elif inLine.startswith('tagged') or inLine.startswith('untagged') \
             or inLine.startswith('!untagged') or inLine.startswith('channel-member'):
            self.getMappedInterfaces(inLine, intfName)
        elif inLine.startswith('no '):
            key = inLine.split(' ')[1]
            self.jsonOut['ports'][intfName][key] = False
        else:
            key = inLine.split(' ')[0]
            self.jsonOut['ports'][intfName][key] = inLine[len(key)+1:]
        return inLine

    def parser(self, inputLines):
        """ Parse file, out json"""
        self._clean()
        intfName = ""
        saveOut = False
        for line in inputLines:
            line = line.strip()
            if line == "!":
                saveOut = False
            if saveOut:
                self.parseIntfLine(line, intfName)
            elif line.startswith('interface'):
                saveOut = True
                intfName = getIntfName(line)
                self.jsonOut['ports'].setdefault(intfName, {})
            elif line.startswith('ip route') or line.startswith('ipv6 route'):
                splLine = line.split(' ')
                self.jsonOut['routes'].setdefault(splLine[0], [])
                self.jsonOut['routes'][splLine[0]].append(parseRouteLine(splLine[2:]))



########################################
# It mainly produces output from Switch exactly
# what LookupService expects to receive to produce the MRML
# It also joins it with yaml file info, like isAlias, vlans.
# Required functions inside the Switch class:
# getInfo - this will be called by Lookup Service;
#   Same can be used, only important to rewrite
#    switchInfo function for Specific Switch<->LookupServiceOutput
########################################


class Switch(DellOs9, mainCaller):
    """
    Dell Force10 Switch Plugin
    """
    def __init__(self, config, logger, nodesInfo, site):
        super().__init__()
        self.config = config
        self.creds = {"creds": getSwitchLoginDetails(), "conns": {}}
        self.sOut = {}
        self.logger = logger
        self.nodesInfo = nodesInfo
        if not self.nodesInfo:
            self.nodesInfo = {}
        self.site = site
        self.output = {'switches': {}, 'ports': {}, 'vlans': {}, 'routes': {}}

    def _setDefaults(self, switchName):
        for key in self.output.keys():
            self.output[key][switchName] = {}

    def getinfo(self, renew=False):
        """Get info from Dell Switch plugin."""
        # If config miss required options. return.
        # See error message for more details.
        if checkConfig(self.config, self.logger, self.site):
            return self.output
        switch = self.config.get(self.site, 'switch')
        for switchn in switch.split(','):
            self.switchInfo(switchn, renew)
        nodeInfo = Node(self.config, self.logger, self.site)
        self.output = nodeInfo.nodeinfo(self.nodesInfo, self.output)
        return cleanupEmpty(self.output)

    def getRunningConfig(self, switch):
        if not switch in self.creds["conns"] or not self.creds["conns"][switch]:
            self.creds["conns"][switch] = RemoteConn(self.creds["creds"][switch], self.logger, Force10)
        out = self.creds["conns"][switch].sendCommand("%s%s" % (Force10.CMD_CONFIG, Force10.LT))
        return out

    def switchInfo(self, switch, renew):
        """Get all switch info from Switch Itself"""
        self._setDefaults(switch)
        if renew or not switch in self.sOut or not self.sOut[switch]:
            self.sOut[switch] = self.getRunningConfig(switch)
        # TODO !!!
        for port in self.config.get(switch, 'ports').split(','):
            # Each port has to have 4 things defined:
            self.output['ports'][switch][port] = {}
            for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
                if not self.config.has_option(switch, "port%s%s" % (port, key)):
                    self.logger.debug('Option %s is not defined for Switch %s and Port %s' % (key, switch, port))
                    continue
                tmpVal = getValFromConfig(self.config, switch, port, key)
                if key == 'capacity':
                    # TODO. Allow in future to specify in terms of G,M,B. For now only G
                    # and we change it to bits
                    self.output['ports'][switch][port][key] = tmpVal * 1000000000
                else:
                    self.output['ports'][switch][port][key] = tmpVal
            self.output['switches'][switch][port] = ""
            if self.config.has_option(switch, "port%shostname" % port):
                self.output['switches'][switch][port] = getValFromConfig(self.config, switch, port, 'hostname')
            elif self.config.has_option(switch, "port%sisAlias" % port):
                spltAlias = getValFromConfig(self.config, switch, port, 'isAlias').split(':')
                #self.output['switches'][switch][port] = spltAlias[-2]
                self.output['ports'][switch][port]['desttype'] = 'switch'
                if 'destport' not in list(self.output['ports'][switch][port].keys()):
                    self.output['ports'][switch][port]['destport'] = spltAlias[-1]
                if 'hostname' not in list(self.output['ports'][switch][port].keys()):
                    self.output['ports'][switch][port]['hostname'] = spltAlias[-2]

if __name__ == '__main__':
    print('WARNING!!!! This should not be used through main call. Only for testing purposes!!!')
    CONFIG = getConfig()
    COMPONENT = 'LookUpService'
    LOGGER = getStreamLogger()
    for sitename in CONFIG.get('general', 'sites').split(','):
        print('Working on %s' % sitename)
        method = Switch(CONFIG, LOGGER, None, sitename)
        print(method.getinfo())
