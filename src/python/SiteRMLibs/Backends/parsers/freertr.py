#!/usr/bin/env python3
# pylint: disable=W0613
"""
FreeRTR Additional Parser.
Ansible module issues simple commands and we need
to parse all to our way to represent inside the model
Needed for SENSE

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/13
"""

class FreeRTR():
    """Default class example for building new parsers"""
    def __init__(self, **kwargs):
        self.factName = ['sense.freertr.freertr_facts']
        self.defVlanNaming = '%(vlanname)%(vlanid)s'

MODULE = FreeRTR
