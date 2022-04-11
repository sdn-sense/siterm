#!/usr/bin/env python3
"""Plugin which gathers everything about all NICs.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/29
"""
from __future__ import print_function
import ipaddress
import pprint
import psutil
from pyroute2 import IPRoute
from DTNRMAgent.RecurringActions.Utilities import externalCommand
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getLoggingObject


def str2bool(val):
    """Check if str is true boolean."""
    return val.lower() in ("yes", "true", "t", "1")

NAME = 'NetInfo'


def presetMacVlans(netInfo, mainIntf, config):
    for macvlan in config.get(mainIntf, 'macvlans').split(','):
        nicInfo = netInfo.setdefault(macvlan, {})
        nicInfo['parent'] = mainIntf
        nicInfo['switch_port'] = str(config.get(mainIntf, "port")).replace('/', '-').replace(' ', '_')
        nicInfo['switch'] = str(config.get(mainIntf, "switch"))
        nicInfo['shared'] = str2bool(config.get(mainIntf, "shared"))

def get(config):
    """Get all network information."""
    netInfo = {}
    interfaces = config.get('agent', "interfaces").split(",")
    for intf in interfaces:
        nicInfo = netInfo.setdefault(intf, {})
        if config.has_option(intf, 'isAlias'):
            nicInfo['isAlias'] = config.get(intf, 'isAlias')
        for key in ['ipv4-address-pool', 'ipv4-subnet-pool', 'ipv6-address-pool', 'ipv6-subnet-pool']:
            if config.has_option(intf, key):
                nicInfo[key] = config.get(intf, key)
        if config.has_option(intf, 'macvlans'):
            presetMacVlans(netInfo, intf, config)
        nicInfo['vlan_range'] = config.get(intf, "vlans")
        nicInfo['min_bandwidth'] = int(config.get(intf, "vlan_min"))
        nicInfo['max_bandwidth'] = int(config.get(intf, "vlan_max"))
        nicInfo['switch_port'] = str(config.get(intf, "port")).replace('/', '-').replace(' ', '_')
        nicInfo['switch'] = str(config.get(intf, "switch"))
        nicInfo['shared'] = str2bool(config.get(intf, "shared"))
        nicInfo['vlans'] = {}
        # TODO. It should calculate available capacity, depending on installed vlans.
        # Currently we set it same as max_bandwidth.
        nicInfo['available_bandwidth'] = int(config.get(intf, "vlan_max"))  # TODO
        # TODO. It should also calculate reservable capacity depending on installed vlans;
        # Currently we set it to max available;
        nicInfo['reservable_bandwidth'] = int(config.get(intf, "vlan_max"))  # TODO
    tmpifAddr = psutil.net_if_addrs()
    tmpifStats = psutil.net_if_stats()
    tmpIOCount = psutil.net_io_counters(pernic=True)
    foundInterfaces = []
    for nic, addrs in list(tmpifAddr.items()):
        # TODO: Check with configuration of which vlans are provisioned;
        # Currently it is a hack. if it is a vlan, I assume it is provisioned by orchestrator;
        nicSplit = nic.split('.')
        nicInfo = netInfo.setdefault(nicSplit[0], {'vlans': {}})
        if len(nicSplit) == 2:
            nicInfo = nicInfo['vlans'].setdefault(nic, {})
            nicInfo['provisioned'] = True
            nicInfo['vlanid'] = nicSplit[1]
        else:
            nicInfo['provisioned'] = False
        foundInterfaces.append(nic)
        for vals in addrs:
            nicInfo.setdefault(str(vals.family.value), [])
            familyInfo = {}
            # vals - family=2, address='127.0.0.1', netmask='255.0.0.0', broadcast=None, ptp=None
            # For family more information look here: http://lxr.free-electrons.com/source/include/linux/socket.h#L160
            familyInfo["family"] = vals.family.value
            familyInfo["address"] = vals.address
            familyInfo["netmask"] = vals.netmask
            if int(vals.family.value) in [2, 10] and vals.address and vals.netmask:
                try:
                    ipwithnetmask = ipaddress.ip_interface(u"%s/%s" % (vals.address, vals.netmask))
                    if isinstance(ipwithnetmask, ipaddress.IPv4Interface):
                        familyInfo["ipv4-address"] = str(ipwithnetmask)
                    elif isinstance(ipwithnetmask, ipaddress.IPv6Interface):
                        familyInfo["ipv6-address"] = str(ipwithnetmask)
                    else:
                        logger.debug("This type was not understood by the system. Type: %s and value: %s" %  \
                                     (type(ipwithnetmask), str(ipwithnetmask)))
                except ValueError as ex:
                    logger.debug('Got an exception %s' % ex)
            elif int(vals.family.value) in [17]:
                familyInfo["mac-address"] = vals.address
            familyInfo["broadcast"] = vals.broadcast
            familyInfo["ptp"] = vals.ptp
            # tmpifStats - snicstats(isup=True, duplex=0, speed=0, mtu=1500)
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
                nicType = externalCommand('cat /sys/class/net/' + nic + "/type")
                familyInfo["Type"] = nicType[0].strip()
                txQueueLen = externalCommand('cat /sys/class/net/' + nic + "/tx_queue_len")
                familyInfo["txqueuelen"] = txQueueLen[0].strip()
            nicInfo[str(vals.family.value)].append(familyInfo)
    # Check in the end which interfaces where defined in config but not available...
    outputForFE = {"interfaces": {}, "routes": []}
    for intfName, intfDict in netInfo.items():
        if intfName.split('.')[0] not in foundInterfaces:
            logger.debug('This interface was defined in configuration, but not available. Will not add it to final output')
        else:
            outputForFE["interfaces"][intfName] = intfDict
    # Get Routing Information
    outputForFE["routes"] = getRoutes()
    return outputForFE


def getRoutes():
    """Get Routing information from host."""
    routes = []
    with IPRoute() as ipr:
        for route in ipr.get_routes(table=254, family=2):
            newroute = {"dst_len": route['dst_len'], 'iptype': 'ipv4'}
            for item in route['attrs']:
                if item[0] in ['RTA_GATEWAY', 'RTA_DST', 'RTA_PREFSRC']:
                    newroute[item[0]] = item[1]
            routes.append(newroute)
        for route in ipr.get_routes(table=254, family=10):
            newroute = {"dst_len": route['dst_len'], 'iptype': 'ipv6'}
            for item in route['attrs']:
                # TODO: Need to test this. New feature of node assign IPv6
                if item[0] in ['RTA_GATEWAY', 'RTA_DST', 'RTA_PREFSRC']:
                    newroute[item[0]] = item[1]
            routes.append(newroute)
    return routes

if __name__ == "__main__":
    getLoggingObject(logType='StreamLogger')
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig()))
