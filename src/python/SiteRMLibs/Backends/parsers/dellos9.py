#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Dell OS9 Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""


class DellOS9():
    """Dell OS 9 Parser"""
    def __init__(self, **kwargs):
        self.factName = ['sense.dellos9.dellos9_facts']
        self.defVlanNaming = 'Vlan%(vlanid)s'


MODULE = DellOS9
