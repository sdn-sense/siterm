#!/usr/bin/env python3
"""
BW Service - converts bandwidth to QoS understandable format.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2024/02/21
"""

class BWService:
    """BW Service - converts bandwidth to QoS understandable format."""
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

    def _calculateRemaining(self, device, port, maxbw, reserve):
        """Calculate remaining bandwidth for device and port."""
        # If reserve is still -1, means full link speed allowed; if not, then we need to calculate
        # if reserve is 0, then no bandwidth is allowed.
        if reserve == 0:
            return 0
        if reserve == -1:
            reserve = "100%"
        if reserve.endswith("%"):
            # Calculate fraction of maxbw based on reserve %
            reserve = int(maxbw/100*int(reserve[:-1]))
        maxbw = reserve
        for _uri, uriData in self.activeDeltas.get('output', {}).get('vsw', {}).items():
            if device not in uriData:
                continue
            if port not in uriData[device]:
                continue
            # Means device and port is in the activeDeltas and we get hasService
            bwparams = uriData[device][port].get('hasService', {})
            if not bwparams:
                continue
            reservedRate = self.convertToRate(bwparams)
            self.logger.debug(f"Device {device} port {port} has reserved {reservedRate[0]} {reservedRate[1]}")
            maxbw -= reservedRate[0]
            self.logger.debug(f"Device {device} port {port} has reserved {maxbw} left")
        if maxbw < 0:
            self.logger.warning(f"Device {device} port {port} has reserved more than allowed. {maxbw}")
            return 0
        return maxbw

    def bwCalculatereservableSwitch(self, config, device, port, maxbw):
        """Calculate reserved bandwidth for port on switch."""
        reserve = config.get(device, {}).get(port, {}).get("reservableCapacity", -1)
        if reserve == -1:
            reserve = config.get(device, {}).get("reservableCapacity", -1)
        # Now we need to remove all active QoS policies and calculate how much is left for the port to use.
        vport = self.switch.getSystemValidPortName(port)
        return self._calculateRemaining(device, vport, maxbw, reserve)

    def bwCalculatereservableServer(self, config, device, port, maxbw):
        """Calculate reserved bandwidth for port on server."""
        reserve = config.get(port, {}).get('bwParams', {}).get("reservableCapacity", -1)
        if reserve == -1:
            reserve = config.get('agent', {}).get("reservableCapacity", -1)
        # Now we need to remove all active QoS policies and calculate how much is left for the port to use.
        return self._calculateRemaining(device, port, maxbw, reserve)
