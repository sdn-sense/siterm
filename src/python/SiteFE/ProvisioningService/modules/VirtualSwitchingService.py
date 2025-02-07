"""Virtual Switching module to prepare/compare with ansible config.

Copyright 2021 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title                   : siterm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
UpdateDate              : 2022/05/09
"""
from SiteRMLibs.ipaddr import normalizedip


def dictCompare(inDict, oldDict, key1):
    """Compare dict and set any remaining items
    from current ansible yaml as absent in new one if
    it's status is present"""
    # If equal - return
    if inDict == oldDict:
        return
    for key, val in oldDict.items():
        if isinstance(val, dict):
            dictCompare(inDict.setdefault(key, {}), val, key1)
            if not inDict[key]:
                # if it is empty after back from loop, delete
                del inDict[key]
            continue
        tmpKey = key
        if key1 in ["ipv4_address", "ipv6_address"]:
            tmpKey = normalizedip(key)
        if val == "present" and tmpKey not in inDict.keys():
            # Means current state is present, but model does not know anything
            inDict[tmpKey] = "absent"
        elif val not in ["present", "absent"]:
            # Ensure we pre-keep all other keys
            inDict[tmpKey] = val
    return


class VirtualSwitchingService:
    """Virtual Switching - add interfaces inside ansible yaml"""

    # pylint: disable=E1101,W0201,W0235
    def __init__(self):
        super().__init__()

    def __getdefaultIntf(self, host, key='vsw', subkey="interface"):
        """Setup default yaml dict for interfaces"""
        tmpD = self.yamlconfuuid.setdefault(key, {}).setdefault(self.connID, {})
        tmpD = tmpD.setdefault(host, {})
        tmpD = tmpD.setdefault(subkey, {})
        return tmpD

    @staticmethod
    def __getIP(iptype, inval):
        """Get IP from input"""
        ipval = inval.get("hasNetworkAddress", {}).get(f"{iptype}-address", {}).get("value", "")
        if ipval:
            return normalizedip(ipval)
        return None

    def __getVlanID(self, host, port, portDict):
        """Get vlan id from portDict"""
        if "hasLabel" not in portDict or "value" not in portDict["hasLabel"]:
            raise Exception(
                f"Bad running config. Missing vlan entry: {host} {port} {portDict}"
            )
        return portDict["hasLabel"]["value"]

    def __getdefaultVlan(self, host, port, portDict):
        """Default yaml dict setup"""
        tmpD = self.__getdefaultIntf(host, self.acttype)
        vlan = self.__getVlanID(host, port, portDict)
        vlanName = f"Vlan{vlan}"
        vlanDict = tmpD.setdefault(vlanName, {})
        vlanDict.setdefault("name", vlanName)
        vlanDict.setdefault("vlanid", vlan)
        tmpVrf = self.getConfigValue(host, "vrf")
        if tmpVrf:
            vlanDict.setdefault("vrf", tmpVrf)
        tmpVlanMTU = self.getConfigValue(host, "vlan_mtu")
        if tmpVlanMTU:
            vlanDict.setdefault("mtu", tmpVlanMTU)
        return vlanDict

    def _addQoS(self, host, port, portDict, _params):
        """Add QoS to expected yaml conf"""
        resvRate, resvUnit = self.convertToRate(portDict.get("hasService", {}))
        if resvRate == 0:
            return
        portName = self.switch.getSwitchPortName(host, port)
        portData = self.switch.getSwitchPort(host, portName)
        if portData.get('rate_limit', False):
            vlan = self.__getVlanID(host, port, portDict)
            tmpD = self.__getdefaultIntf(host, "qos", "qos")
            vlanD = tmpD.setdefault(f"{port}-{vlan}", {})
            vlanD.setdefault("port", portName)
            vlanD.setdefault("vlan", vlan)
            vlanD.setdefault("rate", resvRate)
            vlanD.setdefault("unit", resvUnit)
            vlanD.setdefault("state", "present")

    def _addTaggedInterfaces(self, host, port, portDict, _params):
        """Add Tagged Interfaces to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host, port, portDict)
        portName = self.switch.getSwitchPortName(host, port)
        vlanDict.setdefault("tagged_members", {})
        vlanDict["tagged_members"][portName] = "present"

    def _addIPv4Address(self, host, port, portDict, params):
        """Add IPv4 to expected yaml conf"""
        # For IPv4 - only single IP is supported. No secondary ones
        vlanDict = self.__getdefaultVlan(host, port, portDict)
        ipaddr = self.__getIP("ipv4", portDict)
        if ipaddr:
            vlanDict.setdefault("ipv4_address", {})
            vlanDict["ipv4_address"][ipaddr] = "present"
        # Add Debug IP if present
        ipaddr = self.__getIP("ipv4", params)
        if ipaddr:
            vlanDict.setdefault("ipv4_address", {})
            vlanDict["ipv4_address"][ipaddr] = "present"

    def _addIPv6Address(self, host, port, portDict, params):
        """Add IPv6 to expected yaml conf"""
        vlanDict = self.__getdefaultVlan(host, port, portDict)
        ipaddr = self.__getIP("ipv6", portDict)
        if ipaddr:
            vlanDict.setdefault("ipv6_address", {})
            vlanDict["ipv6_address"][ipaddr] = "present"
        # Add Debug IP if present
        ipaddr = self.__getIP("ipv6", params)
        if ipaddr:
            vlanDict.setdefault("ipv6_address", {})
            vlanDict["ipv6_address"][ipaddr] = "present"

    def _presetDefaultParams(self, host, port, portDict, _params):
        vlanDict = self.__getdefaultVlan(host, port, portDict)
        vlanDict["description"] = portDict.get("_params", {}).get(
            "tag", "SENSE-VLAN-Without-Tag"
        )
        vlanDict["belongsTo"] = portDict.get("_params", {}).get(
            "belongsTo", "SENSE-VLAN-Without-belongsTo"
        )
        vlanDict["state"] = "present"

    def _addparamsVsw(self, connDict, switches):
        """Wrapper for add params, to put individual request info too inside dictionary"""
        params = connDict.get("_params", {})
        for host, hostDict in connDict.items():
            if host in switches:
                for port, portDict in hostDict.items():
                    if port == "_params":
                        continue
                    self._presetDefaultParams(host, port, portDict, params)
                    self._addTaggedInterfaces(host, port, portDict, params)
                    self._addIPv4Address(host, port, portDict, params)
                    self._addIPv6Address(host, port, portDict, params)
                    self._addQoS(host, port, portDict, params)

    def addvsw(self, activeConfig, switches):
        """Prepare ansible yaml from activeConf (for vsw)"""
        if self.acttype in activeConfig:
            for connID, connDict in activeConfig[self.acttype].items():
                self.connID = connID
                if not self.checkIfStarted(connDict):
                    self.logger.info(f"{connID} has not started yet. Not adding to apply list")
                    continue
                self._addparamsVsw(connDict, switches)
                if connDict.get('_params', {}).get('networkstatus', '') == "deactivated":
                    # This happens during modify, force apply;
                    self.forceapply.append(connID)
                # If first run, we also force apply
                if self.firstrun and connID not in self.forceapply:
                    self.forceapply.append(connID)

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
                tmpD.setdefault(key, {"state": "absent",
                                      "rate": val["rate"],
                                      "unit": val["unit"],
                                      "port": val["port"],
                                      "vlan": val["vlan"]})
            if val["state"] != "absent":
                for key1, val1 in val.items():
                    if key1 in ["rate", "unit"]:
                        tmpD.setdefault(key, {}).setdefault(key1, val1)
        return True

    def compareVsw(self, switch, runningConf, uuid):
        """Compare expected and running conf"""
        different = False
        tmpD = self.yamlconfuuid.setdefault(self.acttype, {}).setdefault(uuid, {}).setdefault(switch, {})
        tmpD = tmpD.setdefault("interface", {})
        # If equal - return no difference
        if tmpD == runningConf:
            return different
        # If runningConf is empty, then it is different
        if not runningConf:
            return True
        for key, val in runningConf.items():
            if key not in tmpD.keys() and val["state"] != "absent":
                # Vlan is present in ansible config, but not in new config
                # set vlan to state: 'absent'. In case it is absent already
                # we dont need to set it again. Switch is unhappy to apply
                # same command if service is not present.
                tmpD.setdefault(key, {"state": "absent", "vlanid": val["vlanid"]})
                different = True
            if val["state"] != "absent":
                for key1, val1 in val.items():
                    if not val1:
                        continue
                    if isinstance(val1, (dict, list)) and key1 in [
                        "tagged_members",
                        "ipv4_address",
                        "ipv6_address",
                    ]:
                        yamlOut = tmpD.setdefault(key, {}).setdefault(key1, {})
                        dictCompare(yamlOut, val1, key1)
                        different = True
                    if isinstance(val1, str) and key1 == "vlanid":
                        tmpD.setdefault(key, {}).setdefault(key1, val1)
                        different = True
        return different
