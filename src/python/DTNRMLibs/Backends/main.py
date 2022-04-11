#!/usr/bin/env python3
# pylint: disable=C0301
"""
Main Switch class called by all modules.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import json
from DTNRMLibs.Backends.Ansible import Switch as Ansible
from DTNRMLibs.Backends.Raw import Switch as Raw
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.Backends.generalFunctions import getConfigParams, getValFromConfig
from DTNRMLibs.MainUtilities import getConfig, getLoggingObject, getUTCnow
from DTNRMLibs.FECalls import getDBConn


class Switch(Ansible, Raw, Node):
    """ Main Switch Class. It will load module based on config """
    def __init__(self, config, site):
        self.config = config
        self.logger = getLoggingObject()
        self.site = site
        self.switches = {}
        checkConfig(self.config, self.site)
        self.dbI = getDBConn('Switch', self)[self.site]
        self.output = {'switches': {}, 'ports': {},
                       'vlans': {}, 'routes': {},
                       'lldp': {}, 'info': {},
                       'portMapping': {}}
        if self.config[site]['plugin'] == 'ansible':
            Ansible.__init__(self)
        elif self.config[site]['plugin'] == 'raw':
            Raw.__init__(self)
        else:
            raise Exception(f"Plugin {self.config[site]['plugin']} is not supported. Contact Support")

    def mainCall(self, stateCall, inputDict, actionState):
        """Main caller function which calls specific state."""
        out = {}
        if stateCall == 'activate':
            out = self.activate(inputDict, actionState)
        else:
            raise Exception('Unknown State %s' % stateCall)
        return out


    #getconfig(refresh=False):
    #    if no refresh - get from db if available;
    #    if refresh - run ansible runner and update db
    #    if refresh and plugin == raw - use raw plugin and update db

    def _setDefaults(self, switchName):
        for key in self.output.keys():
            self.output[key].setdefault(switchName, {})

    def _cleanOutput(self):
        self.output = {'switches': {}, 'ports': {},
                       'vlans': {}, 'routes': {},
                       'lldp': {}, 'info': {},
                       'portMapping': {}}

    def _delPortFromOut(self, switch, portname):
        for key in self.output.keys():
            if switch in self.output[key] and portname in self.output[key][switch]:
                del self.output[key][switch][portname]

    def _getDBOut(self):
        tmp = self.dbI.get('switches', limit=1, search=[['sitename', self.site]])
        if tmp:
            self.switches = tmp[0]
            self.switches['output'] = json.loads(self.switches['output'])
        if not self.switches:
            self.logger.debug('No switches in database.')

    def _getSystemValidPortName(self, port):
        """ get Systematic port name. MRML expects it without spaces """
        # Spaces from port name are replaced with _
        # Backslashes are replaced with dash
        # Also - mrml does not expect to get string in nml. so need to replace all
        # Inside the output of dictionary
        # Also - sometimes lldp reports multiple quotes for interface name from ansible out
        for rpl in [[" ", "_"], ["/", "-"], ['"', ''], ["'", ""]]:
            port = port.replace(rpl[0], rpl[1])
        return port

    # def _getAllSystemValidPortNames(self, switchName=None):
    #     out = {}
    #     for switch in self._getAllSwitches(switchName):
    #         sOut = out.setdefault(switch, [])
    #         for key in ['ports', 'vlans']:
    #             if key in self.output[switch]:
    #                 for portName in self.output['switch'][key].keys():
    #                     tmpP = self._getSystemValidPortName(portName)
    #                     if tmpP not in out:
    #                         sOut.append(tmpP)
    #     return out

    def _getPortMapping(self):
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
                        self.output['portMapping'][switch]['Vlan %s' % vlankey] = realportname
                        self.output['portMapping'][switch]['Vlan%s' % vlankey] = realportname
                        self.output['portMapping'][switch]['vlan%s' % vlankey] = realportname
                    else:
                        self.output['portMapping'][switch][portKey] = realportname

    def _getSwitchPortName(self, switchName, portName, vlanid=None):
        # Get the portName which is uses in Switch
        # as you can see in _getSystemValidPortName -
        # Port name from Orchestrator will come modified.
        # We need a way to revert it back to systematic switch port name
        sysPort = self.output['portMapping'].get(switchName, {}).get(portName, "")
        if not sysPort and vlanid:
            sysPort = 'Vlan %s' % vlanid
        elif not sysPort:
            sysPort = portName
        return sysPort

    def _getAllSwitches(self, switchName=None):
        if switchName:
            return [switchName] if switchName in self.output['switches'] else []
        return self.output['switches'].keys()


    def _insertToDB(self, data):
        self._getDBOut()
        out = {'sitename': self.site,
               'updatedate': getUTCnow(),
               'output': json.dumps(data)}
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

    def _addyamlInfoToPort(self, switch, nportName, defVlans, out):
        portKey = "port_%s_%s"
        for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
            if not self.config.has_option(switch, portKey % (nportName, key)):
                if key == 'vlan_range':
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
           any parameter in switch  configuration. """
        ports, defVlans, portsIgn = getConfigParams(self.config, switch, self)
        vlans = self.getvlans(self.switches['output'][switch])
        for port in ports:
            if port in portsIgn:
                self._delPortFromOut(switch, port)
                continue
            # Spaces from port name are replaced with _
            # Backslashes are replaced with dash
            # Also - mrml does not expect to get string in nml. so need to replace all
            # Inside the output of dictionary
            nportName = port.replace(" ", "_").replace("/", "-")
            tmpData = self.getportdata(self.switches['output'][switch], port)
            if port in vlans:
                tmpData = self.getvlandata(self.switches['output'][switch], port)
                vlansDict = self.output['vlans'][switch].setdefault(nportName, tmpData)
                vlansDict['realportname'] = port
                vlansDict['value'] = self.getVlanKey(port)
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
        self.output['info'][switch] = self.getfactvalues(self.switches['output'][switch], 'ansible_command_info')
        self.output['routes'][switch]['ipv4'] = self.getfactvalues(self.switches['output'][switch], 'ansible_command_ipv4')
        self.output['routes'][switch]['ipv6'] = self.getfactvalues(self.switches['output'][switch], 'ansible_command_ipv6')
        self.output['lldp'][switch] = self.getfactvalues(self.switches['output'][switch], 'ansible_command_lldp')


    def getinfo(self, renew=False):
        """Get info about RAW plugin."""
        # If renew or switches var empty - get latest
        # And update in DB
        if renew:
            out = self._getFacts()
            self._insertToDB(out)
        if not self.switches:
            self._getDBOut()
        # Clean and prepare output which is returned to caller
        self._cleanOutput()
        switch = self.config.get(self.site, 'switch')
        for switchn in switch.split(','):
            self._setDefaults(switchn)
            self._mergeYamlAndSwitch(switchn)
        self.output = cleanupEmpty(self.nodeinfo())
        self._getPortMapping()
        return self.output


def execute(config=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    for siteName in config.get('general', 'sites').split(','):
        switchM = Switch(config, siteName)
        out = switchM.getinfo()
        print(out)

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger')
    execute()
