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
        if 'masklen' in inval and 'address' in inval:
            return "%s/%s" % (inval['address'], inval['masklen'])
    elif isinstance(inval, dict) and inkey == 'ipv6':
        subnet = 128
        if 'subnet' in inval:
            subnet = inval['subnet'].split('/')[-1]
        if 'address' in inval:
            return "%s/%s" % (inval['address'], subnet)
    elif isinstance(inval, dict):
        cls.logger.info('Out is dictionary, but vals unknown. Return as str %s' % inval)
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
        tmpKeys = [{'key': inkey, 'subkey': generateKey(cls, val, inkey), 'val': val} for val in inval]
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
        tmpKeys = [{'key': inkey, 'subkey': generateKey(cls, val, inkey), 'val': val} for val in inval]
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
        return _genIPv4(cls, inval, inkey)
    if inkey == 'ipv6':
        return _genIPv4(cls, inval, inkey)
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
                self.generateHostIsalias(portSwitch=portSwitch, switchName=switchName,
                                         portName=portName, newuri=newuri)
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

    def _addPort(self, uri, vsw, vlanuri=None, addToSite=True):
        if addToSite:
            self.newGraph.add((self.genUriRef('site'),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', uri)))
            self.newGraph.add((self.genUriRef('site', ':service+vsw:%s' % vsw),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', uri)))
        self.newGraph.add((self.genUriRef('site', uri),
                           self.genUriRef('rdf', 'type'),
                           self.genUriRef('nml', 'BidirectionalPort')))
        if vlanuri:
            self.newGraph.add((self.genUriRef('site', uri),
                               self.genUriRef('nml', 'hasBidirectionalPort'),
                               self.genUriRef('site', vlanuri)))
            self.newGraph.add((self.genUriRef('site', vlanuri),
                               self.genUriRef('rdf', 'type'),
                               self.genUriRef('nml', 'BidirectionalPort')))


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
                self._addPort(newuri, vsw)
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
# {'macaddress': '4c:76:25:e8:44:c2', 'lineprotocol': 'up', 'description': 'NDISE UCLA 211108',
# 'duplex': None, 'mediatype': None, 'mtu': 9214, 'operstatus': 'up', 'bandwidth': 40000, 'ipv4': None,
# 'type': None, 'tagged': ['fortyGigE_1-29-1', 'fortyGigE_1-30-1', 'hundredGigE_1-6', 'hundredGigE_1-7', 'hundredGigE_1-10',
# 'hundredGigE_1-22', 'hundredGigE_1-23', 'hundredGigE_1-27', 'hundredGigE_1-31', 'hundredGigE_1-32', 'Port-channel_101',
# 'Port-channel_102', 'Port-channel_111'], 'realportname': 'Vlan 2803', 'value': 2803, 'vlan_range': '1779-1799,3600-3619,3985-3989'}
                if 'tagged' in portSwitch:
                    for taggedIntf in portSwitch['tagged']:
                        newuri = ":%s:%s" % (switchName, taggedIntf)
                        self._addPort(newuri, vsw)
                        self._addPort(newuri, vsw, vlanuri, False)
                        self._addSwitchVlanLabel(vlanuri, portSwitch['value'])
                        #self._addIsAlias()


    def _addSwitchLldpInfo(self, switchInfo):
        """ TODO: ADD LLDP Info to MRML """
        return

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
