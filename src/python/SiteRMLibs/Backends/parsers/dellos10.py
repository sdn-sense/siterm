#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Dell OS9 Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""

class DellOS10():
    """Dell OS 10 Parser"""
    def __init__(self, **kwargs):
        self.factName = ['sense.dellos10.dellos10_facts']
        self.defVlanNaming = 'Vlan%(vlanid)s'

MODULE = DellOS10
