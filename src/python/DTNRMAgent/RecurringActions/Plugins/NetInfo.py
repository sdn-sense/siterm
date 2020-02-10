#!/usr/bin/env python
"""
Plugin which gathers everything about all NICs

Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2016 California Institute of Technology
Date			: 2017/09/26
"""
import ipaddress
import pprint
import psutil
from pyroute2 import IPRoute
from DTNRMAgent.RecurringActions.Utilities import externalCommand
from DTNRMLibs.MainUtilities import getConfig

def str2bool(val):
    return val.lower() in ("yes", "true", "t", "1")

NAME = 'NetInfo'
# Custom Functions append values to Summary part of dictionary
#CUSTOM_FUNCTIONS = {'vlan_count': getVlanCount}

def get(config):
    """Get all network information"""
    netInfo = {}
    interfaces = config.get('agent', "interfaces").split(",")
    for intf in interfaces:
        nicInfo = netInfo.setdefault(intf, {})
        vlan_range = config.get(intf, "vlans")
        vlan_min = config.get(intf, "vlan_min")
        vlan_max = config.get(intf, "vlan_max")
        switch_port = config.get(intf, "port")
        switch = config.get(intf, "switch")
        shared_interface = config.get(intf, "shared")
        if config.has_option(intf, 'isAlias'):
            nicInfo['isAlias'] = config.get(intf, 'isAlias')
        if config.has_option(intf, "ips"):
            nicInfo['ipv4-floatingip-pool'] = config.get(intf, "ips")
        nicInfo['vlan_range'] = vlan_range
        nicInfo['min_bandwidth'] = int(vlan_min)
        nicInfo['max_bandwidth'] = int(vlan_max)
        nicInfo['switch_port'] = str(switch_port).replace('/', '_')
        nicInfo['switch'] = str(switch)
        nicInfo['shared'] = str2bool(shared_interface)
        nicInfo['vlans'] = {}
        # TODO. It should calculate available capacity, depending on installed vlans.
        # Currently we set it same as max_bandwidth.
        nicInfo['available_bandwidth'] = int(vlan_max)  # TODO
        # TODO. It should also calculate reservable capacity depending on installed vlans;
        # Currently we set it to max available;
        nicInfo['reservable_bandwidth'] = int(vlan_max)  # TODO
    print netInfo
    tmpifAddr = psutil.net_if_addrs()
    tmpifStats = psutil.net_if_stats()
    tmpIOCount = psutil.net_io_counters(pernic=True)
    foundInterfaces = []
    for nic, addrs in tmpifAddr.items():
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
            familyInfo = nicInfo.setdefault(str(vals.family), {})
            # vals - family=2, address='127.0.0.1', netmask='255.0.0.0', broadcast=None, ptp=None
            # For family more information look here: http://lxr.free-electrons.com/source/include/linux/socket.h#L160
            familyInfo["family"] = vals.family
            familyInfo["address"] = vals.address
            familyInfo["netmask"] = vals.netmask
            if int(vals.family) in [2, 10] and vals.address and vals.netmask:
                try:
                    ipwithnetmask = ipaddress.ip_interface(u"%s/%s" % (vals.address, vals.netmask))
                    if isinstance(ipwithnetmask, ipaddress.IPv4Interface):
                        familyInfo["ipv4-address"] = str(ipwithnetmask)
                    elif isinstance(ipwithnetmask, ipaddress.IPv6Interface):
                        familyInfo["ipv6-address"] = str(ipwithnetmask)
                    else:
                        print "This type was not understood by the system. Type: %s and value: %s" % (type(ipwithnetmask), str(ipwithnetmask))
                except ValueError as ex:
                    print 'Got an exception %s' % ex
            elif int(vals.family) in [17]:
                familyInfo["mac-address"] = vals.address
            familyInfo["broadcast"] = vals.broadcast
            familyInfo["ptp"] = vals.ptp
            # tmpifStats - snicstats(isup=True, duplex=0, speed=0, mtu=1500)
            if vals.family == 2:
                familyInfo["UP"] = tmpifStats[nic].isup
                familyInfo["duplex"] = tmpifStats[nic].duplex
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
    # Check in the end which interfaces where defined in config but not available...
    outputForFE = {"interfaces": {}, "routes": []}
    for intfName, intfDict in netInfo.iteritems():
        if intfName.split('.')[0] not in foundInterfaces:
            print 'This interface was defined in configuration, but not available. Will not add it to final output'
            print intfName, intfDict
        else:
            outputForFE["interfaces"][intfName] = intfDict
    # Get Routing Information
    outputForFE["routes"] = getRoutes(config)
    return outputForFE

def getRoutes(config):
    # Get Routing Information
    routes = []
    with IPRoute() as ipr:
        for route in ipr.get_routes(table=254, family=2):
            newroute = {"dst_len": route['dst_len']}
            for item in route['attrs']:
                if item[0] in ['RTA_GATEWAY', 'RTA_DST', 'RTA_PREFSRC']:
                    newroute[item[0]] = item[1]
            routes.append(newroute)
    print routes
    return routes

def getVlanCount(config):
    """ Custom function to get vlanCount """
    # Count all vlans as if there are multiple interfaces it can have different on each
    out = get(config)
    vlanCount = 0
    for intfName, intfDict in out.iteritems():
        if not isinstance(intfDict, dict):
            continue
        if not intfDict['provisioned']:
            vlanCount += len(intfDict['vlans'])
    return vlanCount

if __name__ == "__main__":
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get(getConfig(['/etc/dtnrm/main.conf', 'main.conf'])))
