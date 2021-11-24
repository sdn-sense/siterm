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
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2021 California Institute of Technology
Date              : 2021/11/08
UpdateDate        : 2021/11/08
"""
import re

class DellOS9():
    def __init__(self):
        self.factName = 'dellos9_facts'
        self.regexs = [r'tagged (.+) (.+)', r'untagged (.+) (.+)', r'channel-member (.+) (.+)']


    def _portSplitter(self, portName, inPorts):
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
            splRange = splPorts.split('-')
            if len(splRange) == 2:
                start = splRange[0].split('/')
                end = splRange[1].split('/')
                vCh = 1  # Which value changes, usually it is 2nd, otherwise changed on intf Name
                apnd = ""
                if portName == "fortyGigE":
                    apnd = "fortyGigE %s/%%s/%s" % (start[0], start[2])
                elif portName == "hundredGigE":
                    apnd = "hundredGigE %s/%%s" % (start[0])
                elif portName == "Port-channel":
                    vCh = 0
                    apnd = "Port-channel %s"
                # 25G? TODO! - We do not have any of 25G
                # 10G? TODO! - SDN Testbed no 10G
                else:
                    print("UNSUPPORTED!")
                for i in range(int(start[vCh]), int(end[vCh]) + 1):
                    outPorts.append(apnd % i)
            else:
                outPorts.append("%s %s" % (portName, splRange[0]))
        return outPorts


    def _parseMembers(self, line):
        for regex in self.regexs:
            match = re.search(regex, line)
            if match:
                return self._portSplitter(match.group(1), match.group(2))

    def parser(self, ansibleOut):
        out = {}
        # Out must be {'<interface_name>': {'key': 'value'}} OR
        #             {'<interface_name>': {'key': ['value1', 'value2']}
        # dict as value are not supported (not found use case yet for this)
        interfaceSt = False
        for line in ansibleOut['event_data']['res']['ansible_facts']['ansible_net_config'].split('\n'):
            line = line.strip() # Remove all white spaces
            if line == "!" and interfaceSt:
                interfaceSt = False # This means interface ended!
            elif line.startswith('interface'):
                interfaceSt = True
                key = line[10:]
                out[key] = {}
            elif interfaceSt:
                if line.startswith('tagged') or line.startswith('untagged') or line.startswith('channel-member'):
                    tmpOut = self._parseMembers(line)
                    if tmpOut:
                        out[key][line.split()[0]] = tmpOut
        return out

# TODO ROUTING PARSING
# def parseRouteLine(splLine):
#     """
#     ip route 0.0.0.0/0 192.168.1.1
#     ipv6 route vrf lhcone ::/0 2600:dddd:0:ffff::
#     ip route vrf lhcone 0.0.0.0/0 192.1.1.1
#     ipv6 route vrf lhcone 2600:dddd:0::/48 NULL 0
#     """
#     tmpRoute = {}
#     tmpSplit = []
#     skip = False
#     for index, val in enumerate(splLine):
#         if skip:
#             skip = False
#         elif splLine[index] in ['vrf', 'weight', 'tag', 'distance']:
#             tmpRoute[val] = splLine[index+1]
#             skip = True
#         elif splLine[index] == 'permanent':
#             tmpRoute[val] = True
#         else:
#             tmpSplit.append(val)
#     valId = 0
#     if len(tmpSplit[valId].split('/')) == 2:
#         # Means it is with mask
#         tmpRoute['ip'] = tmpSplit[valId]
#         valId += 1
#     else:
#         tmpRoute['ip'] = "%s/%s" % (tmpSplit[valId], tmpSplit[valId+1])
#         valId += 2
#     tmpVal = tmpSplit[valId]
#     if validIPAddress(tmpVal) in ["IPv4", "IPv6"]:
#         tmpRoute['routerIP'] = tmpVal
#         valId += 1
#     else:
#         tmpRoute['routerIntf'] = "%s %s" % (tmpVal, tmpSplit[valId+1])
#         valId += 2
#     if tmpSplit[valId:]:
#         tmpRoute['unparsed'] = tmpSplit[valId:]
#     return tmpRoute




########################################
# It mainly produces output from Switch exactly
# what LookupService expects to receive to produce the MRML
# It also joins it with yaml file info, like isAlias, vlans.
# Required functions inside the Switch class:
# getInfo - this will be called by Lookup Service;
#   Same can be used, only important to rewrite
#    switchInfo function for Specific Switch<->LookupServiceOutput
########################################


