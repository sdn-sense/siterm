#!/usr/bin/env python3
"""
General functions for ipaddress

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/08
"""
from ipaddress import ip_address, IPv4Address



def ipVersion(ipInput):
    """ Check if IP is valid.
        Input: str
        Returns: (one of) IPv4, IPv6, Invalid"""
    tmpIP = ipInput.split('/')
    try:
        return ip_address(tmpIP[0]).version
    except ValueError:
        return -1


def validMRMLName(valIn, ipType='ipv4'):
    """ Generate valid MRML Name. [:/ ] not supported """
    # In case of IPv6, it does allow multiple ways to list IP address, like:
    # 2001:0DB8:0000:CD30:0000:0000:0000:0000/60
    # 2001:0DB8::CD30:0:0:0:0/60
    # 2001:0DB8:0:CD30::/60
    # See https://datatracker.ietf.org/doc/html/rfc4291.html
    # Because of this - we always use a short version
    if ipVersion(valIn) == 6:
        valIn = ip_address(valIn.split('/')[0]).compressed
    for repl in [[':', '_'], ['/', '_'], [' ', '_']]:
        valIn = valIn.replace(repl[0], repl[1])
    return valIn