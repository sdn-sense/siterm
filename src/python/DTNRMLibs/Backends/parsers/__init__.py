#!/usr/bin/env python3
"""
Load all parsers from this directory to ALL variable

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
# TODO: Load by name of all possible plugins.
from DTNRMLibs.Backends.parsers.aristaeos import AristaEOS
from DTNRMLibs.Backends.parsers.dellos9 import DellOS9

ALL = {}
for module in [AristaEOS, DellOS9]:
    _tmp = module()
    for name in _tmp.factName:
        ALL[name] = _tmp
