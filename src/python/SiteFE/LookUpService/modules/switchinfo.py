#!/usr/bin/env python3
"""
    Add Switch Info to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import configparser
from DTNRMLibs.ipaddr import validMRMLName


def generateVal(cls, inval, inkey, esc=False):
    """Generate mrml valid val/key for ipv4/ipv6"""
    if isinstance(inval, dict) and inkey == 'ipv4':
        return _genIPv4(cls, inval, inkey, esc)
    if isinstance(inval, dict) and inkey == 'ipv6':
        return _genIPv6(cls, inval, inkey, esc)
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

def _genIPv4(cls, inval, inkey, esc=True):
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
            if esc:
                return validMRMLName("%s/%s" % (inval['address'], subnet))
            return "%s/%s" % (inval['address'], subnet)
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv4(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug('No IPv4 value. Return empty String. This might break things. Input: %s %s' % (inval, inkey))
    return ''

def _genIPv6(cls, inval, inkey, esc=True):
    """
    Generate Interface IPv6 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 128 # Default we will use /128 just to secure code from diff ansible-switch outputs
        if 'subnet' in inval:
            subnet = inval['subnet'].split('/')[-1]
        if 'address' in inval:
            if esc:
                return validMRMLName("%s/%s" % (inval['address'], subnet))
            return "%s/%s" % (inval['address'], subnet)
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv6(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug('No IPv6 value. Return empty String. This might break things. Input: %s %s' % (inval, inkey))
    return ''

def generateKey(cls, inval, inkey):
    """Generate keys for mrml and escape special charts"""
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
    """Module for Switch Info add to MRML"""
    # pylint: disable=E1101,W0201,E0203

    def _addVals(self, key, subkey, val, newuri):
        if not subkey:
            return
        val = generateVal(self, val, key, False)
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
        """Add switch info to mrml"""
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
                self._addIsAlias(uri=newuri, isAlias=portSwitch.get('isAlias'), hostname=switchName, portName=portName)
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
        """Add Switch Port Info for ports, vlans"""
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug('Working on1 %s' % switchName)
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            try:
                rst = self.config.get(switchName, 'rst')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                rst = False
            for portName, portSwitch in list(switchDict.items()):
                newuri = ":%s:%s" % (switchName, portName)
                self._addVswPort(hostname=switchName, portName=portName, vsw=vsw)
                self.addSwitchIntfInfo(switchName, portName, portSwitch, newuri)
                if rst:
                    self._addAddressPool(newuri)

    def _addSwitchVlanLabel(self, vlanuri, value):
        """Add Switch Vlan Label"""
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
        """Add All Vlan Info from switch"""
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug('Working on %s' % switchName)
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue

            for portName, portSwitch in list(switchDict.items()):
                if 'tagged' not in portSwitch:
                    # TODO: LOG LINE
                    continue
                for taggedIntf in portSwitch['tagged']:
                    vlanuri = self._addVlanPort(hostname=switchName, portName=taggedIntf, vsw=vsw, vtype='vlanport', vlan=portSwitch['value'])
                    self._addSwitchVlanLabel(vlanuri, portSwitch['value'])
                    if 'vlan_range' in portSwitch:
                        # Vlan range for vlan - this is default coming from switch yaml conf
                        # But for sure we dont want to add into model
                        del portSwitch['vlan_range']
                    self.addSwitchIntfInfo(switchName, portName, portSwitch, vlanuri)


    def _addSwitchLldpInfo(self, switchInfo):
        """ADD LLDP Info to MRML"""
        for hostname, macDict in switchInfo['info'].items():
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
                        localuri = ":%s:%s" % (hostname, self.switch._getSystemValidPortName(intfDict['remote_port_id']))
                        self._addIsAlias(uri=localuri, isAlias=remoteuri)

    def _addAddressPool(self, uri):
        """Add Address Pools"""
        for key in ['ipv4-address-pool', 'ipv6-address-pool']:
            tmp = self.__getValFromConfig(key)
            if tmp:
                self._addNetworkAddress(uri, key, str(tmp))

    def __getValFromConfig(self, name, key=''):
        """Get Floating val from configuration"""
        outVal = ""
        try:
            if key:
                outVal = self.config.get(key, name)
            else:
                outVal = self.config.get(self.sitename, name)
        except (configparser.NoOptionError, configparser.NoSectionError):
            pass
        return outVal

    def _addSwitchRoutes(self, switchInfo):
        """Add Route info to MRML"""

        for switchName, rstEntries in switchInfo.get('routes', {}).items():
            self.logger.debug('Working on1 %s' % switchName)
            out = {'hostname': switchName}
            try:
                out['rst'] = self.config.get(switchName, 'rst')
            except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                continue
            if 'rst' in out and out['rst']:
                try:
                    out['private_asn'] = self.config.get(switchName, 'private_asn')
                except (configparser.NoOptionError, configparser.NoSectionError) as ex:
                    self.logger.debug('ERROR: private_asn parameter is not defined (MISCONFIG. Contact Support) for %s. Err: %s', switchName, ex)
                    continue
            for ipX, routeList in rstEntries.items():
                out['rstname'] = 'rst-%s' % ipX
                for route in routeList:
                    # get ipv6/ipv4 floating ranges
                    for key in ['ipv4-subnet-pool', 'ipv6-subnet-pool']:
                        tmp = self.__getValFromConfig(key)
                        if tmp:
                            out[key] = tmp
                    out['iptype'] = ipX
                    out['rt-table'] = 'main' if 'vrf' not in route else 'vrf-%s' % route['vrf']
                    if 'from' in route:
                        out['routename'] = validMRMLName(route['from'])
                    elif 'intf' in route:
                        out['routename'] = validMRMLName(route['intf'])
                    else:
                        # We dont have from or intf it goes to. Not parsed correctly?
                        continue
                    if 'to' in route:
                        out['routetype'] ='routeTo'
                        out['type'] = '%s-prefix' % ipX
                        out['value'] = route['to']
                        self._addRouteEntry(**out)
                    if 'from' in route:
                        out['routetype'] = 'nextHop'
                        out['type'] = '%s-address' % ipX
                        out['value'] = route['from']
                        self._addRouteEntry(**out)

    def addSwitchInfo(self):
        """Add All Switch information from switch Backends plugin."""
        # Get switch information...
        switchInfo = self.switch.getinfo(True)
        # Add Switch information to MRML
        self._addSwitchPortInfo('ports', switchInfo)
        self._addSwitchVlanInfo('vlans', switchInfo)
        self._addSwitchLldpInfo(switchInfo)
        self._addSwitchRoutes(switchInfo)
