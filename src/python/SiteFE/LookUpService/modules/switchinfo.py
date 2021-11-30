import configparser

class SwitchInfo():
    """ Module for Switch Info add to MRML """
    # pylint: disable=E1101,W0201,E0203

    def addSwitchIntfInfo(self, switchName, portName, portSwitch, newuri):
        """ Add switch info (not for raw switches) """
        if 'vlan_range' in list(portSwitch.keys()) and \
           portSwitch['vlan_range']:
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
        for key, val in portSwitch.items():
            if key == 'vlan_range':
                continue
            if key == 'channel-member':
                for value in val:
                    switchuri = ":".join(newuri.split(':')[:-1])
                    self.addToGraph(['site', newuri],
                                    ['nml', 'hasBidirectionalPort'],
                                    ['site', '%s:%s' % (switchuri, self.switch._getSystemValidPortName(value))])
                continue

            self.addToGraph(['site', newuri],
                            ['mrs', 'hasNetworkAddress'],
                            ['site', '%s:%s' % (newuri, key)])
            self.addToGraph(['site', '%s:%s' % (newuri, key)],
                            ['rdf', 'type'],
                            ['mrs', 'NetworkAddress'])
            self.addToGraph(['site', "%s:%s" % (newuri, key)],
                            ['mrs', 'type'],
                            [key])
            self.addToGraph(['site', "%s:%s" % (newuri, key)],
                            ['mrs', 'value'],
                            [val])

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
                if 'tagged' in portSwitch:
                    for taggedIntf in portSwitch['tagged']:
                        newuri = ":%s:%s" % (switchName, taggedIntf)
                        self._addPort(newuri, vsw)
                        vlanuri = ":%s:%s:vlanport+%s" % (switchName, taggedIntf, portSwitch['value'])
                        self._addPort(newuri, vsw, vlanuri, False)
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
