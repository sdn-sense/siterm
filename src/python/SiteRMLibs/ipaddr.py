#!/usr/bin/env python3
"""
General functions for ipaddress

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/08
"""
from ipaddress import (AddressValueError, IPv4Network, IPv6Network, ip_address,
                       ip_network)
import psutil
import netifaces
from SiteRMLibs.MainUtilities import externalCommand


def getMasterSlaveInterfaces():
    """Get dictionary of slaveIntfName: MasterIntfName interfaces"""
    out = {}
    nics = externalCommand("ip -br a")
    for nicline in nics[0].decode("UTF-8").split("\n"):
        if not nicline:
            continue
        nictmp = nicline.split()[0].split("@")
        if len(nictmp) == 1:
            out.setdefault(nictmp[0], "")
        elif len(nictmp) == 2:
            out.setdefault(nictmp[0], nictmp[1])
    return out


def getInterfaces():
    """Get all interface names"""
    return netifaces.interfaces()

def getInterfaceTxQueueLen(interface):
    """Get Interface Tx Queue Length"""
    txQueueLen = externalCommand(f"cat /sys/class/net/{interface}/tx_queue_len")
    return int(txQueueLen[0].strip())

def getIfAddrStats():
    """Get Interface Address Stats"""
    tmpifAddr = psutil.net_if_addrs()
    tmpifStats = psutil.net_if_stats()
    return tmpifAddr, tmpifStats

def getInterfaceIP(interface):
    """Get Interface IP"""
    out = {}
    try:
        out = netifaces.ifaddresses(interface)
    except ValueError:
        pass
    return out


def getNetmaskBits(netmask):
    """Get Netmask Bits"""
    return sum([bin(int(x)).count("1") for x in netmask.split(".")])


def normalizedipwithnet(ipInput, netmask):
    """Normalize IP with separate netmask"""
    tmp = ipInput.split("/")
    if len(tmp) >= 2:
        return normalizedip(ipInput)
    tmpNet = netmask.split("/")
    return normalizedip(f"{ipInput}/{tmpNet[1]}")


def normalizeipdict(ipdict):
    """Normalize IP in a dictionary"""
    if isinstance(ipdict, dict) and "address" in ipdict:
        tmpval = normalizedip(ipdict["address"])
        ipdict["address"] = tmpval
    return ipdict


def normalizedip(ipInput):
    """
    Normalize IPv6 address. It can have leading 0 or not and both are valid.
    This function will ensure same format is used.
    """
    ipaddr = None
    try:
        tmp = ipInput.split("/")
        ipaddr = ip_address(tmp[0]).exploded
    except ValueError:
        ipaddr = tmp[0]
    except AttributeError:
        return None
    ipaddr = _ipv6InJavaFormat(ipaddr)
    if len(tmp) == 2:
        return f"{ipaddr}/{tmp[1]}"
    if len(tmp) == 1:
        return ipaddr
    # We return what we get here, because it had multiple / (which is not really valid)
    return ipInput


def getsubnet(ipInput, strict=False):
    """Get subnet if IP address"""
    return ip_network(ipInput, strict=strict).compressed


def checkoverlap(net1, net2):
    """Check if two networks overlap. Return True/False."""
    try:
        return ip_network(net1).overlaps(ip_network(net2))
    except ValueError:
        return False


def ipVersion(ipInput, strict=False):
    """Check if IP is valid.
    Input: str
    Returns: (one of) IPv4, IPv6, Invalid"""
    version = -1
    try:
        version = ip_network(ipInput, strict=strict).version
    except ValueError:
        pass
    if version != -1:
        return version
    tmpIP = ipInput.split("/")
    try:
        version = ip_address(tmpIP[0]).version
    except ValueError:
        pass
    return version


def getBroadCast(inIP):
    """Return broadcast IP."""
    myNet = ip_network(str(inIP), strict=False)
    return str(myNet.broadcast_address)


def replaceSpecialSymbols(valIn):
    """Replace all symbols [:/'" ] as they not supported in mrml tag"""
    for repl in [[" ", "_"], ["/", "-"], ['"', ""], ["'", ""], [":", "__"]]:
        valIn = valIn.replace(repl[0], repl[1])
    return valIn


def _ipv6InJavaFormat(ipinput):
    """Return IPv6 address in Java expected output format.
    2001:0DB8:0000:0D30:0000:0000:0000:0000 becomes
    2001:DB8:0:CD30:0:0:0:0
    """
    out = []
    for item in ipinput.split(":"):
        tmpval = str(item)
        tmparr = []
        stoploop = False
        for i in enumerate(tmpval):
            if not stoploop:
                if i[1] != "0":
                    tmparr.append(i[1])
                    stoploop = True
                continue
            tmparr.append(i[1])
        if not tmparr:
            tmparr.append("0")
        out.append("".join(tmparr))
    return ":".join(out)


def validMRMLName(valIn):
    """Generate valid MRML Name for ipv6 value"""
    # In case of IPv6, it does allow multiple ways to list IP address, like:
    # 2001:0DB8:0000:CD30:0000:0000:0000:0000/60
    # 2001:0DB8::CD30:0:0:0:0/60
    # 2001:0DB8:0:CD30::/60
    # See https://datatracker.ietf.org/doc/html/rfc4291.html
    # Because of this - we always use a short version
    if ipVersion(valIn) == 6:
        tmpspl = valIn.split("/")
        longip = _ipv6InJavaFormat(ip_address(tmpspl[0]).exploded)
        if len(tmpspl) == 2:
            return f"{longip}_{tmpspl[1]}".replace(":", "_")
        return f"{longip}".replace(":", "_")
    return replaceSpecialSymbols(valIn)


def checkOverlap(inrange, ipval, iptype):
    """Check if overlap"""
    overlap = False
    for vrange in inrange:
        overlap = ipOverlap(vrange, ipval, iptype)
        if overlap:
            return overlap
    return overlap


def ipOverlap(ip1, ip2, iptype):
    """Check if IP Overlap. Return True/False"""

    def ipv4Wrapper(ipInput):
        """IPv4 Wrapper to check if IP Valid."""
        try:
            return IPv4Network(ipInput, False)
        except AddressValueError:
            return False

    def ipv6Wrapper(ipInput):
        """IPv6 Wrapper to check if IP Valid."""
        try:
            return IPv6Network(ipInput, False)
        except AddressValueError:
            return False

    overlap = False
    if not ip1 or not ip2:
        return overlap
    if iptype == "ipv4":
        net1 = ipv4Wrapper(ip1)
        net2 = ipv4Wrapper(ip2)
        overlap = net1.subnet_of(net2) or net2.subnet_of(net1)
    if iptype == "ipv6":
        net1 = ipv6Wrapper(ip1)
        net2 = ipv6Wrapper(ip2)
        overlap = net1.subnet_of(net2) or net2.subnet_of(net1)
    return overlap
