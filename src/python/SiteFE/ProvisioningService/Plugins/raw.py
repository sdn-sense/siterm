#!/usr/bin/env python3
"""Raw switch configuration. Means all rules are in place and it always
succeed.

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
"""
class mainCaller():
    """Main call for RAW Plugin."""
    def __init__(self):
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

    @staticmethod
    def accepting(inputDict, actionState):
        """Accepting state actions."""
        return True

    @staticmethod
    def accepted(inputDict, actionState):
        """Accepted state actions."""
        return True

    @staticmethod
    def committing(inputDict, actionState):
        """Committing state actions."""
        return True

    @staticmethod
    def committed(inputDict, actionState):
        """Committed state actions."""
        return True

    @staticmethod
    def activating(inputDict, actionState):
        """Activating state actions."""
        return True

    @staticmethod
    def active(inputDict, actionState):
        """Activating state actions."""
        return True

    @staticmethod
    def activated(inputDict, actionState):
        """Activating state actions."""
        return True

    @staticmethod
    def failed(inputDict, actionState):
        """Failed state actions."""
        return True

    @staticmethod
    def remove(inputDict, actionState):
        """Remove state actions."""
        return True


class topology(object):
    def __init__(self):
        self.name = 'RAW'

    @staticmethod
    def getTopology():
        return {'switches': {}, 'vlans': {}}
