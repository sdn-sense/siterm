#!/usr/bin/env python3
"""
    Add Switch Info to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""

import configparser

def generateVal(cls, inval, inkey):
    if isinstance(inval, dict) and inkey == 'ipv4':
        return _genIPv4(cls, inval, inkey)
        #if 'masklen' in inval and 'address' in inval:
        #    return "%s/%s" % (inval['address'], inval['masklen'])
    elif isinstance(inval, dict) and inkey == 'ipv6':
        return _genIPv6(cls, inval, inkey)
        #subnet = 128
        #if 'subnet' in inval:
        #    subnet = inval['subnet'].split('/')[-1]
        #if 'address' in inval:
        #    return "%s/%s" % (inval['address'], subnet)
    if isinstance(inval, (dict, list)):
        cls.logger.info('Out is dictionary/list, but vals unknown. Return as str %s' % inval)
        return str(inval)
    if isinstance(inval, (int, float)):
        return inval
    if isinstance(inval, str):
        for call in [int, float]:
            try:
                return call(inval)
            except ValueError:
                continue
    return str(inval)

def _genIPv4(cls, inval, inkey):
    """
    Generate Interface IPv4 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 32
        if 'masklen' in inval:
            subnet = inval['masklen']
        if 'address' in inval:
            return "%s_%s" % (inval['address'], subnet)
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv4(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug('No IPv4 value. Return empty String. This might break things. Input: %s %s' % (inval, inkey))
    return ''

def _genIPv6(cls, inval, inkey):
    """
    Generate Interface IPv4 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 128 # Default we will use /128 just to secure code from diff ansible-switch outputs
        if 'subnet' in inval:
            subnet = inval['subnet'].split('/')[-1]
        if 'address' in inval:
            return "%s_%s" % (inval['address'].replace(':', '_').replace('/', '-'), subnet)
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv6(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug('No IPv4 value. Return empty String. This might break things. Input: %s %s' % (inval, inkey))
    return ''
#'ipv4': {'masklen': 0, 'address': '0.0.0.0'}, 'ipv6': {'subnet': 'fd01::/127', 'address': 'fd01::1'},
# {'masklen': 24, 'address': '10.1.0.1'}
# {'masklen': 25, 'address': '198.32.43.1'}

def generateKey(cls, inval, inkey):
    """ Generate keys for mrml and escape special charts """
    if isinstance(inval, str):
        return inval.replace(':', '_').replace('/', '-')
    if isinstance(inval, int):
        return str(inval)
    if inkey == 'ipv4':
        if not isinstance(inval, list):
            # Diff switches return differently. Make it always list in case dict
            # e.g. Dell OS 9 returns dict if 1 IP set, List if 2
            # Arista EOS always returns list.
            inval = [inval]
        return _genIPv4(cls, inval, inkey)
    if inkey == 'ipv6':
        if not isinstance(inval, list):
            # Diff switches return differently. Make it always list in case dict
            # e.g. Dell OS 9 returns dict if 1 IP set, List if 2
            # Arista EOS always returns list.
            inval = [inval]
        return _genIPv6(cls, inval, inkey)
    cls.logger.debug('Generate Keys return empty. Unexpected. Input: %s %s' % (inval, inkey))
    return ""

class SwitchInfo():
    """ Module for Switch Info add to MRML """
    # pylint: disable=E1101,W0201,E0203

    def _addVals(self, key, subkey, val, newuri):
        if not subkey:
            return
        val = generateVal(self, val, key)
        labeluri = '%s:%s' % (newuri, "%s+%s" % (key, subkey))
        reptype = key
        if key in ['ipv4', 'ipv6']:
            reptype = '%s-address' % key
            labeluri = '%s:%s' % (newuri, "%s-address+%s" % (key, subkey))
        self.addToGraph(['site', newuri],
                        ['mrs', 'hasNetworkAddress'],
                        ['site', labeluri])
        self.addToGraph(['site', labeluri],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', labeluri],
                        ['mrs', 'type'],
                        [reptype])
        self.addToGraph(['site', labeluri],
                        ['mrs', 'value'],
                        [val])

    def addSwitchIntfInfo(self, switchName, portName, portSwitch, newuri):
        """ Add switch info to mrml """
        for key, val in portSwitch.items():
            if not val:
                continue
            if key == 'vlan_range':
                self.addToGraph(['site', newuri],
                                ['nml', 'hasLabelGroup'],
                                ['site', '%s:%s' % (newuri, "vlan-range")])
                self.addToGraph(['site', '%s:%s' % (newuri, "vlan-range")],
                                ['rdf', 'type'],
                                ['nml', 'LabelGroup'])
                self.addToGraph(['site', "%s:%s" % (newuri, "vlan-range")],
                                ['nml', 'labeltype'],
                                ['schema', '#vlan'])
                self.addToGraph(['site', "%s:%s" % (newuri, "vlan-range")],
                                ['nml', 'values'],
                                [portSwitch['vlan_range']])
                # Generate host alias or adds' isAlias
                self._addIsAlias(newuri, portSwitch)
                continue
            if key == 'channel-member':
                for value in val:
                    switchuri = ":".join(newuri.split(':')[:-1])
                    self.addToGraph(['site', newuri],
                                    ['nml', 'hasBidirectionalPort'],
                                    ['site', '%s:%s' % (switchuri, self.switch._getSystemValidPortName(value))])
                continue
            if key in ['ipv4', 'ipv6', 'mac', 'macaddress', 'lineprotocol', 'operstatus', 'mtu']:
                subkey = generateKey(self, val, key)
                if isinstance(subkey, list):
                    for item in subkey:
                        self._addVals(item['key'], item['subkey'], item['val'], newuri)
                else:
                    self._addVals(key, subkey, val, newuri)

    def _addSwitchPortInfo(self, key, switchInfo):
        """ Add Switch Port Info for ports, vlans """
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug('Working on %s and %s' % (switchName, switchDict))
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            for portName, portSwitch in list(switchDict.items()):
                #if 'hostname' in portSwitch and 'isAlias' not in portSwitch:
                #    newuri = ":%s:%s:%s" % (switchName, portName, portSwitch['hostname'])
                #else:
                # This should come from the host itself. or we can add isAlias here.
                newuri = ":%s:%s" % (switchName, portName)
                self._addVswPort(switchName, portName, vsw)
                self.addSwitchIntfInfo(switchName, portName, portSwitch, newuri)

    def _addSwitchVlanLabel(self, vlanuri, value):
        labeluri = '%s:%s' % (vlanuri, "label+%s" % str(value))
        self.addToGraph(['site', vlanuri],
                        ['nml', 'hasLabel'],
                        ['site', labeluri])
        self.addToGraph(['site', labeluri],
                        ['rdf', 'type'],
                        ['nml', 'Label'])
        self.addToGraph(['site', labeluri],
                        ['nml', 'labeltype'],
                        ['schema', '#vlan'])
        self.addToGraph(['site', labeluri],
                        ['nml', 'value'],
                        [value])

    def _addSwitchVlanInfo(self, key, switchInfo):
        """ Add All Vlan Info from switch """
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug('Working on %s and %s' % (switchName, switchDict))
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue

            for portName, portSwitch in list(switchDict.items()):
                vlanuri = ":%s:%s:vlanport+%s" % (switchName, portName, portSwitch['value'])
                if 'vlan_range' in portSwitch:
                    # Vlan range for vlan - this is default coming from switch
                    # But for sure we dont want to add into model
                    del portSwitch['vlan_range']
                self.addSwitchIntfInfo(switchName, portName, portSwitch, vlanuri)
                if 'tagged' in portSwitch:
                    for taggedIntf in portSwitch['tagged']:
                        newuri = ":%s:%s" % (switchName, taggedIntf)
                        self._addVlanPort(switchName, taggedIntf, vsw, portSwitch['value'])
                        self._addSwitchVlanLabel(vlanuri, portSwitch['value'])
                        #self._addIsAlias()


    def _addSwitchLldpInfo(self, switchInfo):
        """ TODO: ADD LLDP Info to MRML """
        for hostname, macDict in switchInfo['info'].items():
            mac = "00:00:00:00:00:00"
            if 'mac' in macDict:
                mac = macDict['mac']
            else:
                continue
            for lldpHost, lldpDict in switchInfo['lldp'].items():
                if lldpHost == hostname:
                    # Loops? No way
                    continue
                for lldpIntf, intfDict in lldpDict.items():
                    if intfDict['remote_chassis_id'] == mac:
                        remoteuri = "%s:%s:%s" % (self.prefixes['site'], lldpHost, self.switch._getSystemValidPortName(lldpIntf))
                        localuri = "%s:%s:%s" % (self.prefixes['site'], hostname, self.switch._getSystemValidPortName(intfDict['remote_port_id']))
                        self._addIsAlias(remoteuri, {'isAlias': localuri})
                        self._addIsAlias(localuri, {'isAlias': remoteuri})
                        print(intfDict)
# (Pdb) pprint.pprint(switchInfo['lldp'])
# {'aristaeos_s0': {'Ethernet13/1': {'local_port_id': 'Ethernet13/1',
#                                    'remote_chassis_id': '4c:76:25:e8:44:c0',
#                                    'remote_port_id': '"hundredGigE 1/3"'},
#                   'Ethernet14/1': {'local_port_id': 'Ethernet14/1',
#                                    'remote_chassis_id': '4c:76:25:e8:44:c0',
#                                    'remote_port_id': '"hundredGigE 1/4"'},
#                   'Ethernet15/1': {'local_port_id': 'Ethernet15/1',
#                                    'remote_chassis_id': '4c:76:25:e8:44:c0',
#                                    'remote_port_id': '"hundredGigE 1/8"'},
#                   'Ethernet16/1': {'local_port_id': 'Ethernet16/1',
#                                    'remote_chassis_id': '4c:76:25:e8:44:c0',
#                                    'remote_port_id': '"hundredGigE 1/9"'},
#                   'Ethernet18/1': {'local_port_id': 'Ethernet18/1',
#                                    'remote_chassis_id': 'b8:59:9f:ed:29:fe',
#                                    'remote_port_id': 'enp33s0',
#                                    'remote_system_name': 'k8s-gen4-07.ultralight.org'},
#                   'Ethernet22/1': {'local_port_id': 'Ethernet22/1',
#                                    'remote_chassis_id': '3c:ec:ef:1c:90:00',
#                                    'remote_port_id': 'enp129s0f1',
#                                    'remote_system_name': 'sandie-7.ultralight.org'},
#                   'Ethernet29/1': {'local_port_id': 'Ethernet29/1',
#                                    'remote_chassis_id': 'b8:59:9f:ed:29:fe',
#                                    'remote_port_id': 'enp161s0',
#                                    'remote_system_name': 'k8s-gen4-07.ultralight.org'},
#                   'Ethernet31/1': {'local_port_id': 'Ethernet31/1',
#                                    'remote_chassis_id': '98:5d:82:03:3d:19',
#                                    'remote_port_id': '"Ethernet30/1"',
#                                    'remote_system_name': 'caltech-sc21-sw'},
#                   'Ethernet32/1': {'local_port_id': 'Ethernet32/1',
#                                    'remote_chassis_id': '98:5d:82:03:3d:19',
#                                    'remote_port_id': '"Ethernet29/1"',
#                                    'remote_system_name': 'caltech-sc21-sw'},
#                   'Management1': {'local_port_id': 'Management1',
#                                   'remote_chassis_id': '00:12:f2:86:20:80',
#                                   'remote_port_id': 'GigabitEthernet3',
#                                   'remote_system_name': 'lrt-sdn-r02-foundry-x448'}},
#  'dellos9_s0': {'ManagementEthernet 1/1': {'local_port_id': 'ManagementEthernet '
#                                                             '1/1',
#                                            'remote_chassis_id': '00:12:f2:86:20:80',
#                                            'remote_port_id': '00:12:f2:86:20:80',
#                                            'remote_system_name': 'lrt-sdn-r02-foundry-x448'},
#                 'fortyGigE 1/17/1': {'local_port_id': 'fortyGigE 1/17/1',
#                                      'remote_chassis_id': '00:01:e8:d7:72:f9',
#                                      'remote_port_id': 'fortyGigE 0/60'},
#                 'fortyGigE 1/18/1': {'local_port_id': 'fortyGigE 1/18/1',
#                                      'remote_chassis_id': '00:01:e8:d7:72:f9',
#                                      'remote_port_id': 'fortyGigE 0/52'},
#                 'fortyGigE 1/19/1': {'local_port_id': 'fortyGigE 1/19/1',
#                                      'remote_chassis_id': '00:01:e8:d7:72:f9',
#                                      'remote_port_id': 'fortyGigE 0/56'},
#                 'fortyGigE 1/20/1': {'local_port_id': 'fortyGigE 1/20/1',
#                                      'remote_chassis_id': '00:01:e8:d7:72:f9',
#                                      'remote_port_id': 'fortyGigE 0/48'},
#                 'fortyGigE 1/29/1': {'local_port_id': 'fortyGigE 1/29/1',
#                                      'remote_chassis_id': '00:25:90:7f:ff:3e',
#                                      'remote_port_id': '00:02:c9:21:4b:11',
#                                      'remote_system_name': 'sdn-dtn-2-09.ultralight.org'},
#                 'fortyGigE 1/30/1': {'local_port_id': 'fortyGigE 1/30/1',
#                                      'remote_chassis_id': '0c:c4:7a:fb:47:04',
#                                      'remote_port_id': '00:02:c9:a0:c4:e0',
#                                      'remote_system_name': 'sandie-3.ultralight.org'},
#                 'hundredGigE 1/1': {'local_port_id': 'hundredGigE 1/1',
#                                     'remote_chassis_id': '34:17:eb:4c:1e:80',
#                                     'remote_port_id': 'hundredGigE 1/32'},
#                 'hundredGigE 1/10': {'local_port_id': 'hundredGigE 1/10',
#                                      'remote_chassis_id': 'e4:1d:2d:fd:c4:cc',
#                                      'remote_port_id': 'e4:1d:2d:62:0c:66',
#                                      'remote_system_name': 'sandie-1.ultralight.org'},
#                 'hundredGigE 1/15': {'local_port_id': 'hundredGigE 1/15',
#                                      'remote_chassis_id': 'b8:59:9f:d1:34:aa',
#                                      'remote_port_id': 'etp14',
#                                      'remote_system_name': 'sonic'},
#                 'hundredGigE 1/16': {'local_port_id': 'hundredGigE 1/16',
#                                      'remote_chassis_id': 'b8:59:9f:d1:34:aa',
#                                      'remote_port_id': 'etp12',
#                                      'remote_system_name': 'sonic'},
#                 'hundredGigE 1/2': {'local_port_id': 'hundredGigE 1/2',
#                                     'remote_chassis_id': '34:17:eb:4c:1e:80',
#                                     'remote_port_id': 'hundredGigE 1/31'},
#                 'hundredGigE 1/23': {'local_port_id': 'hundredGigE 1/23',
#                                      'remote_chassis_id': 'e4:1d:2d:fd:c4:d0',
#                                      'remote_port_id': 'e4:1d:2d:fd:c4:dc',
#                                      'remote_system_name': 'sdn-dtn-1-7.ultralight.org'},
#                 'hundredGigE 1/24': {'local_port_id': 'hundredGigE 1/24',
#                                      'remote_chassis_id': 'b8:59:9f:ed:29:fe',
#                                      'remote_port_id': '24:8a:07:9c:00:af',
#                                      'remote_system_name': 'k8s-gen4-07.ultralight.org'},
#                 'hundredGigE 1/27': {'local_port_id': 'hundredGigE 1/27',
#                                      'remote_chassis_id': '0c:c4:7a:69:22:ca',
#                                      'remote_port_id': '24:8a:07:9c:02:be',
#                                      'remote_system_name': 'sdn-dtn-2-11.ultralight.org'},
#                 'hundredGigE 1/3': {'local_port_id': 'hundredGigE 1/3',
#                                     'remote_chassis_id': '44:4c:a8:55:2c:dd',
#                                     'remote_port_id': 'Ethernet13/1',
#                                     'remote_system_name': '7060cx-r1'},
#                 'hundredGigE 1/31': {'local_port_id': 'hundredGigE 1/31',
#                                      'remote_chassis_id': '0c:c4:7a:68:5f:70',
#                                      'remote_port_id': '24:8a:07:9c:02:1e',
#                                      'remote_system_name': 'sdn-dtn-2-10.ultralight.org'},
#                 'hundredGigE 1/32': {'local_port_id': 'hundredGigE 1/32',
#                                      'remote_chassis_id': '3c:ec:ef:1c:90:00',
#                                      'remote_port_id': 'ec:0d:9a:c1:ba:60',
#                                      'remote_system_name': 'sandie-7.ultralight.org'},
#                 'hundredGigE 1/4': {'local_port_id': 'hundredGigE 1/4',
#                                     'remote_chassis_id': '44:4c:a8:55:2c:dd',
#                                     'remote_port_id': 'Ethernet14/1',
#                                     'remote_system_name': '7060cx-r1'},
#                 'hundredGigE 1/5': {'local_port_id': 'hundredGigE 1/5',
#                                     'remote_chassis_id': '0c:c4:7a:d9:b4:8c',
#                                     'remote_port_id': 'ec:0d:9a:92:b2:36',
#                                     'remote_system_name': 'k8s-nvme-01.ultralight.org'},
#                 'hundredGigE 1/6': {'local_port_id': 'hundredGigE 1/6',
#                                     'remote_chassis_id': '24:8a:07:55:29:cc',
#                                     'remote_port_id': '24:8a:07:55:29:cc'},
#                 'hundredGigE 1/7': {'local_port_id': 'hundredGigE 1/7',
#                                     'remote_chassis_id': '54:bf:64:e5:aa:c1',
#                                     'remote_port_id': 'hundredGigE 1/2'},
#                 'hundredGigE 1/8': {'local_port_id': 'hundredGigE 1/8',
#                                     'remote_chassis_id': '44:4c:a8:55:2c:dd',
#                                     'remote_port_id': 'Ethernet15/1',
#                                     'remote_system_name': '7060cx-r1'},
#                 'hundredGigE 1/9': {'local_port_id': 'hundredGigE 1/9',
#                                     'remote_chassis_id': '44:4c:a8:55:2c:dd',
#                                     'remote_port_id': 'Ethernet16/1',
#                                     'remote_system_name': '7060cx-r1'}}}
# 
# pprint.pprint(switchInfo['info'])
# {'aristaeos_s0': {'mac': '44:4c:a8:55:2c:dd'},
#  'dellos9_s0': {'mac': '4c:76:25:e8:44:c0'}}


    def _addSwitchRoutes(self, switchInfo):
        """ TODO: Add Route info to MRML """
        return

    def addSwitchInfo(self):
        """Add All Switch information from switch Backends plugin."""
        # Get switch information...
        switchInfo = self.switch.getinfo(self.renewSwitchConfig)
        # Add Switch information to MRML
        self._addSwitchPortInfo('ports', switchInfo)
        self._addSwitchVlanInfo('vlans', switchInfo)
        self._addSwitchLldpInfo(switchInfo)
        self._addSwitchRoutes(switchInfo)
