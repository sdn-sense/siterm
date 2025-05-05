#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Azure Sonic Additional Parser.
Ansible module issues simple commands and we need
to parse all to our way to represent inside the model
Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/04/13
"""


class Sonic():
    """Default class example for building new parsers"""
    def __init__(self, **kwargs):
        self.factName = ['sense.sonic.sonic_facts']
        self.defVlanNaming = 'Vlan%(vlanid)s'


MODULE = Sonic
