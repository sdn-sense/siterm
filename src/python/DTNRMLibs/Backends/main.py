# Here goes iumport of all mudiles from Backends
# And it will update database with switch configs.
# It can also be called remotely
from DTNRMLibs.Backends.Ansible import Switch as Ansible
from DTNRMLibs.Backends.Raw import Switch as Raw
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.Backends.generalFunctions import getValFromConfig
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger



class Switch(Ansible, Raw):
    def __init__(self, config, logger, nodesInfo, site):
        self.config = config
        self.logger = logger
        self.nodesInfo = nodesInfo
        if not self.nodesInfo:
            self.nodesInfo = {}
        self.site = site
        self.output = {'switches': {}, 'ports': {}, 'vlans': {}, 'routes': {}}

        if self.config['vsw'] == 'ansible':
            Ansible.__init__(self, self.config['vsw'])
        elif self.config['vsw'] == 'raw':
            Raw.__init__(self, self.config['vsw'])

    #getconfig(refresh=False):
    #    if no refresh - get from db if available;
    #    if refresh - run ansible runner and update db
    #    if refresh and plugin == raw - use raw plugin and update db

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
