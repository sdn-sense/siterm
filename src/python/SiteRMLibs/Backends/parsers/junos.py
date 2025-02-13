#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Junos Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2025/02/13
"""
import re
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.ipaddr import normalizedip

class Junos():
    """Junos Parser"""
    def __init__(self, **kwargs):
        self.factName = ['sense.junos.junos_facts']
        self.defVlanNaming = 'Vlan%(vlanid)s'

MODULE = Junos
