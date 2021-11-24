#!/usr/bin/env python3
"""
    Switch class - to get all info for LookUpService

Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2021 California Institute of Technology
Date              : 2017/09/26
UpdateDate        : 2021/11/08
"""
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.Backends.generalFunctions import getValFromConfig
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger


class mainCaller():
    """Main call for RAW Plugin."""
    def __init__(self):
        super().__init__()
        self.name = 'RAW'

    def mainCall(self, stateCall, inputDict, actionState):
        """Main caller function which calls specific state."""
        out = {}
        if stateCall == 'accepting':
            out = self.accepting(inputDict, actionState)
        elif stateCall == 'accepted':
            out = self.accepted(inputDict, actionState)
        elif stateCall == 'committing':
            out = self.committing(inputDict, actionState)
        elif stateCall == 'committed':
            out = self.committed(inputDict, actionState)
        elif stateCall == 'activating':
            out = self.activating(inputDict, actionState)
        elif stateCall == 'active':
            out = self.active(inputDict, actionState)
        elif stateCall == 'activated':
            out = self.activated(inputDict, actionState)
        elif stateCall == 'failed':
            out = self.failed(inputDict, actionState)
        elif stateCall == 'remove':
            out = self.remove(inputDict, actionState)
        else:
            raise Exception('Unknown State %s' % stateCall)
        return out

    def accepting(self, inputDict, actionState):
        """Accepting state actions."""
        return True

    def accepted(self, inputDict, actionState):
        """Accepted state actions."""
        return True

    def committing(self, inputDict, actionState):
        """Committing state actions."""
        return True

    def committed(self, inputDict, actionState):
        """Committed state actions."""
        return True

    def activating(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def active(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def activated(self, inputDict, actionState):
        """Activating state actions."""
        return True

    def failed(self, inputDict, actionState):
        """Failed state actions."""
        return True

    def remove(self, inputDict, actionState):
        """Remove state actions."""
        return True


class Switch(mainCaller):
    """RAW Switch plugin.
    All info comes from yaml files.
    """
    def __init__(self, config, logger, nodesInfo, site):
        super().__init__()
        self.config = config
        self.logger = logger
        self.nodesInfo = nodesInfo
        if not self.nodesInfo:
            self.nodesInfo = {}
        self.site = site
        self.output = {'switches': {}, 'ports': {}, 'vlans': {}, 'routes': {}}

    def _setDefaults(self, switchName):
        for key in self.output.keys():
            self.output[key][switchName] = {}

    def getinfo(self, jOut={}, renew=False):
        """Get info about RAW plugin."""
        # If config miss required options. return.
        # See error message for more details.
        del renew # Renew False/True does not make sense in RAW plugin
        # It can always get the latest config
        if jOut:
            self.nodesInfo = jOut
        if checkConfig(self.config, self.logger, self.site):
            return self.output
        switch = self.config.get(self.site, 'switch')
        for switchn in switch.split(','):
            self.switchInfo(switchn)
        nodeInfo = Node(self.config, self.logger, self.site)
        self.output = nodeInfo.nodeinfo(self.nodesInfo, self.output)
        return cleanupEmpty(self.output)

    def switchInfo(self, switch):
        """Get all switch info from FE main yaml file."""
        self._setDefaults(switch)
        for port in self.config.get(switch, 'ports').split(','):
            # Each port has to have 4 things defined:
            self.output['ports'][switch][port] = {}
            for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
                if not self.config.has_option(switch, "port%s%s" % (port, key)):
                    self.logger.debug('Option %s is not defined for Switch %s and Port %s' % (key, switch, port))
                    continue
                tmpVal = getValFromConfig(self.config, switch, port, key)
                if key == 'capacity':
                    # TODO. Allow in future to specify in terms of G,M,B. For now only G
                    # and we change it to bits
                    self.output['ports'][switch][port][key] = tmpVal * 1000000000
                else:
                    self.output['ports'][switch][port][key] = tmpVal
            self.output['switches'][switch][port] = ""
            if self.config.has_option(switch, "port%shostname" % port):
                self.output['switches'][switch][port] = getValFromConfig(self.config, switch, port, 'hostname')
            elif self.config.has_option(switch, "port%sisAlias" % port):
                spltAlias = getValFromConfig(self.config, switch, port, 'isAlias').split(':')
                #self.output['switches'][switch][port] = spltAlias[-2]
                self.output['ports'][switch][port]['desttype'] = 'switch'
                if 'destport' not in list(self.output['ports'][switch][port].keys()):
                    self.output['ports'][switch][port]['destport'] = spltAlias[-1]
                if 'hostname' not in list(self.output['ports'][switch][port].keys()):
                    self.output['ports'][switch][port]['hostname'] = spltAlias[-2]

if __name__ == '__main__':
    print('WARNING!!!! This should not be used through main call. Only for testing purposes!!!')
    CONFIG = getConfig()
    COMPONENT = 'LookUpService'
    LOGGER = getStreamLogger()
    for sitename in CONFIG.get('general', 'sites').split(','):
        print('Working on %s' % sitename)
        method = Switch(CONFIG, LOGGER, None, sitename)
        print(method.getinfo())
