#!/usr/bin/env python3
"""Helper Script to interact with SiteRM."""
import copy
import pprint
from SiteRMLibs.MainUtilities import getVal
from SiteRMLibs.MainUtilities import getDBConn
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import writeActiveDeltas
from SiteRMLibs.MainUtilities import getActiveDeltas
from SiteRMLibs.MainUtilities import evaldict
from SiteRMLibs.GitConfig import getGitConfig
from SiteFE.PolicyService.stateMachine import StateMachine

class Helper:
    """Helper class"""
    def __init__(self):
        self.commands = {"print-help": {"desc": "Print all available commands",
                                        "call": self.printhelp},
                         "print-active": {"desc": "Print all active resources in SiteRM.",
                                          "call": self.printactive},
                         "cancel-resource": {"desc": "Cancel resource in SiteRM.",
                                             "call": self.cancelresource},
                         "print-hosts": {"desc": "Print all hosts information in Frontend",
                                         "call": self.printhosts},
                         "change-delta": {"desc": "Change Delta State",
                                          "call": self.changedeltastate},
                         "exit": {"desc": "Exit helper script.",
                                  "call": self.exithelper}}
        self.config = getGitConfig()
        self.sitename = self._getSitename()
        self.dbI = getVal(getDBConn('List', self), **{'sitename': self.sitename})
        self.statemachine = StateMachine(self.config)

    @staticmethod
    def _getInput(question, validOptions=[]):
        """Wrapper for correct input to question"""
        while True:
            inpVal = input(question)
            if validOptions and inpVal not in validOptions:
                print(f'Input {inpVal} not in allowed list: {validOptions}')
            else:
                return inpVal

    def _getSitename(self):
        """Get Sitename from Git Config"""
        if len(self.config.get('general', 'sites')) == 1:
            sitename = self.config.get('general', 'sites')[0]
        else:
            print('Which sitename you want to modify?')
            nid = -1
            availcmds = []
            for stname in self.config.get('general', 'sites'):
                nid += 1
                availcmds.append(str(nid))
                print(f'{nid} : {stname}')
            siteID = self._getInput("Enter sitename ID: ", availcmds)
            sitename = self.config.get('general', 'sites')[int(siteID)]
        return sitename

    def changedeltastate(self):
        """Change delta state to committed and readd to model"""
        print("Which delta state you want to change")
        deltaid = self._getInput('Enter id: ')
        print(f"You entered: {deltaid}")
        for delta in self.dbI.get("deltas", search=[["uid", deltaid]]):
            print(delta)
            self.statemachine.stateChangerDelta(self.dbI, 'committed', **delta)
            self.statemachine.modelstatechanger(self.dbI, 'add', **delta)

    def printactive(self):
        """List Active"""
        activeDeltas = getActiveDeltas(self)
        print('=' * 50)
        pprint.pprint(activeDeltas)

    def _cancelConfirmed(self, activeDeltas, *args):
        """Cancel was confirmed and will modify exitsDuring time for delta"""
        def __setlifetime(initem):
            lifetime = initem.setdefault('existsDuring', {})
            # Setting lifetime that it was running for 1 hour 1 day ago.
            lifetime['start'] = int(getUTCnow()) - 87400
            lifetime['end'] = int(getUTCnow()) - 86400

        def __loopsubitems(indeltas, outdeltas):
            for key, val in indeltas.items():
                if key == '_params':
                    workitem = outdeltas.setdefault('_params', {})
                    __setlifetime(workitem)
                elif isinstance(val, dict):
                    workitem = outdeltas.setdefault(key, {})
                    __loopsubitems(val, workitem)

        print('Cancel confirmed. Setting lifetime for resource as expired yesterday')
        newActive = copy.deepcopy(activeDeltas)
        workID = newActive['output'].setdefault(args[0], {}).setdefault(args[1], {})
        __loopsubitems(activeDeltas['output'][args[0]][args[1]], workID)
        # Write new activeDeltas;
        writeActiveDeltas(self, newActive['output'])
        print('New active Deltas written to database.')
        print('IMPORTANT: Start lookup_service to take effect.')

    def printhosts(self):
        """Print all hosts"""
        hosts = self.dbI.get("hosts", orderby=["updatedate", "DESC"], limit=1000)
        for host in hosts:
            tmpH = evaldict(host.get("hostinfo", {}))
            pprint.pprint(tmpH)

    def cancelresource(self):
        """Cancel specific resource"""
        print('='*50)
        print('1. Use this command carefully as it will delete resources!')
        print('2. Please make sure lookup_service is stopped.')
        print('   You can do this with the following command: supervisorctl stop lookup_service')
        print('   If not stopped - resources are not guaranteed to be deleted.')
        print('='*50)
        activeDeltas = getActiveDeltas(self)
        if not activeDeltas.get('output', {}):
            print('There are no active Deltas provisioned. Exiting')
            return
        print('-'*50)
        print('Which resource we want to deactivate?')
        print('Available options:')
        print('   vsw: Virtual Switching (VLAN)')
        print('   rst: Routing Service (BGP)')
        action = self._getInput('Enter action: ', ["vsw", "rst"])
        print('-'*50)
        print("List of all available {action} items:")
        availcmds = {}
        nid = -1
        for key in activeDeltas['output'][action].keys():
            nid += 1
            print(f"{nid}: {key}")
            availcmds[str(nid)] = key
        print("Which resource you want to cancel? Enter ID:")
        deltaid = self._getInput('Enter id: ', availcmds.keys())
        print(f"You entered: {deltaid}")
        print("This resource will be cancelled:")
        pprint.pprint(activeDeltas['output'][action][availcmds[deltaid]])
        print("See full delta above. If you want to proceed to cancel it")
        print("enter yes - to proceed cancel of resource;")
        print("enter no - to exit without changes")
        confirm = self._getInput('Proceed with cancel: ', ["yes", "no"])
        if confirm == 'yes':
            self._cancelConfirmed(activeDeltas, action, availcmds[deltaid])

    def printhelp(self):
        """Print Help and all available commands, descriptions"""
        print("-"*50)
        print("Available commands:")
        print("-"*50)
        for cmd, cmddict in self.commands.items():
            print(f"{cmd} : {cmddict['desc']}")
        print("-"*50)
        print('Which command you want to execute? ')

    @staticmethod
    def exithelper():
        """Exit Helper Script"""
        print('Finished.')
        exit(0)

    def startup(self):
        """Startup"""
        self.printhelp()
        while True:
            cmd = self._getInput('Enter command: ', self.commands.keys())
            self.commands[cmd]['call']()
            print('To see available commands, use print-help command.')

if __name__ == "__main__":
    helper = Helper()
    helper.startup()
