#!/usr/bin/env python3
"""
Warnings class to handle warnings and raise ServiceWarning if needed.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2025/06/26
"""
from SiteRMLibs.CustomExceptions import ServiceWarning
from SiteRMLibs.MainUtilities import getUTCnow

class Warnings:
    """Warnings class to handle warnings and raise ServiceWarning if needed."""

    # pylint: disable=E1101,W0201,E0203
    def countWarnings(self, warning):
        """Warning Counter"""
        self.warningscounters.setdefault(warning, 0)
        self.warningscounters[warning] += 1

    def addWarning(self, warning):
        """Record Alarm."""
        self.countWarnings(warning)
        if self.warningscounters[warning] >= 5:
            self.warnings.append(warning)

    def checkAndRaiseWarnings(self):
        """Check and raise warnings in case there raised by Process"""
        if self.warnings:
            self.warningstart = self.warningstart if self.warningstart else getUTCnow()
            self.logger.warning("Warnings: %s", self.warnings)
            warnings = "\n".join(self.warnings)
            self.warnings = []
            raise ServiceWarning(warnings)
