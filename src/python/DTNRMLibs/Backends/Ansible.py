# pylint: disable=E1101
""" DESCRIPTION """
import ansible_runner
import pprint
from DTNRMLibs.Backends.NodeInfo import Node
from DTNRMLibs.Backends.generalFunctions import *

# =======================
#  Main caller - calls are done only by Provisioning Service
# =======================

class mainCaller():
    """ Main caller """
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
    """
    Ansible Switch Module
    """

    def _setDefaults(self, switchName):
        for key in self.output.keys():
            self.output[key][switchName] = {}

    def _getFacts(self):
        r = ansible_runner.run(private_data_dir='/etc/ansible/sense/',
                               inventory='/etc/ansible/sense/inventory/inventory.yaml',
                               playbook='getfacts.yaml')
                               #debug = True,
                               #ignore_logging = False)
        import pdb; pdb.set_trace()
        print(r.stats)
        for host, _ in r.stats['ok'].items():
            print("HOSTNAME: %s" % host)
            print('-'*100)
            for host_events in r.host_events(host):
                if 'runner_on_ok' != host_events['event']:
                    continue
                if 'stdout_lines' in host_events['event_data']['res']:
                    for line in host_events['event_data']['res']['stdout_lines'][0]:
                        print(line)
                elif 'ansible_facts' in host_events['event_data']['res'] and  \
                     'ansible_net_interfaces' in host_events['event_data']['res']['ansible_facts']:
                    action = host_events['event_data']['task_action']
                    #if action in vlanToInterface.keys():
                    #    tmpOut = vlanToInterface[action].parser(host_events)
                    #    for portName, portVals in tmpOut.items():
                    #        host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'].setdefault(portName, {})
                    #        host_events['event_data']['res']['ansible_facts']['ansible_net_interfaces'][portName].update(portVals)
                    pprint.pprint(host_events['event_data']['res']['ansible_facts'])
                else:
                    pprint.pprint(host_events)
            print('-'*100)





    def switchInfo(self, switch):
        "Get all switch info from Switch Itself"
        self._setDefaults(switch)
        self._getFacts()
        ports, defVlans, portsIgn = getConfigParams(self.config, switch, None)
        portKey = "port_%s_%s"
        for port in ports:
            # Spaces from port name are replaced with _
            # Backslashes are replaced with dash
            # Also - mrml does not expect to get string in nml. so need to replace all
            # Inside the output of dictionary
            nportName = port.replace(" ", "_").replace("/", "-")
            if port in portsIgn:
                del self.sOut[switch]['ports'][port]
                continue
            portDict = self.output['ports'][switch].setdefault(nportName, {})
            switchDict = self.output['switches'].setdefault(switch, {})
            switchPortDict = switchDict.setdefault(nportName, {})
            for key in ['hostname', 'isAlias', 'vlan_range', 'capacity', 'desttype', 'destport']:
                if not self.config.has_option(switch, portKey % (nportName, key)):
                    if key == 'vlan_range':
                        portDict[key] = defVlans
                    # if destType not defined, check if switchport available in switch config.
                    # Then set it to switch
            # elif 'switchport' in self.sOut[switch]['ports'][nportName].keys() and self.sOut[switch]['ports'][nportName]['switchport']:
            #     self.sOut[switch]['ports'][nportName]['desttype'] = 'switch'
                    continue
                portDict[key] = getValFromConfig(self.config, switch, nportName, key, portKey)
                if key == 'isAlias':
                    spltAlias = portDict[key].split(':')
                    switchPortDict['isAlias'] = portDict[key]
                    switchPortDict['desttype'] = 'switch'
                    switchPortDict['destport'] = spltAlias[-1]
                    switchPortDict['hostname'] = spltAlias[-2]

