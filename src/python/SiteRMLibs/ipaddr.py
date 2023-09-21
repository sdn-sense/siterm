#!/usr/bin/env python3
"""
General functions for ipaddress

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/08
"""
import netifaces
from ipaddress import ip_address, ip_network


def getInterfaces():
    """Get all interface names"""
    return netifaces.interfaces()


def getInterfaceIP(interface):
    """Get Interface IP"""
    return netifaces.ifaddresses(interface)


def normalizedipwithnet(ipInput, netmask):
    """Normalize IP with separate netmask"""
    tmp = ipInput.split('/')
    if len(tmp) >= 2:
        return normalizedip(ipInput)
    tmpNet = netmask.split('/')
    return normalizedip(f"{ipInput}/{tmpNet[1]}")


def normalizedip(ipInput):
    """
    Normalize IPv6 address. It can have leading 0 or not and both are valid.
    This function will ensure same format is used.
    """
    tmp = ipInput.split('/')
    ipaddr = None
    try:
        ipaddr = ip_address(tmp[0]).compressed
    except ValueError:
        ipaddr = tmp[0]
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
    tmpIP = ipInput.split('/')
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
    for repl in [[" ", "_"], ["/", "-"], ['"', ''], ["'", ""], [":", "__"]]:
        valIn = valIn.replace(repl[0], repl[1])
    return valIn

def validMRMLName(valIn):
    """Generate valid MRML Name for ipv6 value"""
    # In case of IPv6, it does allow multiple ways to list IP address, like:
    # 2001:0DB8:0000:CD30:0000:0000:0000:0000/60
    # 2001:0DB8::CD30:0:0:0:0/60
    # 2001:0DB8:0:CD30::/60
    # See https://datatracker.ietf.org/doc/html/rfc4291.html
    # Because of this - we always use a short version
    if ipVersion(valIn) == 6:
        valIn = ip_address(valIn.split('/')[0]).compressed
    replaceSpecialSymbols(valIn)
