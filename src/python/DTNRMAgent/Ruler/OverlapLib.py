#!/usr/bin/env python3
"""Overlap Libraries to check network IP Overlaps from delta with OS IPs

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/08/29
"""
from DTNRMLibs.ipaddr import getInterfaces
from DTNRMLibs.ipaddr import getInterfaceIP
from DTNRMLibs.ipaddr import getsubnet
from DTNRMLibs.ipaddr import checkoverlap

class OverlapLib():
    """OverLap Lib - checks and prepares configs for overlap calculations"""
    # pylint: disable=E1101
    def __init__(self):
        self.allIPs = {'ipv4': {}, 'ipv6': {}}
        self.totalrequests = {}
        self.getAllIPs()

    # bps, bytes per second
    # kbps, Kbps, kilobytes per second
    # mbps, Mbps, megabytes per second
    # gbps, Gbps, gigabytes per second
    # bit, bits per second
    # kbit, Kbit, kilobit per second
    # mbit, Mbit, megabit per second
    # gbit, Gbit, gigabit per second
    # Seems there are issues with QoS when we use really big bites and it complains about this.
    # Solution is to convert to next lower value...
    def convertToRate(self, params):
        """Convert input to rate understandable to fireqos."""
        self.logger.info(f'Converting rate for QoS. Input {params}')
        inputVal, inputRate = params.get('reservableCapacity', 0), params.get('unit', 'undef')
        if inputVal == 0 and inputRate == 'undef':
            return 0, 'mbit'
        outRate = -1
        outType = ''
        if inputRate == 'bps':
            outRate = int(inputVal // 1000000)
            outType = 'mbit'
            if outRate == 0:
                outRate = int(inputVal // 1000)
                outType = 'bit'
        elif inputRate == 'mbps':
            outRate = int(inputVal)
            outType = 'mbit'
        elif inputRate == 'gbps':
            outRate = int(inputVal * 1000)
            outType = 'mbit'
        if outRate != -1:
            self.logger.info(f'Converted rate for QoS from {inputRate} {inputVal} to {outRate}')
            return outRate, outType
        raise Exception(f'Unknown input rate parameter {inputRate} and {inputVal}')

    def __getAllIPsHost(self):
        """Get All IPs on the system"""
        for intf in getInterfaces():
            for intType, intDict in getInterfaceIP(intf).items():
                if int(intType) == 2:
                    for ipv4 in intDict:
                        address = f"{ipv4.get('addr')}/{ipv4.get('netmask')}"
                        self.allIPs['ipv4'].setdefault(address, [])
                        self.allIPs['ipv4'][address].append({'intf': intf, 'master': intf})
                elif int(intType) == 10:
                    for ipv6 in intDict:
                        address = f"{ipv6.get('addr')}/{ipv6.get('netmask').split('/')[1]}"
                        self.allIPs['ipv6'].setdefault(address, [])
                        self.allIPs['ipv6'][address].append({'intf': intf, 'master': intf})

    def __getAllIPsNetNS(self):
        """Mapping for Private NS comes from Agent configuration"""
        if not self.config.has_section('qos'):
            return
        if not self.config.has_option('qos', 'interfaces'):
            return
        for intf, params in self.config.get('qos', 'interfaces').items():
            for key in ['ipv6', 'ipv4']:
                iprange = params.get(f'{key}_range')
                if iprange:
                    self.allIPs[key].setdefault(iprange, [])
                    self.allIPs[key][iprange].append({'master': params['master_intf'],
                                                      'intf': intf})

    def getAllIPs(self):
        """Get all IPs"""
        self.allIPs = {'ipv4': {}, 'ipv6': {}}
        self.__getAllIPsHost()
        self.__getAllIPsNetNS()

    @staticmethod
    def networkOverlap(net1, net2):
        """Check if 2 networks overlap"""
        try:
            net1Net = getsubnet(net1, strict=False)
            net2Net = getsubnet(net2, strict=False)
            if checkoverlap(net1Net, net2Net):
                return True
        except ValueError:
            pass
        return False

    def findOverlaps(self, iprange, iptype):
        """Find all networks which overlap and add it to service list"""
        for ipPresent in self.allIPs.get(iptype, []):
            if self.networkOverlap(iprange, ipPresent):
                return ipPresent.split('/')[0], self.allIPs[iptype][ipPresent]
        return None, None

    def getAllOverlaps(self, activeDeltas):
        """Get all overlaps"""
        self.getAllIPs()
        self.totalrequests = {}
        overlapServices = {}
        for _key, vals in activeDeltas.get('output', {}).get('rst', {}).items():
            for _, ipDict in vals.items():
                for iptype, routes in ipDict.items():
                    if 'hasService' not in routes:
                        continue
                    bwuri = routes['hasService']['bwuri']
                    for _, routeInfo in routes.get('hasRoute').items():
                        iprange = routeInfo.get('routeFrom', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
                        ipVal, intfArray = self.findOverlaps(iprange, iptype)
                        if ipVal and intfArray:
                            for intfName in intfArray:
                                service = overlapServices.setdefault(intfName['intf'], {})
                                intServ = service.setdefault(bwuri, {'src_ipv4': '',
                                                                     'src_ipv4_intf': '',
                                                                     'src_ipv6': '',
                                                                     'src_ipv6_intf': '',
                                                                     'dst_ipv4': '',
                                                                     'dst_ipv6': '',
                                                                     'master_intf': '',
                                                                     'rules': ''})
                                intServ[f"src_{iptype}"] = ipVal
                                intServ[f"src_{iptype}_intf"] = intfName['intf']
                                intServ["master_intf"] = intfName['master']
                                resvRate, _ = self.convertToRate(routes['hasService'])
                                self.totalrequests.setdefault(intfName['master'], 0)
                                self.totalrequests[intfName['master']] += resvRate
                                # Add dest IPs to overlap info
                                iprange = routeInfo.get('routeTo', {}).get(f'{iptype}-prefix-list', {}).get('value', None)
                                intServ[f"dst_{iptype}"] = iprange
                                intServ['rules'] = routes['hasService']
        return overlapServices
