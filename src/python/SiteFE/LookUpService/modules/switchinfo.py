#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    Add Switch Info to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from SiteRMLibs.ipaddr import validMRMLName
from SiteRMLibs.ipaddr import normalizeipdict
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.CustomExceptions import NoSectionError


def generateVal(cls, inval, inkey, esc=False):
    """Generate mrml valid val/key for ipv4/ipv6"""
    if isinstance(inval, dict) and inkey == 'ipv4':
        return _genIPv4(cls, inval, inkey, esc)
    if isinstance(inval, dict) and inkey == 'ipv6':
        return _genIPv6(cls, inval, inkey, esc)
    if isinstance(inval, (dict, list)):
        cls.logger.info(f'Out is dictionary/list, but vals unknown. Return as str {inval}')
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
                return validMRMLName(f"{inval['address']}/{subnet}")
            return f"{inval['address']}/{subnet}"
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv4(cls, val, inkey), 'val': val} for val in inval]
        return tmpKeys
    cls.logger.debug(f'No IPv4 value. Return empty String. This might break things. Input: {inval} {inkey}')
    return ''

def _genIPv6(cls, inval, inkey, esc=True):
    """
    Generate Interface IPv6 details
    Ansible returns list if multiple IPs set on Interface.
    But for some switches, it will return dict if a single entry
    """
    if isinstance(inval, dict):
        subnet = 64 # Default we will use /64 just to secure code from diff ansible-switch outputs
        if 'subnet' in inval:
            subnet = inval['subnet'].split('/')[-1]
        if 'masklen' in inval:
            subnet = inval['masklen']
        if 'address' in inval:
            if esc:
                return validMRMLName(f"{inval['address']}/{subnet}")
            return f"{inval['address']}/{subnet}"
        cls.logger.debug('One of params in Dict not available. Upredictable output')
    if isinstance(inval, list):
        tmpKeys = [{'key': inkey, 'subkey': _genIPv6(cls, val, inkey), 'val': normalizeipdict(val)} for val in inval]
        return tmpKeys
    cls.logger.debug(f'No IPv6 value. Return empty String. This might break things. Input: {inval} {inkey}')
    return ''

def generateKey(cls, inval, inkey):
    """Generate keys for mrml and escape special charts"""
    if isinstance(inval, str):
        return replaceSpecialSymbols(inval)
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
    cls.logger.debug(f'Generate Keys return empty. Unexpected. Input: {inval} {inkey}')
    return ""

