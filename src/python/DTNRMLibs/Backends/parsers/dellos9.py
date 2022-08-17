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
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.ipaddr import normalizedip

class DellOS9():
    """Dell OS 9 Parser"""
    def __init__(self, **kwargs):
        self.factName = ['dellemc.os9.os9_facts', 'dellemc.os9.os9_command']
        self.regexs = [r'^tagged (.+) (.+)', r'^untagged (.+) (.+)', r'^channel-member (.+) (.+)', r'^(Port-channel) (.+)']
        self.logger = getLoggingObject(config=kwargs['config'], service='SwitchBackends')

    @staticmethod
    def getSystemValidPortName(port):
        """Get Systematic port name. MRML expects it without spaces"""
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Also - sometimes lldp reports multiple quotes for interface name from ansible out
        for rpl in [[" ", "_"], ["/", "-"], ['"', ''], ["'", ""]]:
            port = port.replace(rpl[0], rpl[1])
        return port

    @staticmethod
    def _portSplitter(portName, inPorts):
        """Port splitter for dellos9"""
        def __identifyStep():
            if portName == 'fortyGigE':
                return 4
            return 1

        def rule0(reMatch):
            """Rule 0 to split ports to extended list
            INPUT: ('2,18-21,100,122', ',122', '122', '21')
            Split by comma, and loop:
              if no split - add to list
              if exists - split by dash and check if st < en
                every step is 1, 40G - is 4"""
            out = []
            for vals in reMatch[0].split(','):
                if '-' in vals:
                    stVal, enVal = vals.split('-')[0], vals.split('-')[1]
                    if int(stVal) > int(enVal):
                        #self.logger.debug('WARNING. Ignore this port (endVal > stVal): %s %s' % (portName, vals))
                        continue
                    for val in range(int(stVal), int(enVal)+1, __identifyStep()):
                        out.append(val)
                else:
                    out.append(int(vals))
            return out

        def rule1(reMatch):
            """Rule 1 to split ports to extended list
            INPUT: ('1/1-1/2,1/3,1/4,1/10-1/20', ',1/10-1/20', '1/10-1/20', '-1/20')
            Split by comma and loop:
            if no -, add to list
            if - exists - split by dash, split by / and identify which value is diff
            diff values check if st < en and push to looper;
            every step is 1, 40G - is 4"""
            out = []
            for vals in reMatch[0].split(','):
                if '-' in vals:
                    stVal, enVal = vals.split('-')[0].split('/'), vals.split('-')[1].split('/')
                    mod, modline = None, None
                    # If first digit not equal - replace first
                    if stVal[0] != enVal[0] and stVal[1] == enVal[1] and \
                       int(stVal[0]) < int(enVal[0]):
                        modline = "%%s/%s" % stVal[1]
                        mod = 0
                    # If second digit not equal - replace second
                    elif stVal[0] == enVal[0] and stVal[1] != enVal[1] and \
                         int(stVal[1]) < int(enVal[1]):
                        modline = "%s/%%s" % stVal[0]
                        mod = 1
                    if mod and modline:
                        for val in range(int(stVal[mod]), int(enVal[mod])+1, __identifyStep()):
                            out.append(modline % val)
                else:
                    out.append(vals)
            return out

        def rule2(reMatch):
            """Rule 2 to split ports to extended list
            INPUT ('0', '0-3,11-12,15,56,58-59', ',58-59', '58', '59')
            Split by comma and loop:
            if no -, add to list
            if - exists - split by dash, and check if st < en
            every step is 1, 40G - is 4"""
            out = []
            tmpOut = rule0(tuple([reMatch[1]]))
            for line in tmpOut:
                out.append(f"{reMatch[0]}/{line}")
            return out

        def rule3(reMatch):
            """Rule 3 to split ports to extended list
            INPUT ('1/6/1-1/8/1,1/9/1,1/10/1-1/20/1', ',1/10/1-1/20/1', '1/10/1', '1', '10', '1', '1/20/1', '1', '20', '1')
            Split by comma and loop:
            if no -, add to list
            if - exists - split by dash, split by / and identify which value is diff
            diff values check if st < en and push to looper;
            Here all step is 1, even 40G is 1;"""
            out = []
            for vals in reMatch[0].split(','):
                if '-' in vals:
                    stVal, enVal = vals.split('-')[0].split('/'), vals.split('-')[1].split('/')
                    mod, modline = None, None
                    # If first digit not equal - replace first
                    if stVal[0] != enVal[0] and stVal[1] == enVal[1] and \
                       stVal[2] == enVal[2] and int(stVal[0]) < int(enVal[0]):
                        modline = "%%s/%s/%s" % (stVal[1], stVal[2])
                        mod = 0
                    # If second digit not equal - replace second
                    elif stVal[0] == enVal[0] and stVal[1] != enVal[1] and \
                         stVal[2] == enVal[2] and int(stVal[1]) < int(enVal[1]):
                        modline = "%s/%%s/%s" % (stVal[0], stVal[2])
                        mod = 1
                    # If third digit not equal - replace third
                    elif stVal[0] == enVal[0] and stVal[1] == enVal[1] and \
                         stVal[2] != enVal[2] and int(stVal[2]) < int(enVal[2]):
                        modline = "%s/%s/%%s" % (stVal[0], stVal[1])
                        mod = 2
                    if mod and modline:
                        for val in range(int(stVal[mod]), int(enVal[mod])+1, 1):
                            out.append(modline % val)
                else:
                    out.append(vals)
            return out


        # Rule 0: Parses digit or digit group separated with dash.
        # Can be multiple separated by comma:
        match = re.match(r'((,*(\d{1,3}-*(\d{1,3})*))+)$', inPorts)
        if match:
            return rule0(match.groups())
        # Rule 1: Parses only this group below, can be multiple separated by comma:
        # 1/1
        # 1/1-1/2
        match = re.match(r'((,*(\d{1,3}/\d{1,3}(-\d{1,3}/\d{1,3})*))+)$', inPorts)
        if match:
            return rule1(match.groups())
        # Rule 2: 0/XX, where XX can be digit or 2 digits separated by dash.
        # Afterwards joint by comma, digit or 2 digits separated by dash:
        match = re.match(r'(\d{1,3})/((,*(\d{1,3})-*(\d{1,3})*)+)$', inPorts)
        if match:
            return rule2(match.groups())
        # Rule 3: Parses only this group below, can be multiple separated by comma:
        # 1/1/1
        # 1/7/1-1/8/1
        match = re.match(r'((,*((\d{1,3})/(\d{1,3})/(\d{1,3}))-*((\d{1,3})/(\d{1,3})/(\d{1,3}))*)+)$', inPorts)
        if match:
            return rule3(match.groups())

        # If we are here - raise WARNING, and continue. Return empty list
        #self.logger.debug('WARNING. Line %s %s NOT MATCHED' % (portName, inPorts))
        return []

    def _parseMembers(self, line):
        """Parse Members of port"""
        out = []
        for regex in self.regexs:
            match = re.search(regex, line)
            if match:
                tmpout = self._portSplitter(match.group(1), match.group(2))
                if not tmpout:
                    return out
                for item in tmpout:
                    out.append(self.getSystemValidPortName(f"{match.group(1)} {item}"))
        return out

    def parser(self, ansibleOut):
        """General Parser to parse ansible config"""
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

    @staticmethod
    def getinfo(ansibleOut):
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

    @staticmethod
    def getlldpneighbors(ansibleOut):
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

    @staticmethod
    def getIPv4Routing(ansibleOut):
        """Get IPv4 Routing from running config"""
        #self.logger.debug('Call ipv4 routing DellOS9')
        out = []
        for inline in ansibleOut.split('\n'):
            inline = inline.strip() # Remove all white spaces
            # Rule 0: Parses route like: ip route 0.0.0.0/0 192.168.255.254
            match = re.match(r'ip route (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}/\d{1,2}) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})$', inline)
            if match:
                out.append({'to': match.groups()[0], 'from': match.groups()[1]})
                continue
            # Rule 1: Parses route like: ip route vrf lhcone 0.0.0.0/0 192.84.86.242
            match = re.match(r'ip route vrf (\w+) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}/\d{1,2}) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': match.groups()[1], 'from': match.groups()[2]})
                continue
            # Rule 2: Parses route like: ip route vrf lhcone 192.84.86.0/24 NULL 0
            match = re.match(r'ip route vrf (\w+) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}/\d{1,2}) (\w+) (\w+)$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': match.groups()[1],
                            'intf': f"{match.groups()[2]} {match.groups()[3]}"})
                continue
            # Rule 3: Parses route like: ip route vrf lhcone 192.84.86.0/24 NULL 0 1.2.3.1
            match = re.match(r'ip route vrf (\w+) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3}/\d{1,2}) (\w+) (\w+) (\d{1,3}.\d{1,3}.\d{1,3}.\d{1,3})$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': match.groups()[1],
                            'intf': f"{match.groups()[2]} {match.groups()[3]}", 'from': match.groups()[4]})
        return out

    @staticmethod
    def getIPv6Routing(ansibleOut):
        """Get IPv6 Routing from running config"""
        #self.logger.debug('Call ipv6 routing DellOS9')
        out = []
        for inline in ansibleOut.split('\n'):
            inline = inline.strip() # Remove all white spaces
            # Rule 0: Matches ipv6 route 2605:d9c0:2:11::/64 fd00::3600:1
            match = re.match(r'ipv6 route ([abcdef0-9:]+/\d{1,3}) ([abcdef0-9:]+)$', inline)
            if match:
                out.append({'to': normalizedip(match.groups()[0]), 'from': normalizedip(match.groups()[1])})
                continue
            # Rule 1: Matches ipv6 route vrf lhcone ::/0 2605:d9c0:0:1::2
            match = re.match(r'ipv6 route vrf (\w+) ([abcdef0-9:]+/\d{1,3}) ([abcdef0-9:]+)$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': normalizedip(match.groups()[1]), 'from': normalizedip(match.groups()[2])})
                continue
            # Rule 2: Matches ipv6 route vrf lhcone 2605:d9c0::/32 NULL 0
            match = re.match(r'ipv6 route vrf (\w+) ([abcdef0-9:]+/\d{1,3}) (\w+) (\w+)$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': normalizedip(match.groups()[1]),
                            'intf': f"{match.groups()[2]} {match.groups()[3]}"})
                continue
            # Rule 3: Matches ipv6 route vrf lhcone 2605:d9c0::2/128 NULL 0 2605:d9c0:0:1::2
            match = re.match(r'ipv6 route vrf (\w+) ([abcdef0-9:]+/\d{1,3}) (\w+) (\w+) ([abcdef0-9:]+)$', inline)
            if match:
                out.append({'vrf': match.groups()[0], 'to': normalizedip(match.groups()[1]),
                            'intf': f"{match.groups()[2]} {match.groups()[3]}",
                            'from': normalizedip(match.groups()[4])})
        return out

MODULE = DellOS9
