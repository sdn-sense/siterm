#!/usr/bin/env python3
"""Overlap Libraries to check network IP Overlaps from delta with OS IPs

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/08/29
"""
import ipaddress
import netifaces


def getAllIPs():
    """Get All IPs on the system"""
    allIPs = {'ipv4': {}, 'ipv6': {}}
    for intf in netifaces.interfaces():
        for intType, intDict in netifaces.ifaddresses(intf).items():
            if int(intType) == 2:
                for ipv4 in intDict:
                    address = f"{ipv4.get('addr')}/{ipv4.get('netmask')}"
                    allIPs['ipv4'][address] = intf
            elif int(intType) == 10:
                for ipv6 in intDict:
                    address = f"{ipv6.get('addr')}/{ipv6.get('netmask').split('/')[1]}"
                    allIPs['ipv6'][address] = intf
    return allIPs


def networkOverlap(net1, net2):
    """Check if 2 networks overlap"""
    try:
        net1Net = ipaddress.ip_network(net1, strict=False)
        net2Net = ipaddress.ip_network(net2, strict=False)
        if net1Net.overlaps(net2Net):
            return True
    except ValueError:
        pass
    return False


def findOverlaps(service, iprange, allIPs, iptype):
    """Find all networks which overlap and add it to service list"""
    for ipPresent in allIPs.get(iptype, []):
        if networkOverlap(iprange, ipPresent):
            service[f"src_{iptype}"] = ipPresent.split('/')[0]
            service[f"src_{iptype}_intf"] = allIPs[iptype][ipPresent]
            break


def getAllOverlaps(activeDeltas):
    """Get all overlaps"""
    allIPs = getAllIPs()
    overlapServices = {}
    for _key, vals in activeDeltas.get('output', {}).get('rst', {}).items():
        for _, ipDict in vals.items():
            for iptype, routes in ipDict.items():
                if 'hasService' not in routes:
                    continue
                service = overlapServices.setdefault(routes['hasService']['bwuri'],
                                                     {'src_ipv4': "",
                                                      'src_ipv4_intf': "",
                                                      'src_ipv6': "",
                                                      'src_ipv6_intf': "",
                                                      'dst_ipv4': "",
                                                      'dst_ipv6': "",
                                                      'rules': {}})
                service['rules'] = routes['hasService']
                for _, routeInfo in routes.get('hasRoute').items():
                    iprange = routeInfo.get('routeFrom', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
                    findOverlaps(service, iprange, allIPs, iptype)
                    # Add dest IPs to overlap info
                    iprange = routeInfo.get('routeTo', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
                    service[f"dst_{iptype}"] = iprange
    return overlapServices