class SwitchInfo():
    """Module for Switch Info add to MRML"""
    # pylint: disable=E1101,W0201,E0203

    def _addVals(self, key, subkey, val, newuri):
        if not subkey:
            return
        val = generateVal(self, val, key, False)
        labeluri = f"{newuri}:{key}+{subkey}"
        reptype = key
        if key in ['ipv4', 'ipv6']:
            reptype = f'{key}-address'
            labeluri = f"{newuri}:{key}-address+{subkey}"
        elif key == 'sense-rtmon':
            reptype = f'{key}:name'
        self.addToGraph(['site', newuri],
                        ['mrs', 'hasNetworkAddress'],
                        ['site', labeluri])
        self.addToGraph(['site', labeluri],
                        ['rdf', 'type'],
                        ['mrs', 'NetworkAddress'])
        self.addToGraph(['site', labeluri],
                        ['mrs', 'type'],
                        [reptype])
        self.setToGraph(['site', labeluri],
                        ['mrs', 'value'],
                        [val])

    def addSwitchIntfInfo(self, switchName, portName, portSwitch, newuri):
        """Add switch info to mrml"""
        for key, val in portSwitch.items():
            if not val:
                continue
            if key == 'vlan_range_list':
                self.addToGraph(['site', newuri],
                                ['nml', 'hasLabelGroup'],
                                ['site', f"{newuri}:{'vlan-range'}"])
                self.addToGraph(['site', f"{newuri}:{'vlan-range'}"],
                                ['rdf', 'type'],
                                ['nml', 'LabelGroup'])
                self.addToGraph(['site', f"{newuri}:{'vlan-range'}"],
                                ['nml', 'labeltype'],
                                ['schema', '#vlan'])
                self.setToGraph(['site', f"{newuri}:{'vlan-range'}"],
                                ['nml', 'values'],
                                [",".join(map(str, portSwitch['vlan_range_list']))])
                # Generate host alias or adds' isAlias
                self._addIsAlias(uri=newuri, isAlias=portSwitch.get('isAlias'), hostname=switchName, portName=portName, nodetype='switch')
                continue
            if key == 'channel-member':
                for value in val:
                    switchuri = ":".join(newuri.split(':')[:-1])
                    self.addToGraph(['site', newuri],
                                    ['nml', 'hasBidirectionalPort'],
                                    ['site', f'{switchuri}:{self.switch.getSystemValidPortName(value)}'])
                continue
            if key in ['ipv4', 'ipv6', 'mac', 'macaddress', 'lineprotocol', 'operstatus', 'mtu', 'bandwidth']:
                subkey = generateKey(self, val, key)
                if isinstance(subkey, list):
                    for item in subkey:
                        self._addVals(item['key'], item['subkey'], item['val'], newuri)
                else:
                    self._addVals(key, subkey, val, newuri)
            if key in ['capacity', 'availableCapacity', 'granularity', 'reservableCapacity']:
                # TODO: Allow specify availableCapacity and granularity from config
                # reservableCapacity calculated automatically based on available - allAllocated.
                self._mrsLiteral(newuri, key, int(portSwitch.get(key)))
            if key in ['realportname']:
                # TODO Remove below check once config parser modified:
                # https://github.com/sdn-sense/siterm/issues/346
                tmpport = self.switch.getSystemValidPortName(val)
                # TODO Remove above replacement, once fix added.
                if self.config.has_option(switchName, f"port_{tmpport}_realport"):
                    val = self.config.config["MAIN"][switchName][f"port_{tmpport}_realport"]
                # Add real Port Name for Monitoring mapping
                self._addVals('sense-rtmon', key, val, newuri)

    def _addSwitchPortInfo(self, key, switchInfo):
        """Add Switch Port Info for ports, vlans"""
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug(f'Adding Switch Port Info {switchName}')
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (NoOptionError, NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            try:
                rst = self.config.get(switchName, 'rst')
            except (NoOptionError, NoSectionError):
                rst = False
            for portName, portSwitch in list(switchDict.items()):
                newuri = f":{switchName}:{self.switch.getSystemValidPortName(portName)}"
                self._addVswPort(hostname=switchName, portName=portName, vsw=vsw)
                self.addSwitchIntfInfo(switchName, portName, portSwitch, newuri)
                if rst:
                    self._addAddressPool(newuri)

    def _addSwitchVlanLabel(self, vlanuri, value):
        """Add Switch Vlan Label"""
        labeluri = f"{vlanuri}:label+{str(value)}"
        self.addToGraph(['site', vlanuri],
                        ['nml', 'hasLabel'],
                        ['site', labeluri])
        self.addToGraph(['site', labeluri],
                        ['rdf', 'type'],
                        ['nml', 'Label'])
        self.addToGraph(['site', labeluri],
                        ['nml', 'labeltype'],
                        ['schema', '#vlan'])
        self.setToGraph(['site', labeluri],
                        ['nml', 'value'],
                        [str(value)])

    def _addSwitchVlanInfo(self, key, switchInfo):
        """Add All Vlan Info from switch"""
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug(f'Adding Switch Vlan Info {switchName}')
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (NoOptionError, NoSectionError) as ex:
                self.logger.debug('ERROR: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue

            for portName, portSwitch in list(switchDict.items()):
                if 'tagged' not in portSwitch:
                    # This simply means vlan created but no tagged ports added. Ignoring it.
                    continue
                for taggedIntf in portSwitch['tagged']:
                    vlanuri = self._addVlanPort(hostname=switchName, portName=taggedIntf, vsw=vsw,
                                                vtype='vlanport', vlan=portSwitch['value'])
                    self._addSwitchVlanLabel(vlanuri, portSwitch['value'])
                    if 'vlan_range_list' in portSwitch:
                        # Vlan range for vlan - this is default coming from switch yaml conf
                        # But for sure we dont want to add into model
                        del portSwitch['vlan_range_list']
                    self.addSwitchIntfInfo(switchName, portName, portSwitch, vlanuri)


    def _addSwitchLldpInfo(self, switchInfo):
        """ADD LLDP Info to MRML"""
        def getSwitchSiteRMName(allMacs, macLookUp):
            """SiteRM uses uniques names for switches.
               Need to map it back via mac address"""
            for hName, hMacs in allMacs.items():
                if macLookUp in hMacs:
                    return hName
            return None
        for lldpHost, lldpDict in switchInfo['lldp'].items():
            for lldpIntf, intfDict in lldpDict.items():
                if 'remote_port_id' not in intfDict:
                    self.logger.debug(f'Remote port id not available from lldp info. lldp enabled? Full port info {lldpHost} {lldpIntf} {intfDict}')
                    continue
                macName = getSwitchSiteRMName(switchInfo['nametomac'], intfDict['remote_chassis_id'])
                if not macName:
                    continue
                remoteuri = f"{self.prefixes['site']}:{macName}:{self.switch.getSystemValidPortName(intfDict['remote_port_id'])}"
                localuri = f":{lldpHost}:{self.switch.getSystemValidPortName(lldpIntf)}"
                self._addIsAlias(uri=localuri, isAlias=remoteuri)

    def _addAddressPool(self, uri):
        """Add Address Pools"""
        for key in ['ipv4-address-pool-list', 'ipv6-address-pool-list']:
            tmp = self.__getValFromConfig(key)
            if tmp:
                self._addNetworkAddress(uri, key[:-5], ",".join(map(str, tmp)))

    def __getValFromConfig(self, name, key=''):
        """Get Floating val from configuration"""
        outVal = ""
        try:
            if key:
                outVal = self.config.get(key, name)
            else:
                outVal = self.config.get(self.sitename, name)
        except (NoOptionError, NoSectionError):
            pass
        return outVal

    def _addSwitchRoutes(self, switchInfo):
        """Add Route info to MRML"""
        for switchName, rstEntries in switchInfo.get('routes', {}).items():
            self.logger.debug(f'Adding Switch Routes {switchName}')
            out = {'hostname': switchName}
            try:
                out['rst'] = self.config.get(switchName, 'rst')
            except (NoOptionError, NoSectionError):
                continue
            if 'rst' in out and out['rst']:
                try:
                    out['private_asn'] = self.config.get(switchName, 'private_asn')
                except (NoOptionError, NoSectionError) as ex:
                    self.logger.debug('ERROR: private_asn parameter is not defined (MISCONFIG. Contact Support) for %s. Err: %s', switchName, ex)
                    continue
            for key in ['ipv4-subnet-pool-list', 'ipv6-subnet-pool-list']:
                tmp = self.__getValFromConfig(key)
                if tmp:
                    out[key[:-5]] = ",".join(map(str, tmp))
            for iptype in ["ipv4", "ipv6"]:
                out['iptype'] = iptype
                out['rstname'] = f'rst-{iptype}'
                self._addRoutingTable(**out)
            # Add all routes from network device
            for ipX, routeList in rstEntries.items():
                out['rstname'] = f'rst-{ipX}'
                for route in routeList:
                    out['iptype'] = ipX
                    out['rt-table'] = 'main' if 'vrf' not in route else f"vrf-{route['vrf']}"
                    if 'from' in route:
                        out['routename'] = validMRMLName(route['from'])
                    elif 'intf' in route:
                        out['routename'] = validMRMLName(route['intf'])
                    else:
                        # We dont have from or intf it goes to. Not parsed correctly?
                        continue
                    if 'to' in route:
                        out['routetype'] ='routeTo'
                        out['type'] = f'{ipX}-prefix'
                        out['value'] = route['to']
                        self._addRouteEntry(**out)
                    if 'from' in route:
                        out['routetype'] = 'nextHop'
                        out['type'] = f'{ipX}-address'
                        out['value'] = route['from']
                        self._addRouteEntry(**out)

    def addSwitchInfo(self, renew):
        """Add All Switch information from switch Backends plugin."""
        # Get switch information...
        switchInfo = self.switch.getinfo(renew)
        # Add Switch information to MRML
        self._addSwitchPortInfo('ports', switchInfo)
        self._addSwitchVlanInfo('vlans', switchInfo)
        self._addSwitchLldpInfo(switchInfo)
        self._addSwitchRoutes(switchInfo)