# class Switch(DellOs9, mainCaller):
#     """
#     Dell Force10 Switch Plugin
#     """
#     def __init__(self, config, logger, nodesInfo, site):
#         super().__init__()
#         self.config = config
#         self.creds = {"creds": getSwitchLoginDetails(), "conns": {}}
#         self.sOut = {}
#         self.logger = logger
#         self.nodesInfo = nodesInfo
#         if not self.nodesInfo:
#             self.nodesInfo = {}
#         self.site = site
#         self.output = {'ports': {}, 'vlans': {}, 'routes': {}}
# 
#     def _setDefaults(self, switchName):
#         for key in self.output.keys():
#             self.output[key][switchName] = {}
# 
#     def getinfo(self, jOut={}, renew=False):
#         """Get info from Dell Switch plugin."""
#         # If config miss required options. return.
#         # See error message for more details.
#         if checkConfig(self.config, self.logger, self.site):
#             return self.output
#         if jOut:
#             self.nodesInfo = jOut
#         if checkConfig(self.config, self.logger, self.site):
#             return self.output
#         switch = self.config.get(self.site, 'switch')
#         for switchn in switch.split(','):
#             self.switchInfo(switchn, renew)
#             self.output['ports'][switchn] = self.sOut[switchn]['ports']
#             self.output['vlans'][switchn] = self.sOut[switchn]['vlans']
#             self.output['routes'][switchn] = self.sOut[switchn]['routes']
#         nodeInfo = Node(self.config, self.logger, self.site)
#         self.output = nodeInfo.nodeinfo(self.nodesInfo, self.output)
#         return self.output
# 
#     def getRunningConfig(self, switch):
#         if not switch in self.creds["conns"] or not self.creds["conns"][switch]:
#             self.creds["conns"][switch] = RemoteConn(self.creds["creds"][switch], self.logger, Force10)
#         out = self.creds["conns"][switch].sendCommand("%s%s" % (Force10.CMD_CONFIG, Force10.LT))
#         return self.parser(out)
# 
#     def getConfigParams(self, switch):
#         ports = []
#         vlanRange = ""
#         portsIgnore = []
#         if self.config.has_option(switch, 'allports') and self.config.get(switch, 'allports'):
#             ports = [*self.sOut[switch]['ports']]
#         elif self.config.has_option(switch, 'ports'):
#             ports = self.config.get(switch, 'ports').split(',')
#         if self.config.has_option(switch, 'vlan_range'):
#             vlanRange = self.config.get(switch, 'vlan_range')
#         if self.config.has_option(switch, 'ports_ignore'):
#             portsIgnore = self.config.get(switch, 'ports_ignore').split(',')
#         return ports, vlanRange, portsIgnore
# 
#     def switchInfo(self, switch, renew):
#         """Get all switch info from Switch Itself"""
#         self._setDefaults(switch)
#         if renew or not switch in self.sOut or not self.sOut[switch]:
#             self.sOut[switch] = self.getRunningConfig(switch)
# 
#         ports, defVlans, portsIgn = self.getConfigParams(switch)
#         portKey = "port_%s_%s"
#         for port in ports:
#             # Spaces from port name are replaced with _
#             # Backslashes are replaced with dash
#             # Also - mrml does not expect to get string in nml. so need to replace all
#             # Inside the output of dictionary
#             nportName = port.replace(" ", "_").replace("/", "-")
#             if port in portsIgn:
#                 del self.sOut[switch]['ports'][port]
#                 continue
#             self.sOut[switch]['ports'][nportName] =  self.sOut[switch]['ports'].pop(port)
#             for key in ['hostname', 'vlan_range', 'destport']:
#                 if not self.config.has_option(switch, portKey % (nportName, key)):
#                     continue
#                 self.sOut[switch]['ports'][nportName][key] = getValFromConfig(self.config, switch, nportName, key, portKey)
# 
#             tmpVal = 0
#             # Get port speed from config or if not defined - identify based on interface Name
#             if self.config.has_option(switch, portKey % (nportName, 'capacity')):
#                 tmpVal = getValFromConfig(self.config, switch, nportName, 'capacity', portKey)
#             else:
#                 # Identify port speed automatically
#                 tmpVal = identifyPortSpeed(self.sOut[switch]['ports'][nportName], nportName)
#             self.sOut[switch]['ports'][nportName]['capacity'] = tmpVal * 1000000000
# 
#             # Check if vlan range defined in config for specific port. if not - will use the default (also from config)
#             if self.config.has_option(switch, portKey % (nportName, 'vlan_range')):
#                 self.sOut[switch]['ports'][nportName]['vlan_range'] = getValFromConfig(self.config, switch, nportName, 'vlan_range', portKey)
#             else:
#                 self.sOut[switch]['ports'][nportName]['vlan_range'] = defVlans
# 
#             # if desttype defined (mainly to show switchport and reflect that in mrml) - add. Otherwise - check switch config
#             # and if switchport: True - define desttype
#             if self.config.has_option(switch, portKey % (nportName, 'desttype')):
#                 self.sOut[switch]['ports'][nportName]['desttype'] = getValFromConfig(self.config, switch, nportName, 'desttype', portKey)
#             elif 'switchport' in self.sOut[switch]['ports'][nportName].keys() and self.sOut[switch]['ports'][nportName]['switchport']:
#                 self.sOut[switch]['ports'][nportName]['desttype'] = 'switch'
# 
#             if self.config.has_option(switch, portKey % (nportName, 'isAlias')):
#                 self.sOut[switch]['ports'][nportName]['isAlias'] = getValFromConfig(self.config, switch, nportName, 'isAlias', portKey)
#                 spltAlias = self.sOut[switch]['ports'][nportName]['isAlias'].split(':')
#                 self.sOut[switch]['ports'][nportName]['desttype'] = 'switch'
#                 if 'destport' not in list(self.sOut[switch]['ports'][nportName].keys()):
#                     self.sOut[switch]['ports'][nportName]['destport'] = spltAlias[-1]
#                 if 'hostname' not in list(self.sOut[switch]['ports'][nportName].keys()):
#                     self.sOut[switch]['ports'][nportName]['hostname'] = spltAlias[-2]
# 
#             if port.startswith('Vlan'):
#                 self.sOut[switch]['vlans'][nportName] =  self.sOut[switch]['ports'].pop(nportName)
