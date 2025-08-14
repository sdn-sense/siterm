#!/usr/bin/env python3
# pylint: disable=line-too-long, too-many-arguments
"""
Quality of Service module for switches
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/08/14
"""

class QualityOfService:
    """Quality of Service - manage QoS settings for switches"""
    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    def checkQoSEnabled(self, host, portData):
        """Check if QoS is enabled for this port"""
        # First check if this is enabled (either at port level, or globally at switch)
        hostratelimit = self.getConfigValue(host, "rate_limit")
        if hostratelimit != "":
            if not bool(hostratelimit):
                self.logger.debug(f"QoS is not enabled at switch level for {host}. ")
                return False
        portratelimit = portData.get("rate_limit", "NOTSET")
        if portratelimit == "NOTSET":
            # If not set, and switch level is set to true, then we assume it is enabled
            return True
        return bool(portratelimit)

    def __getQoSPolicyNumber(self, host, portDict):
        """Get QoS policy number from portDict"""
        qosPolicy = portDict.get("hasService", {}).get("type", {})
        qosPolicy = qosPolicy if qosPolicy else "default"
        if qosPolicy not in self.getConfigValue(host, "qos_policy"):
            self.logger.warning(f"QoS policy {qosPolicy} is not defined in config. " "Using default instead.")
            qosPolicy = "default"
            return self.getConfigValue(host, "qos_policy").get(qosPolicy, 1)
        return self.getConfigValue(host, "qos_policy")[qosPolicy]

    def addQoS(self, host, port, portDict, _params):
        """Add QoS to expected yaml conf"""
        portName = self.switch.getSwitchPortName(host, port)
        portData = self.switch.getSwitchPort(host, portName)
        if not self.checkQoSEnabled(host, portData):
            # QoS is not enabled, so no need to add it
            return
        resvRate, resvUnit = self.convertToRate(portDict.get("hasService", {}))
        if resvRate == 0:
            self.logger.debug(f"QoS is enabled for {host} {port} {portDict}. " "Rate is 0, so not adding to ansible yaml")
            # Should we still add this to 1?
            return

        vlan = self._getVlanID(host, port, portDict)
        tmpD = self._getdefaultIntf(host, "qos", "qos")
        vlanD = tmpD.setdefault(f"{port}-{vlan}", {})
        vlanD.setdefault("port", portName)
        vlanD.setdefault("vlan", vlan)
        vlanD.setdefault("rate", resvRate)
        vlanD.setdefault("unit", resvUnit)
        vlanD.setdefault("qosnumber", self.__getQoSPolicyNumber(host, portDict))
        vlanD.setdefault("qosname", portDict.get("hasService", {}).get("type", "default"))
        vlanD.setdefault("state", "present")
        vlanD.setdefault("maxremaining", self.bwCalculatereservableSwitch(self.config.config["MAIN"], host, port))

    def compareQoS(self, switch, runningConf, uuid=""):
        """Compare expected and running conf"""
        tmpD = self.yamlconfuuid.setdefault("qos", {}).setdefault(uuid, {}).setdefault(switch, {})
        tmpD = tmpD.setdefault("qos", {})
        if tmpD == runningConf:
            return False
        for key, val in runningConf.items():
            if key not in tmpD.keys() and val["state"] != "absent":
                # QoS is present in ansible config, but not in new config
                # set qos to state: 'absent'. In case it is absent already
                # we dont need to set it again. Switch is unhappy to apply
                # same command if service is not present.
                tmpD.setdefault(
                    key,
                    {
                        "state": "absent",
                        "rate": val["rate"],
                        "unit": val["unit"],
                        "port": val["port"],
                        "vlan": val["vlan"],
                        "qosnumber": val["qosnumber"],
                        "qosname": val["qosname"],
                    },
                )
            if val["state"] != "absent":
                for key1, val1 in val.items():
                    if key1 in ["rate", "unit"]:
                        tmpD.setdefault(key, {}).setdefault(key1, val1)
        return True
