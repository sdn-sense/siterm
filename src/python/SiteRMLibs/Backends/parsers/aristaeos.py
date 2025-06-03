#!/usr/bin/env python3
# pylint: disable=E1101, C0301
"""
Arista EOS Additional Parser.
Ansible module does not parse vlans, channel members
attached to interfaces. Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""


class AristaEOS:
    """Arista EOS Ansible wrapper."""

    def __init__(self, **kwargs):
        self.factName = ["sense.aristaeos.aristaeos_facts"]
        self.defVlanNaming = "Vlan%(vlanid)s"


MODULE = AristaEOS
