#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Dell OS9 Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import re

class DellOS9():
    def __init__(self):
        self.factName = ['dellos9_facts', 'dellos9_command']
        self.regexs = [r'tagged (.+) (.+)', r'untagged (.+) (.+)', r'channel-member (.+) (.+)']

    @staticmethod
    def _getSystemValidPortName(port):
        """ get Systematic port name. MRML expects it without spaces """
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Same function is reused in main, and should be in other plugins.
        return port.replace(" ", "_").replace("/", "-")


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
                    self.logger.debug("UNSUPPORTED port name %s %s" % (portName, splPorts))
                    continue
                for i in range(int(start[vCh]), int(end[vCh]) + 1):
                    outPorts.append(self._getSystemValidPortName(apnd % i))
            else:
                outPorts.append(self._getSystemValidPortName("%s %s" % (portName, splRange[0])))
        return outPorts


    def _parseMembers(self, line):
        out = []
        for regex in self.regexs:
            match = re.search(regex, line)
            if match:
                out += self._portSplitter(match.group(1), match.group(2))
        return out

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
                        out[key].setdefault(line.split()[0], [])
                        out[key][line.split()[0]] += tmpOut
        return out


    def getinfo(self, ansibleOut):
        """
        Get info from ansible out, Mainly mac. Output example:
        Stack MAC                  : 4c:76:25:e8:44:c0
        Reload-Type                         : normal-reload [Next boot : normal-reload]

        --  Unit 1 --
        Unit Type                  : Management Unit
        Status                     : online
        Next Boot                  : online
        Required Type              : Z9100-ON - 34-port TE/TF/FO/FI/HU G (Z9100-ON)
        Current Type               : Z9100-ON - 34-port TE/TF/FO/FI/HU G (Z9100-ON)
        Master priority            : NA
        Hardware Rev               : 0.0
        Num Ports                  : 130
        Up Time                    : 4 wk, 6 day, 20 hr, 7 min
        Dell Networking OS Version : 9.11(0.0P6)
        Jumbo Capable              : yes
        POE Capable                : no
        FIPS Mode                  : disabled
        Burned In MAC              : 4c:76:25:e8:44:c0
        No Of MACs                 : 3
        """
        regexs = {'mac': r'^Stack MAC\s*:\s*(.+)'}
        out = {}
        for line in ansibleOut.split('\n'):
            for regName, regex in regexs.items():
                match = re.search(regex, line, re.M)
                if match:
                    out[regName] = match.group(1)
        return out

    def getlldpneighbors(self, ansibleOut):
        """
        Get all lldp neighbors. Each entry will contain:
         Local Interface Hu 1/1 has 1 neighbor
          Total Frames Out: 98232
          Total Frames In: 98349
          Total Neighbor information Age outs: 0
          Total Multiple Neighbors Detected: 0
          Total Frames Discarded: 0
          Total In Error Frames: 0
          Total Unrecognized TLVs: 0
          Total TLVs Discarded: 0
          Next packet will be sent after 7 seconds
          The neighbors are given below:
          -----------------------------------------------------------------------

            Remote Chassis ID Subtype: Mac address (4)
            Remote Chassis ID:  34:17:eb:4c:1e:80
            Remote Port Subtype:  Interface name (5)
            Remote Port ID:  hundredGigE 1/32
            Local Port ID: hundredGigE 1/1
            Locally assigned remote Neighbor Index: 2
            Remote TTL:  120
            Information valid for next 113 seconds
            Time since last information change of this neighbor:  2w2d16h
           ---------------------------------------------------------------------------
        """
        regexs = {'local_port_id': r'Local Port ID:\s*(.+)',
                  'remote_system_name': r'Remote System Name:\s*(.+)',
                  'remote_port_id': r'Remote Port ID:\s*(.+)',
                  'remote_chassis_id': r'Remote Chassis ID:\s*(.+)'}
        out = {}
        for entry in ansibleOut.split('========================================================================'):
            entryOut = {}
            for regName, regex in regexs.items():
                match = re.search(regex, entry, re.M)
                if match:
                    entryOut[regName] = match.group(1)
            if 'local_port_id' in entryOut:
                out[entryOut['local_port_id']] = entryOut
        return out

    def getIPv4Routing(self, ansibleOut):
        print('Called get getIPv4Routing. TODO')
        return {}

    def getIPv6Routing(self, ansibleOut):
        print('Called get getIPv6Routing. TODO')
        return {}

# TODO ROUTING PARSING - This is what I used with custom ssh parser
# Leaving it here if needed to re-use.
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