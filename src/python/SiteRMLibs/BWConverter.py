#!/usr/bin/env python3
"""
BW Converter - converts bandwidth to QoS understandable format.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2024/02/21
"""

class BWConverter:
    """BW Converter - converts bandwidth to QoS understandable format."""
    # bps, bytes per second
    # kbps, Kbps, kilobytes per second
    # mbps, Mbps, megabytes per second
    # gbps, Gbps, gigabytes per second
    # bit, bits per second
    # kbit, Kbit, kilobit per second
    # mbit, Mbit, megabit per second
    # gbit, Gbit, gigabit per second
    # Seems there are issues with QoS when we use really big bites and it complains about this.
    # Solution is to convert to next lower value...
    # pylint: disable=E1101
    def convertToRate(self, params):
        """Convert input to rate understandable to fireqos."""
        self.logger.info(f"Converting rate for QoS. Input {params}")
        inputVal = params.get("reservableCapacity", 0)
        inputRate = params.get("unit", "undef")
        if inputVal == 0 and inputRate == "undef":
            return 0, "mbit"
        outRate = -1
        outType = ""
        if inputRate == "bps":
            outRate = int(inputVal // 1000000)
            outType = "mbit"
            if outRate == 0:
                outRate = int(inputVal // 1000)
                outType = "bit"
        elif inputRate == "mbps":
            outRate = int(inputVal)
            outType = "mbit"
        elif inputRate == "gbps":
            outRate = int(inputVal * 1000)
            outType = "mbit"
        if outRate != -1:
            self.logger.info(f"Converted rate for QoS from {inputRate} {inputVal} to {outRate}")
            return outRate, outType
        raise Exception(f"Unknown input rate parameter {inputRate} and {inputVal}")
