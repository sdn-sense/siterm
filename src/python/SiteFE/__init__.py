#!/usr/bin/env python
# pylint: disable=W0611
# W0611 - Unused import (We skip this, because we want to have submodules inside module1)
"""
DTN RM Site FE init
"""
__all__ = ["LookUpService", "ProvisioningService", "REST"]
# IMPORTANT Be aware if you update version here, please update it also in:
# setupUtilities.py
# src/python/__init__.py
# src/python/SiteFE/__init__.py
# src/python/DTNRMAgent/__init__.py
# src/python/DTNRMLibs/__init__.py
__version__ = '201104'
