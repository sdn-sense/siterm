# And it will update database with switch configs.
# It can also be called remotely
from DTNRMLibs.Backends.Ansible import Switch as Ansible
from DTNRMLibs.Backends.Raw import Switch as Raw
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import checkConfig
from DTNRMLibs.Backends.generalFunctions import cleanupEmpty
from DTNRMLibs.MainUtilities import getConfig, getStreamLogger, getLogger
from DTNRMLibs.FECalls import getAllSwitches


class Switch(Ansible, Raw, Node):
    def __init__(self, config, logger, site):
        self.config = config
        self.logger = logger
        self.site = site
        self.output = {'switches': {}, 'ports': {}, 'vlans': {}, 'routes': {}}
        if self.config[site]['plugin'] == 'ansible':
            Ansible.__init__(self)
        elif self.config[site]['plugin'] == 'raw':
            Raw.__init__(self)
        else:
            raise Exception(f"Plugin {self.config[site]['plugin']} is not supported. Contact Support")

    #getconfig(refresh=False):
    #    if no refresh - get from db if available;
    #    if refresh - run ansible runner and update db
    #    if refresh and plugin == raw - use raw plugin and update db

    def _setDefaults(self, switchName):
        for key in self.output.keys():
            self.output[key][switchName] = {}

    def getinfo(self, renew=False):
        """Get info about RAW plugin."""
        # If config miss required options. return.
        # See error message for more details.
#getAllSwitches
        if checkConfig(self.config, self.logger, self.site):
            return self.output
        switch = self.config.get(self.site, 'switch')
        for switchn in switch.split(','):
            self.switchInfo(switchn)
            print(2)
            print(self.output)
        self.output = self.nodeinfo()
        print(1)
        return cleanupEmpty(self.output)

def execute(config=None, logger=None):
    """Main Execute."""
    if not config:
        config = getConfig()
    if not logger:
        logger = getLogger()
    for siteName in config.get('general', 'sites').split(','):
        policer = Switch(config, logger, siteName)
        out = policer.getinfo()
        print(out)

if __name__ == '__main__':
    execute(logger=getStreamLogger())
