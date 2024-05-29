#!/usr/bin/env python3
"""Plugin which gathers everything about all NICs.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import ipaddress
import os
import pprint

from pyroute2 import IPRoute
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.ipaddr import getIfAddrStats
from SiteRMLibs.MainUtilities import (evaldict, externalCommand, getFileContentAsJson)
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.BWService import BWService
from SiteRMLibs.GitConfig import getGitConfig

def str2bool(val):
    """Check if str is true boolean."""
    if isinstance(val, bool):
        return val
    return val.lower() in ("yes", "true", "t", "1")

class NetInfo(BWService):
    """Net Info"""
    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service="Agent")
        self.activeDeltas = {}

    def _getActive(self):
        """Get active deltas."""
        self.activeDeltas = {}
        workDir = self.config.get("general", "privatedir") + "/SiteRM/RulerAgent/"
        activeDeltasFile = f"{workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)

    def getvlans(self):
        """Get interface name and vlan id belonging to it"""
        out = {}
        if not os.path.isfile("/proc/net/vlan/config"):
            self.logger.warning("No /proc/net/vlan/config file found. Will not get vlan information")
            return out
        with open("/proc/net/vlan/config", "r", encoding="utf-8") as fd:
            vlanconf = fd.read()
        for vlanline in vlanconf.split("\n"):
            if not vlanline:
                continue
            splvlans = vlanline.split("|")
            if len(splvlans) == 3:
                intname = splvlans[0].strip()
                try:
                    tmpOut = {"vlanid": int(splvlans[1].strip()),
                              "master": splvlans[2].strip()}
                    out.setdefault(intname, tmpOut)
                except ValueError:
                    continue
        return out

    def getVlanID(self, nicname, privVlans):
        """Get Vlan id from privVlans, or from nicname"""
        try:
            if nicname in privVlans:
                return privVlans[nicname].get("vlanid", None)
            splName = nicname.split(".")
            if len(splName) == 2:
                return int(splName[1])
        except ValueError:
            pass
        return None

    def get(self, **_kwargs):
        """Get all network information"""
        self._getActive()
        netInfo = {}
        privVlans = self.getvlans()

        for intf in self.config.get("agent", "interfaces"):
            nicInfo = netInfo.setdefault(intf, {})
            if self.config.has_option(intf, "isAlias"):
                nicInfo["isAlias"] = self.config.get(intf, "isAlias")
            for key in [
                "ipv4-address-pool",
                "ipv4-subnet-pool",
                "ipv6-address-pool",
                "ipv6-subnet-pool",
            ]:
                if self.config.has_option(intf, key):
                    nicInfo[key] = self.config.get(intf, key)
                if self.config.has_option(intf, f"{key}-list"):
                    nicInfo[f"{key}-list"] = self.config.get(intf, f"{key}-list")
            nicInfo["vlan_range"] = self.config.get(intf, "vlan_range")
            nicInfo["vlan_range_list"] = self.config.get(intf, "vlan_range_list")
            if self.config.has_option(intf, "port"):
                nicInfo["switch_port"] = replaceSpecialSymbols(str(self.config.get(intf, "port")))
            if self.config.has_option(intf, "switch"):
                nicInfo["switch"] = str(self.config.get(intf, "switch"))
            nicInfo["shared"] = str2bool(self.config.get(intf, "shared"))
            nicInfo["vlans"] = {}
            # Bandwidth parameters
            nicInfo.setdefault("bwParams", {})
            nicInfo["bwParams"]["unit"] = "mbit"
            nicInfo["bwParams"]["type"] = self.config.get(intf, "bwParams").get("type", "guaranteedCapped")
            nicInfo["bwParams"]["priority"] = self.config.get(intf, "bwParams").get("priority", 0)
            nicInfo["bwParams"]["minReservableCapacity"] = int(self.config.get(intf, "bwParams").get("minReservableCapacity", 0))
            nicInfo["bwParams"]["maximumCapacity"] = int(self.config.get(intf, "bwParams").get("maximumCapacity", 0))
            nicInfo["bwParams"]["granularity"] = int(self.config.get(intf, "bwParams").get("granularity", 0))

            reservedCap = self.bwCalculatereservableServer(self.config.config["MAIN"],
                                                           self.config.get('agent', 'hostname'), intf,
                                                           nicInfo["bwParams"]["maximumCapacity"])
            nicInfo["bwParams"]["availableCapacity"] = reservedCap
            nicInfo["bwParams"]["reservableCapacity"] = reservedCap
        tmpifAddr, tmpifStats = getIfAddrStats()

        nics = externalCommand("ip -br a")
        for nicline in nics[0].decode("UTF-8").split("\n"):
            if not nicline:
                continue
            nictmp = nicline.split()[0].split("@")
            nic = nictmp[0]
            if len(nictmp) == 1 and nictmp[0] in netInfo:
                nicInfo = netInfo.setdefault(nic, {})
            elif len(nictmp) == 2 and nictmp[1] in netInfo:
                masternic = netInfo.setdefault(nictmp[1], {})
                nicInfo = masternic.setdefault("vlans", {}).setdefault(nic, {})
                vlanid = self.getVlanID(nic, privVlans)
                if vlanid:
                    nicInfo["vlanid"] = vlanid
                    if vlanid in masternic["vlan_range_list"]:
                        nicInfo["provisioned"] = True
                    else:
                        nicInfo["provisioned"] = False
            else:
                continue
            if nic not in tmpifAddr:
                continue
            for vals in tmpifAddr[nic]:
                nicInfo.setdefault(str(vals.family.value), [])
                familyInfo = {
                    "family": vals.family.value,
                    "address": vals.address,
                    "netmask": vals.netmask,
                }
                if int(vals.family.value) in [2, 10] and vals.address and vals.netmask:
                    try:
                        ipwithnetmask = ipaddress.ip_interface(
                            f"{vals.address}/{vals.netmask}"
                        )
                        if isinstance(ipwithnetmask, ipaddress.IPv4Interface):
                            familyInfo["ipv4-address"] = str(ipwithnetmask)
                        elif isinstance(ipwithnetmask, ipaddress.IPv6Interface):
                            familyInfo["ipv6-address"] = str(ipwithnetmask)
                        else:
                            self.logger.debug(
                                f"This type was not understood by the system. Type: {type(ipwithnetmask)} and value: {str(ipwithnetmask)}"
                            )
                    except ValueError:
                        continue
                elif int(vals.family.value) in [17]:
                    familyInfo["mac-address"] = vals.address
                familyInfo["broadcast"] = vals.broadcast
                familyInfo["ptp"] = vals.ptp
                if vals.family.value == 2:
                    familyInfo["UP"] = tmpifStats[nic].isup
                    familyInfo["duplex"] = tmpifStats[nic].duplex.value
                    familyInfo["speed"] = tmpifStats[nic].speed
                    familyInfo["MTU"] = tmpifStats[nic].mtu
                    # Additional info which is not provided by psutil so far...
                    # More detail information about all types here:
                    # http://lxr.free-electrons.qcom/source/include/uapi/linux/if_arp.h
                    nicType = externalCommand("cat /sys/class/net/" + nic + "/type")
                    familyInfo["Type"] = nicType[0].decode("UTF-8").strip()
                    txQueueLen = externalCommand(
                        "cat /sys/class/net/" + nic + "/tx_queue_len"
                    )
                    familyInfo["txqueuelen"] = txQueueLen[0].strip()
                nicInfo[str(vals.family.value)].append(familyInfo)
        # Check in the end which interfaces where defined in config but not available...
        outputForFE = {"interfaces": {}, "routes": [], "lldp": {}}
        for intfName, intfDict in netInfo.items():
            if intfName.split(".")[0] not in self.config.get("agent", "interfaces"):
                self.logger.debug(
                    f"This interface {intfName} was defined in configuration, but not available. Will not add it to final output"
                )
            else:
                outputForFE["interfaces"][intfName] = intfDict
        # Get Routing Information
        outputForFE["routes"] = self.getRoutes()
        outputForFE["lldp"] = self.getLLDP()
        return outputForFE


    def getLLDP(self):
        """Get LLDP Info, if socket is available and lldpcli command does not raise exception"""
        try:
            lldpOut = externalCommand("lldpcli show neighbors -f json")
            lldpObj = evaldict(lldpOut[0].decode("utf-8"))
            out = {}
            for item in lldpObj.get("lldp", {}).get("interface", []):
                for intf, vals in item.items():
                    mac = ""
                    remintf = ""
                    for _switch, swvals in vals.get("chassis", {}).items():
                        if swvals.get("id", {}).get("type", "") == "mac":
                            mac = swvals["id"]["value"]
                    # lets get remote port info
                    if vals.get("port", {}).get("id", {}).get("type", "") in ["ifname", "local"]:
                        remintf = vals["port"]["id"]["value"]
                    if mac and remintf:
                        out[intf] = {
                            "remote_chassis_id": mac,
                            "remote_port_id": remintf,
                            "local_port_id": intf,
                        }
            return out
        except:
            self.logger.debug(
                "Failed to get lldp information with lldpcli show neighbors -f json. lldp daemon down?"
            )
        return {}


    def getRoutes(self):
        """Get Routing information from host"""
        routes = []
        with IPRoute() as ipr:
            for route in ipr.get_routes(table=254, family=2):
                newroute = {"dst_len": route["dst_len"], "iptype": "ipv4"}
                for item in route["attrs"]:
                    if item[0] in ["RTA_GATEWAY", "RTA_DST", "RTA_PREFSRC"]:
                        newroute[item[0]] = item[1]
                routes.append(newroute)
            for route in ipr.get_routes(table=254, family=10):
                newroute = {"dst_len": route["dst_len"], "iptype": "ipv6"}
                for item in route["attrs"]:
                    if item[0] in ["RTA_GATEWAY", "RTA_DST", "RTA_PREFSRC"]:
                        newroute[item[0]] = item[1]
                routes.append(newroute)
        return routes

    def postProcess(self, data):
        """Post process data"""
        for key, intfData in data.get('NetInfo', {}).get('interfaces', {}).items():
            if not intfData.get('switch_port'):
                self.logger.error(f"Interface {key} has no switch port defined, nor was available from Kube (in case Kube install)!")
            if not intfData.get('switch'):
                self.logger.error(f"Interface {key} has no switch defined, nor was available from Kube (in case Kube install)!")
        return data

if __name__ == "__main__":
    obj = NetInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
