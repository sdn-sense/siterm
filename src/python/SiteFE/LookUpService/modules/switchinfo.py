#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
    Add Switch Info to MRML


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from SiteRMLibs.ipaddr import validMRMLName
from SiteRMLibs.CustomExceptions import NoOptionError
from SiteRMLibs.CustomExceptions import NoSectionError

class SwitchInfo():
    """Module for Switch Info add to MRML"""
    # pylint: disable=E1101,W0201,E0203

    def _addSwitchBWParams(self, switchName, portName, portSwitch):
        """Add Switch Bandwidth Params"""
        bw = 0
        if 'capacity' in portSwitch:
            bw = int(portSwitch['capacity'])
        elif 'bandwidth' in portSwitch:
            bw = int(portSwitch['bandwidth'])
        bwuri = self._addBandwidthService(hostname=switchName, portName=portName)
        bwremains = self.bwCalculatereservableSwitch(self.config.config["MAIN"], switchName, portName, bw)
        params = {'bwuri': bwuri,
                  'unit': 'mbps',
                  'maximumCapacity': bw,
                  'availableCapacity': bwremains,
                  'reservableCapacity': bwremains,
                  'minReservableCapacity': 100}
        self._addBandwidthServiceParams(**params)


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
                vlanRange = self.filterOutAvailbVlans(switchName, portSwitch['vlan_range_list'])
                self.setToGraph(['site', f"{newuri}:{'vlan-range'}"],
                                ['nml', 'values'],
                                [",".join(map(str, vlanRange))])
                # Generate host alias or adds' isAlias
                self._addIsAlias(uri=newuri, isAlias=portSwitch.get('isAlias'), hostname=switchName, portName=portName, nodetype='switch')
            elif key == 'channel-member':
                for value in val:
                    switchuri = ":".join(newuri.split(':')[:-1])
                    self.addToGraph(['site', newuri],
                                    ['nml', 'hasBidirectionalPort'],
                                    ['site', f'{switchuri}:{self.switch.getSystemValidPortName(value)}'])
            # All available: ipv4, ipv6, mac, macaddress, lineprotocol, operstatus, mtu, capacity, bandwidth
            elif key in ['ipv4', 'ipv6', 'macaddress']:
                subkey = self.generateKey(val, key)
                if isinstance(subkey, list):
                    for item in subkey:
                        self._addVals(item['key'], item['subkey'], item['val'], newuri)
                else:
                    self._addVals(key, subkey, val, newuri)

            elif key == 'realportname':
                self._addVals('sense-rtmon', key, val, newuri)
        # Add BW Params
        if not portName.startswith('Vlan'):
            self._addSwitchBWParams(switchName, portName, portSwitch)

    def _addSwitchPortInfo(self, key, switchInfo):
        """Add Switch Port Info for ports, vlans"""
        for switchName, switchDict in list(switchInfo[key].items()):
            self.logger.debug(f'Adding Switch Port Info {switchName}')
            # Get info if vsw is enabled in configuration
            try:
                vsw = self.config.get(switchName, 'vsw')
            except (NoOptionError, NoSectionError) as ex:
                self.logger.debug('Warning: vsw parameter is not defined for %s. Err: %s', switchName, ex)
                continue
            # Get info if vswmp is enabled in configuration (Multipoint)
            try:
                vswmp = self.config.get(switchName, 'vswmp')
            except (NoOptionError, NoSectionError):
                vswmp = f"{vsw}_mp"
            # Get info if vswdbip is enabled in configuration (Debug IP)
            try:
                vswdbip = self.config.get(switchName, 'vswdbip')
            except (NoOptionError, NoSectionError):
                vswdbip = f"{vsw}_debugip"
            # Get info if rst is enabled in configuration
            try:
                rst = self.config.get(switchName, 'rst')
            except (NoOptionError, NoSectionError):
                rst = False
            for portName, portSwitch in list(switchDict.items()):
                newuri = f":{switchName}:{self.switch.getSystemValidPortName(portName)}"
                self._addVswPort(hostname=switchName, portName=portName, vsw=vsw, vswmp=vswmp, vswdbip=vswdbip)
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
               Need to map it back via mac address
            """
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
                out['private_asn'] = self.config.get(switchName, 'private_asn')
            except (NoOptionError, NoSectionError):
                continue
            if not out['rst'] or not out['private_asn']:
                continue
            for iptype in ["ipv4", "ipv6"]:
                tmp = self.__getValFromConfig(f"{iptype}-subnet-pool")
                if tmp:
                    out[f"{iptype}-subnet-pool"] = tmp
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
                        out['routetype'] = 'routeTo'
                        out['type'] = f'{ipX}-prefix'
                        out['value'] = route['to']
                        self._addRouteEntry(**out)
                    if 'from' in route:
                        out['routetype'] = 'nextHop'
                        out['type'] = f'{ipX}-address'
                        out['value'] = route['from']
                        self._addRouteEntry(**out)

    def __recordSwitchUsedVlans(self, switchInfo):
        """Add Switch Used Vlans"""
        for switchName, switchDict in list(switchInfo['vlans'].items()):
            self.logger.debug(f'Adding Switch Used Vlans {switchName}')
            for _portName, portSwitch in list(switchDict.items()):
                vlanid = portSwitch.get('value', None)
                if vlanid:
                    self.usedVlans['system'].setdefault(switchName, [])
                    self.usedVlans['system'][switchName].append(int(vlanid))


    def addSwitchInfo(self):
        """Add All Switch information from switch Backends plugin."""
        # Get switch information...
        switchInfo = self.switch.getinfo()
        # Add Switch information to
        self.__recordSwitchUsedVlans(switchInfo)
        self._addSwitchPortInfo('ports', switchInfo)
        self._addSwitchVlanInfo('vlans', switchInfo)
        self._addSwitchLldpInfo(switchInfo)
        self._addSwitchRoutes(switchInfo)
