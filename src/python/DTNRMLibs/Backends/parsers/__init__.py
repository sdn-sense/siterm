#!/usr/bin/env python3
"""
Load all parsers from this directory to ALL variable

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/12/01
"""
from os.path import dirname, basename, isfile, join
import glob
import importlib
modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [ basename(f)[:-3] for f in modules if isfile(f) and not f.endswith('__init__.py')]

ALL = {}
for module in __all__:
    tmpMod = importlib.import_module("DTNRMLibs.Backends.parsers.%s" % module)
    _tmp = tmpMod.MODULE()
    for name in _tmp.factName:
        ALL[name] = _tmp
