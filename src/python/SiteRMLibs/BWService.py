#!/usr/bin/env python3
"""
BW Service - converts bandwidth to QoS understandable format.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2024/02/21
"""


class BWService:
    """BW Service - converts bandwidth to QoS understandable format."""

    def __init__(self):  # pylint: disable=useless-super-delegation
        super().__init__()

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
            return outRate, outType
        raise Exception(f"Unknown input rate parameter {inputRate} and {inputVal}")

    def convertForBWService(self, params):
        """Convert input to rate understandable to sense-o"""
        # SiteRM Reports everything in mbps and we need to cover user input
        # bps, bytes per second
        # kbps, Kbps, kilobytes per second
        # mbps, Mbps, megabytes per second
        # gbps, Gbps, gigabytes per second
        # Input: "unit": "mbps", "minCapacity": "100"
        inputVal = params.get("minCapacity", 100)
        inputRate = params.get("unit", "mbps")
        retVal = 100
        try:
            if inputRate == "mbps":
                retVal = inputVal
            elif inputRate == "gbps":
                retVal = inputVal * 1000
            elif inputRate == "bps":
                retVal = int(inputVal // 1000000)
            elif inputRate == "kbps":
                retVal = int(inputVal // 1000)
            else:
                self.logger.error(f"Unknown input rate parameter {inputRate} and {inputVal}")
                retVal = 100
        except TypeError as ex:
            self.logger.error(f"Error converting BW Service. {ex}. Input {params}")
        return retVal

    def _calculateRemaining(self, device, port, maxbw, reserve, nosubtract=False, subtractGC=False):
        """Calculate remaining bandwidth for device and port."""
        # If reserve is still -1, means full link speed allowed; if not, then we need to calculate
        # if reserve is 0, then no bandwidth is allowed.
        if reserve == 0:
            return 0
        if reserve == -1:
            reserve = "100%"
        if reserve.endswith("%"):
            # Calculate fraction of maxbw based on reserve %
            reserve = int(maxbw / 100 * int(reserve[:-1]))
        maxbw = reserve
        if nosubtract:
            return maxbw
        for _uri, uriData in self.activeDeltas.get("output", {}).get("vsw", {}).items():
            if device not in uriData:
                continue
            if port not in uriData[device]:
                continue
            # Means device and port is in the activeDeltas and we get hasService
            bwparams = uriData[device][port].get("hasService", {})
            if not bwparams:
                continue
            reservedRate = self.convertToRate(bwparams)
            self.logger.debug(f"Device {device} port {port} has reserved {reservedRate[0]} {reservedRate[1]} for {bwparams.get('type', 'default')}")
            # In case subtractGC is set to True, we only subtract guaranteedCapped policies
            # This is mainly used for QoS calculation on switches, where only guaranteedCapped
            # policies actually reserve bandwidth on the switch port. Other policies are just
            # limiting traffic and use traffic classes to tell switch how to treat traffic.
            if subtractGC and bwparams.get("type", "") != "guaranteedCapped":
                continue
            maxbw -= reservedRate[0]
            self.logger.debug(f"Device {device} port {port} has left {maxbw}")
        if maxbw < 0:
            self.logger.warning(f"Device {device} port {port} has reserved more than allowed. {maxbw}")
            return 0
        return maxbw

    def __getMaxSwitchPortBandwidth(self, device, port):
        """Get max port bandwidth."""
        switchInfo = self.switch.getinfo()
        bw = 0
        port = self.switch.getSwitchPortName(device, port)
        if "capacity" in switchInfo.get("ports", {}).get(device, {}).get(port, {}):
            bw = int(switchInfo["ports"][device][port]["capacity"])
        elif "bandwidth" in switchInfo.get("ports", {}).get(device, {}).get(port, {}):
            bw = int(switchInfo["ports"][device][port]["bandwidth"])
        if bw <= 0:
            self.logger.warning(f"Device {device} port {port} has no bandwidth information. ")
        return bw

    def bwCalculatereservableSwitch(self, config, device, port, maxbw=None, nosubtract=False, subtractGC=False):
        """Calculate reserved bandwidth for port on switch."""
        if not maxbw:
            maxbw = self.__getMaxSwitchPortBandwidth(device, port)
        reserve = config.get(device, {}).get(port, {}).get("reservableCapacity", -1)
        if reserve == -1:
            reserve = config.get(device, {}).get("reservableCapacity", -1)
        # Now we need to remove all active QoS policies and calculate how much is left for the port to use.
        vport = self.switch.getSystemValidPortName(port)
        return self._calculateRemaining(device, vport, maxbw, reserve, nosubtract, subtractGC)

    def bwCalculatereservableServer(self, config, device, port, maxbw, nosubtract=False, subtractGC=False):
        """Calculate reserved bandwidth for port on server."""
        reserve = config.get(port, {}).get("bwParams", {}).get("reservableCapacity", -1)
        if reserve == -1:
            reserve = config.get("agent", {}).get("reservableCapacity", -1)
        # Now we need to remove all active QoS policies and calculate how much is left for the port to use.
        return self._calculateRemaining(device, port, maxbw, reserve, nosubtract, subtractGC)
