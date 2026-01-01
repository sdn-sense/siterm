#!/usr/bin/env python3
"""
Load all parsers from this directory to ALL variable

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/12/01
"""

import glob
import importlib
from os.path import basename, dirname, isfile, join

# TODO: Review this of defVlanNaming load - so not loading class where it is not needed;
from SiteRMLibs.GitConfig import getGitConfig

modules = glob.glob(join(dirname(__file__), "*.py"))
__all__ = [basename(f)[:-3] for f in modules if isfile(f) and not f.endswith("__init__.py")]

ALL = {}
MAPPING = {}
for module in __all__:
    config = getGitConfig()
    tmpMod = importlib.import_module(f"SiteRMLibs.Backends.parsers.{module}")
    _tmp = tmpMod.MODULE(config=config)
    for name in _tmp.factName:
        ALL[name] = _tmp
    MAPPING[module] = _tmp.defVlanNaming
