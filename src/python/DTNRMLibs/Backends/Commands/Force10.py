#!/usr/bin/env python3
"""
    Force 10 cli commands.

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
Date            : 2021/11/08
"""

# Enable
CMD_ENABLE = "enable"

# Set terminal length to full output, no paging
CMD_TLENGTH = "terminal length 0"

# Switch End call
CMD_END = "end"

# Switch exit Call
CMD_EXIT = "exit"

# In case unable to disable paging, what to expect for pagging lien
PAGGING_LINE = "--More--"

# Line terminator
LT = "\n"

# Command to get running config
CMD_CONFIG = "show running config"

# Command to enter configure mode
CMD_CONFIGURE = "configure"

# Command to get interface stats #
CMD_INT_STAT = "show interfaces %(name)s %(id)s"

# Command to create vlan
CMD_CREATE_VLAN = """interface vlan %(id)"
 description %(description)s
 no shutdown
 exit"""

# Command to add interface to vlan
CMD_ADD_T_INTF = """interface vlan %(id)s
tagged %(interface)s %(intf_name)s
exit"""

# Command to remove vlan interface
CMD_REMOVE_VLAN = "no interface vlan %(id)s"

# Command to remove tagged interface from vlan
CMD_RM_T_INTF =  """interface vlan %(id)s
no tagged %(interface)s %(intf_name)s
exit"""

# Command to save configuration.
CMD_WRITE = "write memory"
