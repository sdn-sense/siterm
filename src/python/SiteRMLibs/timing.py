#!/usr/bin/env python3
"""
Timing functions to check delta start/stop/overlap

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/10/16
"""
from collections import namedtuple
from datetime import datetime

from SiteRMLibs.MainUtilities import getUTCnow


class Timing:
    """Timing class to check activeDeltas start/end/overlaps"""

    default_timings = [0, 2147483647]

    def _getTimings(self, inConf):
        """Get Runtime params"""
        timings = inConf.get("_params", {}).get("existsDuring", {})
        if "start" not in timings:
            timings["start"] = int(self.default_timings[0])
        if "end" not in timings:
            timings["end"] = int(self.default_timings[1])
        return timings

    def _started(self, inConf):
        """Check if service started"""
        timings = self._getTimings(inConf)
        if getUTCnow() < timings["start"]:
            return False
        return True

    def _ended(self, inConf):
        """Check if service ended"""
        timings = self._getTimings(inConf)
        if getUTCnow() > timings["end"]:
            return True
        return False

    def checkIfStarted(self, inConf):
        """Check if service started."""
        serviceStart = True
        timings = self._getTimings(inConf)
        if timings == self.default_timings:
            return serviceStart
        if timings["start"] > getUTCnow():
            serviceStart = False
        if timings["end"] < getUTCnow():
            serviceStart = False
        return serviceStart

    def getTimeRanges(self, inConf):
        """Get Runtime params"""
        timings = self._getTimings(inConf)
        Range = namedtuple("Range", ["start", "end"])
        timeRange = Range(
            start=datetime.fromtimestamp(timings["start"]),
            end=datetime.fromtimestamp(timings["end"]),
        )
        return timeRange
