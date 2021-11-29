#!/usr/bin/env python3
# pylint: disable=W0613,R0201
"""
    Switch class of RAW Plugin.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""


    # portKey - default is old in RAW plugin.
    # This would require to update all agents to use new key format
    # TODO: Update RAW plugin and all config files to use new config param


class Actions():
    """Main call for RAW Plugin."""
    def __init__(self):
        super().__init__()
        self.name = 'RAW'

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


class Switch(Actions):
    """RAW Switch plugin.
    All info comes from yaml files.
    """
    def _getFacts(self):
        return {}

    def getports(self, inData):
        """ Get ports for raw plugin """
        # TODO: get ports
        return {}

    def getportdata(self, inData, port):
        """ Get port data for raw plugin """
        # TODO: get port data
        return {}

    def getvlans(self, inData):
        """ Get vlans for raw plugin """
        # TODO: get vlan data
        return {}

    def getvlandata(self, inData, vlan):
        """ Get vlan data for raw plugin """
        # TODO: get vlan data
        return {}

    def getfactvalues(self, inData, key):
        """ Get custom command output """
        return {}
