#!/usr/bin/env python3
# pylint: disable=C0301
"""
Main Switch class called by all modules.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import simplejson as json
from DTNRMLibs.Backends.Ansible import Switch as Ansible
from DTNRMLibs.Backends.Raw import Switch as Raw
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.Backends.generalFunctions import getConfigParams, getValFromConfig
from DTNRMLibs.MainUtilities import getGitConfig, getLoggingObject, getUTCnow
from DTNRMLibs.MainUtilities import getDBConn


class Switch(Node):
    """Main Switch Class. It will load module based on config"""
    def __init__(self, config, site):
        self.config = config
        self.logger = getLoggingObject(config=self.config, service='SwitchBackends')
        self.site = site
        self.switches = {}
        checkConfig(self.config, self.site)
        self.dbI = getDBConn('Switch', self)[self.site]
        self.output = {'switches': {}, 'ports': {},
                       'vlans': {}, 'routes': {},
                       'lldp': {}, 'info': {},
                       'portMapping': {}, 'nametomac': {}}
        self.plugin = None
        if self.config[site]['plugin'] == 'ansible':
            self.plugin = Ansible(self.config, self.site)
        elif self.config[site]['plugin'] == 'raw':
            self.plugin = Raw(self.config, self.site)
        else:
            raise Exception(f"Plugin {self.config[site]['plugin']} is not supported. Contact Support")

    def mainCall(self, stateCall, inputDict, actionState):
        """Main caller function which calls specific state."""
        out = {}
        if stateCall == 'activate':
            out = self.activate(inputDict, actionState)
        else:
            raise Exception(f'Unknown State {stateCall}')
        return out


    def _setDefaults(self, switchName):
        """Set Default vals inside output"""
        for key in self.output.keys():
            self.output[key].setdefault(switchName, {})

    def _cleanOutput(self):
        """Clean output"""
        self.output = {'switches': {}, 'ports': {},
                       'vlans': {}, 'routes': {},
                       'lldp': {}, 'info': {},
                       'portMapping': {}, 'nametomac': {}}

    def _delPortFromOut(self, switch, portname):
        """Delete Port from Output"""
        for key in self.output.keys():
            if switch in self.output[key] and portname in self.output[key][switch]:
                del self.output[key][switch][portname]

    def _getDBOut(self):
        """Get Database output of all switches configs for site"""
        tmp = self.dbI.get('switches', limit=1, search=[['sitename', self.site]])
        if tmp:
            self.switches = tmp[0]
            self.switches['output'] = json.loads(self.switches['output'])
        if not self.switches:
            self.logger.debug('No switches in database.')

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

    def _getPortMapping(self):
        """Get Port Mapping. Normalizing diff port representations"""
        for key in ['ports', 'vlans']:
            for switch, switchDict in self.output[key].items():
                if switch not in self.switches['output']:
                    continue
                for portKey in switchDict.keys():
                    self.output['portMapping'].setdefault(switch, {})
                    realportname = switchDict.get(portKey, {}).get('realportname', None)
                    if not realportname:
                        continue
                    if portKey.startswith('Vlan'):
                        # This is mainly a hack to list all possible options
                        # For vlan to interface mapping. Why? Ansible switches
                        # Return very differently vlans, like Vlan XXXX, VlanXXXX or vlanXXXX
                        # And we need to map this back with correct name to ansible for provisioning
                        vlankey = switchDict[portKey]['value']
                        self.output['portMapping'][switch][f'Vlan {vlankey}'] = realportname
                        self.output['portMapping'][switch][f'Vlan{vlankey}'] = realportname
                        self.output['portMapping'][switch][f'vlan{vlankey}'] = realportname
                    else:
                        self.output['portMapping'][switch][portKey] = realportname

    def _getSwitchPortName(self, switchName, portName, vlanid=None):
        """Get Switch Port Name"""
        # Get the portName which is uses in Switch
        # as you can see in getSystemValidPortName -
        # Port name from Orchestrator will come modified.
        # We need a way to revert it back to systematic switch port name
        if vlanid:
            netOS = self.plugin.getAnsNetworkOS(switchName)
            if netOS in self.plugin.defVlans:
                return self.plugin.defVlans[netOS] % vlanid
        sysPort = self.output['portMapping'].get(switchName, {}).get(portName, "")
        if not sysPort:
            sysPort = portName
        return sysPort

    def _getAllSwitches(self, switchName=None):
        """Get All Switches"""
        if switchName:
            return [switchName] if switchName in self.output['switches'] else []
        return self.output['switches'].keys()


    def _insertToDB(self, data):
        """Insert to database new switches data"""
        self._getDBOut()
        out = {'sitename': self.site,
               'updatedate': getUTCnow(),
               'output': json.dumps(data),
               'error': '[]'}
        if not self.switches:
            out['insertdate'] = getUTCnow()
            self.logger.debug('No switches in database. Calling add')
            self.dbI.insert('switches', [out])
        else:
            out['id'] = self.switches['id']
            self.logger.debug('Update switches in database.')
            self.dbI.update('switches', [out])
        # Once updated, inserted. Update var from db
        self._getDBOut()

    def _insertErrToDB(self, err):
        """Insert Error from switch to database"""
        self._getDBOut()
        out = {'sitename': self.site,
               'updatedate': getUTCnow(),
               'error': json.dumps(err)}
        if self.switches:
            out['id'] = self.switches['id']
            self.logger.debug('Update switches in database.')
            self.dbI.update('switches_error', [out])
        else:
            self.logger.info('No switches in DB. Will not update errors in database.')
        # Once updated, inserted. Update var from db
        self._getDBOut()

    def _addyamlInfoToPort(self, switch, nportName, defVlans, out):
        """Add Yaml info to specific port"""
        portKey = "port_%s_%s"
        for key in ['hostname', 'isAlias', 'vlan_range_list', 'desttype', 'destport',
                    'capacity', 'granularity', 'availableCapacity']:
            if not self.config.has_option(switch, portKey % (nportName, key)):
                if key == 'vlan_range_list':
                    out[key] = defVlans
                continue
            out[key] = getValFromConfig(self.config, switch, nportName, key, portKey)
            if key == 'isAlias':
                spltAlias = out[key].split(':')
                out['isAlias'] = out[key]
                out['desttype'] = 'switch'
                out['destport'] = spltAlias[-1]
                out['hostname'] = spltAlias[-2]

    def _mergeYamlAndSwitch(self, switch):
        """Merge yaml and Switch Info. Yaml info overwrites
           any parameter in switch  configuration."""
        ports, defVlans, portsIgn = getConfigParams(self.config, switch, self)
        if switch not in self.switches['output']:
            return
        vlans = self.plugin.getvlans(self.switches['output'][switch])
        for port in ports:
            if port in portsIgn:
                self._delPortFromOut(switch, port)
                continue
            # Spaces from port name are replaced with _
            # Backslashes are replaced with dash
            # Also - mrml does not expect to get string in nml. so need to replace all
            # Inside the output of dictionary
            nportName = port.replace(" ", "_").replace("/", "-")
            tmpData = self.plugin.getportdata(self.switches['output'][switch], port)
            if port in vlans:
                tmpData = self.plugin.getvlandata(self.switches['output'][switch], port)
                vlansDict = self.output['vlans'][switch].setdefault(nportName, tmpData)
                vlansDict['realportname'] = port
                vlansDict['value'] = self.plugin.getVlanKey(port)
                self._addyamlInfoToPort(switch, nportName, defVlans, vlansDict)
            else:
                portDict = self.output['ports'][switch].setdefault(nportName, tmpData)
                portDict['realportname'] = port
                self._addyamlInfoToPort(switch, nportName, defVlans, portDict)
                switchesDict = self.output['switches'][switch].setdefault(nportName, tmpData)
                switchesDict['realportname'] = port
                self._addyamlInfoToPort(switch, nportName, defVlans, switchesDict)
                # if destType not defined, check if switchport available in switch config.
                # Then set it to switch
                if 'switchport' in portDict.keys() and portDict['switchport']:
                    portDict['desttype'] = 'switch'
        # Add route information and lldp information to output dictionary
        self.output['info'][switch] = self.plugin.getfactvalues(self.switches['output'][switch], 'ansible_command_info')
        self.output['routes'][switch]['ipv4'] = self.plugin.getfactvalues(self.switches['output'][switch], 'ansible_command_ipv4')
        self.output['routes'][switch]['ipv6'] = self.plugin.getfactvalues(self.switches['output'][switch], 'ansible_command_ipv6')
        self.output['lldp'][switch] = self.plugin.getfactvalues(self.switches['output'][switch], 'ansible_command_lldp')
        self.output['nametomac'][switch] = self.plugin.nametomac(self.switches['output'][switch], switch)


    def getinfo(self, renew=False, hosts=None):
        """Get info about Network Devices using plugin defined in configuration."""
        # If renew or switches var empty - get latest
        # And update in DB
        out, err = {}, {}
        if renew or not self.switches:
            out, err = self.plugin._getFacts(hosts)
            if err:
                self._insertErrToDB(err)
                raise Exception('Failed ANSIBLE Runtime. See Error %s' % str(err))
            self._insertToDB(out)
        self._getDBOut()
        # Clean and prepare output which is returned to caller
        self._cleanOutput()
        switch = self.config.get(self.site, 'switch')
        for switchn in switch:
            if switchn in err:
                continue
            self._setDefaults(switchn)
            self._mergeYamlAndSwitch(switchn)
        self.output = cleanupEmpty(self.nodeinfo())
        self._getPortMapping()
        return self.output


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getGitConfig()
    for siteName in config.get('general', 'sites'):
        switchM = Switch(config, siteName)
        out = switchM.getinfo()
        print(out)

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='SwitchBackends')
    execute()
