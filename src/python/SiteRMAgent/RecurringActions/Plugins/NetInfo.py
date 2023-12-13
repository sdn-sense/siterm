#!/usr/bin/env python3
"""Plugin which gathers everything about all NICs.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
import ipaddress
import pprint

import psutil
from pyroute2 import IPRoute
from SiteRMLibs.ipaddr import replaceSpecialSymbols
from SiteRMLibs.MainUtilities import (evaldict, externalCommand, getGitConfig,
                                      getLoggingObject)


def str2bool(val):
    """Check if str is true boolean."""
    if isinstance(val, bool):
        return val
    return val.lower() in ("yes", "true", "t", "1")


NAME = "NetInfo"


def get(config):
    """Get all network information"""
    netInfo = {}
    logger = getLoggingObject(logType="StreamLogger")
    interfaces = config.get("agent", "interfaces")
    for intf in interfaces:
        nicInfo = netInfo.setdefault(intf, {})
        if config.has_option(intf, "isAlias"):
            nicInfo["isAlias"] = config.get(intf, "isAlias")
        for key in [
            "ipv4-address-pool",
            "ipv4-subnet-pool",
            "ipv6-address-pool",
            "ipv6-subnet-pool",
        ]:
            if config.has_option(intf, key):
                nicInfo[key] = config.get(intf, key)
            if config.has_option(intf, f"{key}-list"):
                nicInfo[f"{key}-list"] = config.get(intf, f"{key}-list")
        nicInfo["vlan_range"] = config.get(intf, "vlan_range")
        nicInfo["vlan_range_list"] = config.get(intf, "vlan_range_list")
        nicInfo["min_bandwidth"] = int(config.get(intf, "min_bandwidth"))
        nicInfo["max_bandwidth"] = int(config.get(intf, "max_bandwidth"))
        nicInfo["switch_port"] = replaceSpecialSymbols(str(config.get(intf, "port")))
        nicInfo["switch"] = str(config.get(intf, "switch"))
        nicInfo["shared"] = str2bool(config.get(intf, "shared"))
        nicInfo["vlans"] = {}
        # TODO. It should calculate available capacity, depending on installed vlans.
        # Currently we set it same as max_bandwidth.
        nicInfo["available_bandwidth"] = int(config.get(intf, "max_bandwidth"))  # TODO
        # TODO. It should also calculate reservable capacity depending on installed vlans;
        # Currently we set it to max available;
        nicInfo["reservable_bandwidth"] = int(config.get(intf, "max_bandwidth"))  # TODO
    tmpifAddr = psutil.net_if_addrs()
    tmpifStats = psutil.net_if_stats()
    tmpIOCount = psutil.net_io_counters(pernic=True)

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
            splName = nic.split(".")
            if len(splName) == 2:
                vlanid = int(splName[1])
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
                        logger.debug(
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
                # tmpIOCount - (bytes_sent=13839798, bytes_recv=690754706, packets_sent=151186,
                #               packets_recv=630590, errin=0, errout=0, dropin=0, dropout=0)
                familyInfo["bytes_sent"] = tmpIOCount[nic].bytes_sent
                familyInfo["bytes_received"] = tmpIOCount[nic].bytes_recv
                familyInfo["packets_sent"] = tmpIOCount[nic].packets_sent
                familyInfo["packets_recv"] = tmpIOCount[nic].packets_recv
                familyInfo["errin"] = tmpIOCount[nic].errin
                familyInfo["errout"] = tmpIOCount[nic].errout
                familyInfo["dropin"] = tmpIOCount[nic].dropin
                familyInfo["dropout"] = tmpIOCount[nic].dropout
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
        if intfName.split(".")[0] not in interfaces:
            logger.debug(
                f"This interface {intfName} was defined in configuration, but not available. Will not add it to final output"
            )
        else:
            outputForFE["interfaces"][intfName] = intfDict
    # Get Routing Information
    outputForFE["routes"] = getRoutes(logger)
    outputForFE["lldp"] = getLLDP(logger)
    return outputForFE


def getLLDP(logger):
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
                if vals.get("port", {}).get("id", {}).get("type", "") == "ifname":
                    remintf = vals["port"]["id"]["value"]
                if mac and remintf:
                    out[intf] = {
                        "remote_chassis_id": mac,
                        "remote_port_id": remintf,
                        "local_port_id": intf,
                    }
        return out
    except:
        logger.debug(
            "Failed to get lldp information with lldpcli show neighbors -f json. lldp daemon down?"
        )
    return {}


def getRoutes(logger):
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


if __name__ == "__main__":
    getLoggingObject(logType="StreamLogger", service="Agent")
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getGitConfig()))
