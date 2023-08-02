#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Arista EOS Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
import re
from SiteRMLibs.MainUtilities import getLoggingObject

class AristaEOS():
    """Arista EOS Ansible wrapper."""
    def __init__(self, **kwargs):
        self.factName = ['arista.eos.eos_facts', 'arista.eos.facts', 'arista.eos.eos_command']
        self.defVlanNaming = 'Vlan%(vlanid)s'

MODULE = AristaEOS
