#!/usr/bin/env python3
# pylint: disable=W0611
# W0611 - Unused import (We skip this, because we want to have submodules inside module1)
"""DTN RM Site FE init."""
__all__ = ["LookUpService", "ProvisioningService", "REST"]
# IMPORTANT Be aware if you update version here, please update it also in:
# setupUtilities.py
# src/python/__init__.py
# src/python/SiteFE/__init__.py
# src/python/SiteRMAgent/__init__.py
# src/python/SiteRMLibs/__init__.py
__version__ = '1.5.51'
