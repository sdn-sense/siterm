#!/usr/bin/env python3
# pylint: disable=W0613
"""
Cisco NX 9 Additional Parser.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2023/09/19
"""


class CiscoNX9:
    """Cisco NX 9 Parser"""

    def __init__(self, **kwargs):
        self.factName = ["sense.cisconx9.cisconx9_facts"]
        self.defVlanNaming = "Vlan%(vlanid)s"


MODULE = CiscoNX9
