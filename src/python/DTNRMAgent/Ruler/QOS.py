#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Throughput fairshare calculation:
In SENSE, there can be multiple QoS Requests:
End-to-End Path directly to a single DTN with QOS
L3 Path between Routers - where QoS is requested for an IP Range (There might be 1 to many servers behind same IP Range)

QOS Walkthrough:
1. Get all Rules from FE;
2. Get all info about endhost capabilities;
3. Apply all End-To-End QoS (hard qos) - hard qos means no one else can use that specific throughput.
4. Sum all L3 Requests and if any of EndHost IPs are with-in requested range - it will use it for step 5/6
5. For each L3 add soft QoS - min = L3Requested * RemainingTraffic / TotalRSTRequested; max = RemainingTraffic
6. Add default rule for any other traffic - min = (config parameter public_intf_def or 100mbit), max = RemainingTraffic / (TotalRSTRequestedCount + 1)

Scenario 1:
Site uplink is 100gbps, 1 DTN - 100gbps.
If Requested path is End-To-End for 10gbps - SiteRM will create vlan with hard QoS for 10gbps for specific vlan.
Remaining 90gbps will be for any other traffic or default traffic.

Scenario 2:
Site uplink is 10gbps, 1 DTN - 10gbps.
If Requested path is End-To-End for 9gbps - SiteRM will create vlan with hard QoS for 9gbps for specific vlan.
Remaining 1gbps will be for any other traffic or default traffic.

Scenario 3:
Site uplink is 10gbps, 1 DTN - 10gbps.
If Requested path is End-To-End for 10gbps - SiteRM Agent will fail to apply rules and will not add QoS.
It exceeds the requirement. In future (TODO) - this will be prechecked in Frontend and delta request will not be accepted.

Scenario 4:
Site uplink is 100gbps, 10 DTN - each 10gbps.
There 1 End-To-End QoS 1gbps Request on the system. (For End-To-End request to specific DTN - Scenario's 1,2,3 apply.)
Once End-To-End QoS added - all remaining traffic can be fairshared for L3 QoS (L3 Path between Routers). In this case:
If only 1 new L3 Path requested for 50gbps - Site Uplink is capable, but Servers are not. Formula in this case on DTN is:
    TotalDTNSpeed - MinDefault - AllEnd-To-EndLimits = RemainingTraffic
    10gbps - 1gbps - 1gbps(if only 1 end-to-end vlan requested) = 8gbps
    NewRate = L3Requested * RemainingTraffic / TotalRSTRequested
    NewRate = 50gbps * 8 / 50
In this case - All Agents (which have that specific IPv6 address) - will put 8gbps priority for matching ipv6 addresses.

Scenario 5:
Site uplink is 100gbps, 10 DTN - each 10gbps.
There 1 End-To-End QoS 1gbps Request on the system. (For End-To-End request to specific DTN - Scenario's 1,2,3 apply.)
Once End-To-End QoS added - all remaining traffic can be fairshared for L3 QoS (L3 Path between Routers). In this case:
Lets say we have 3 L3 Path requested for diff ranges (1st - 10gbps, 2nd - 20gbps, 3rd - 50gbps). Site uplink is capable to support that,
but DTNs each are limited to 10gbps. Formula in this case on DTN is:
    TotalDTNSpeed - MinDefault - AllEnd-To-EndLimits = RemainingTraffic
    10gbps - 1gbps - 1gbps(if only 1 end-to-end vlan requested) = 8gbps
    NewRate = L3Requested * RemainingTraffic / TotalRSTRequested
    NewRate1st = 10gbps * 8 / 80 = 1gbps
    NewRate2nd = 20gbps * 8 / 80 = 2gbps
    NewRate3rd = 50gbps * 8 / 80 = 5gbps

P.S. In case RemainingTraffic >= TotalRSTRequested - Formula not used and RequestedForRST is Returned. If RST Requested 5gbps,
and server has 8gbps remaining - 5gbps will be added to QoS rules. This is not ideal in case there are 10 servers behind and each capable 10gbps -
because all of them will have 5gbps QoS. SENSE In this case has no knowledge which server will be used for data transfer and limiting QoS
must be done on the network side (Either Site Router, or ESNet).


Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
from __future__ import division
import os
import copy
import tempfile
import filecmp
import shutil
import ipaddress
import netifaces
from DTNRMLibs.MainUtilities import createDirs, contentDB
from DTNRMLibs.MainUtilities import execute as executeCmd
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getFileContentAsJson
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import ConfigException
from DTNRMLibs.CustomExceptions import OverSubscribeException

COMPONENT = 'QOS'

def getAllIPs():
    """Get All IPs on the system"""
    allIPs = {'ipv4': [], 'ipv6': []}
    for intf in netifaces.interfaces():
        for intType, intDict in netifaces.ifaddresses(intf).items():
            if int(intType) == 2:
                for ipv4 in intDict:
                    address = "%s/%s" % (ipv4.get('addr'), ipv4.get('netmask'))
                    allIPs['ipv4'].append(address)
            elif int(intType) == 10:
                for ipv6 in intDict:
                    address = "%s/%s" % (ipv6.get('addr'), ipv6.get('netmask').split("/")[1])
                    allIPs['ipv6'].append(address)
    return allIPs
        #{17: [{'addr': '00:25:90:94:8c:0d', 'broadcast': 'ff:ff:ff:ff:ff:ff'}],
        # 2: [{'addr': '198.32.43.14', 'netmask': '255.255.255.0', 'broadcast': '198.32.43.255'}],
        # 10: [{'addr': '2605:d9c0:2:10::2', 'netmask': 'ffff:ffff:ffff:fff0::/60'},
        #    {'addr': 'fe80::225:90ff:fe94:8c0d%enp5s0f1.43', 'netmask': 'ffff:ffff:ffff:ffff::/64'}]}

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
            service[iptype].append(ipPresent.split('/')[0])

class QOS():
    """QOS class to install new limit rules."""
    def __init__(self, config):
        self.config = config if config else getConfig()
        self.logger = getLoggingObject(config=self.config, service='QOS')
        self.workDir = self.config.get('general', 'private_dir') + "/DTNRM/RulerAgent/"
        self.hostname = self.config.get('agent', 'hostname')
        createDirs(self.workDir)
        self.agentdb = contentDB(config=self.config)
        self.activeDeltas = {}
        self.params = {}

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
        # ['unit'], int(inputDict['params']['reservableCapacity']
        # ['unit'], int(servParams['rules']['reservableCapacity'])
        """Convert input to rate understandable to fireqos."""
        self.logger.info('Converting rate for QoS. Input %s' % params)
        inputVal, inputRate = params['reservableCapacity'], params['unit']
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
            self.logger.info('Converted rate for QoS from %s %s to %s' % (inputRate, inputVal, outRate))
            return outRate, outType
        raise Exception('Unknown input rate parameter %s and %s' % (inputRate, inputVal))

    def restartQos(self):
        """Restart QOS service"""
        self.logger.info("Restarting fireqos rules")
        executeCmd("fireqos clear_all_qos", self.logger)
        executeCmd("fireqos start", self.logger)

    def getMaxThrg(self):
        """Get Maximum set throughput and add QoS on it."""
        if self.config.has_option('agent', 'public_intf'):
            if self.config.has_option('agent', 'public_intf_def'):
                self.logger.info("Getting def class default throughput")
                self.params['defThrgIntf'] = self.config.get('agent', 'public_intf_def')
            else:
                self.params['defThrgIntf'] = 100
            self.params['defThrgType'] = 'mbit'
            if self.config.has_option('agent', 'public_intf_max'):
                self.logger.info("Getting max interface throughput")
                self.params['intfName'] = self.config.get('agent', 'public_intf')
                self.params['maxThrgIntf'] = int(self.config.get('agent', 'public_intf_max'))
                if self.params['maxThrgIntf'] <= 0:
                    raise ConfigException('ConfigError: Remaining throughtput is <= 0: %s' % self.params['maxThrgIntf'])
            else:
                raise ConfigException('ConfigError: Public Interface max speed undefined. See public_intf_max config param')
        else:
            raise ConfigException('ConfigError: Public Interface not defined. See public_intf config param')


    @staticmethod
    def _started(inConf):
        """Check if service started"""
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return True
        if 'start' in timings and getUTCnow() < timings['start']:
            return False
        return True

    def getConf(self):
        """Get conf from local file"""
        activeDeltasFile = "%s/activedeltas.json" % self.workDir
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)

    @staticmethod
    def _getvlanlistqos(inParams):
        """Get vlan qos dict"""
        vlans = []
        for key, vals in inParams.items():
            vlan = {}
            vlan['destport'] = key
            vlan['vlan'] = vals.get('hasLabel', {}).get('value', '')
            vlan['params'] = vals.get('hasService', {})
            vlans.append(vlan)
        return vlans

    def getAllQOSed(self):
        """Read all configs and prepare qos doc."""
        self.logger.info("Getting All QoS rules.")
        self.getConf()
        self.getParams()
        fName = ""
        with tempfile.NamedTemporaryFile(delete=False, mode="w+") as tmpFile:
            fName = tmpFile.name
            self.addVlanQoS(tmpFile)
            if self.params['l3enabled']:
                self.addRSTQoS(tmpFile)
        return fName

    def getParams(self):
        """Get all params from Host Config"""
        self.logger.info("Getting All Params from config file.")
        self.params = {}
        try:
            self.getMaxThrg()
            self.params['maxtype'] = 'mbit'
            self.params['maxThrgRemaining'] = self.params['maxThrgIntf'] - self.params['defThrgIntf']
            self.params['maxName'] =  "%(maxThrgIntf)s%(maxtype)s" % self.params
            self.params['l3enabled'] = True
        except ConfigException as ex:
            print('L3 DTN Config public intf not defined. Will not add QoS for L3. Exception %s' % ex)
            self.params['l3enabled'] = False

    def addVlanQoS(self, tmpFD):
        """Add Vlan BW Request parameters"""
        inputDicts = []
        for _key, vals in self.activeDeltas.get('output', {}).get('vsw', {}).items():
            if self.hostname in vals:
                if not self._started(vals):
                    # This resource has not started yet. Continue.
                    continue
                inputDicts += self._getvlanlistqos(vals[self.hostname])

        for inputDict in inputDicts:
            inputName = "%s%sIn" % (inputDict['destport'], inputDict['vlan'])
            outputName = "%s%sOut" % (inputDict['destport'], inputDict['vlan'])
            if not inputDict['params']:
                self.logger.info('This specific vlan request did not provided any QOS. Ignoring QOS Rules for it')
                continue
            outrate, outtype = self.convertToRate(inputDict['params'])
            if self.params['maxThrgRemaining'] - outrate <= 0:
                raise OverSubscribeException("Node is oversubscribed. Will not modify present QoS.")
            tmpFD.write("# SENSE CREATED VLAN %s %s %s %s\n" % (inputDict['vlan'],
                                                                inputDict['destport'],
                                                                outrate, outtype))
            tmpFD.write("interface vlan.%s %s input rate %s%s\n" % (inputDict['vlan'],
                                                                    inputName, outrate, outtype))
            tmpFD.write("interface vlan.%s %s output rate %s%s\n" % (inputDict['vlan'],
                                                                     outputName, outrate, outtype))
            self.params['maxThrgRemaining'] -= outrate

    def calculateRSTFairshare(self, reqRate):
        """Calculate L3 RST Fairshare throughput. Equivalent Fractions finding."""
        if int(self.params['maxThrgRemaining']) >= int(self.params['totalRSTThrg']):
            self.logger.debug('ThrgRemaining >= than totalRST. Return requested rate')
            return reqRate
        self.logger.debug('RST Throughput is more than server capable. Returning fairshare.')
        newRate = float(reqRate) * float(self.params['maxThrgRemaining'])
        newRate = newRate // float(self.params['totalRSTThrg'])
        self.logger.debug('Requested: %s, TotalRST: %s, MaxRemaining: %s, NewRate: %s' % (reqRate, self.params['totalRSTThrg'], self.params['maxThrgRemaining'], newRate))
        return int(newRate)

    def findTotalRSTAllocation(self, overlapServices):
        """Find total RST Allocations."""
        totalRST = 0
        for _, servParams in overlapServices.items():
            if 'rules' not in servParams:
                continue
            tmpThrg, _ = self.convertToRate(servParams['rules'])
            totalRST += tmpThrg
        self.params['totalRSTThrg'] = totalRST

    def addRSTQoS(self, tmpFD):
        """BW Requests do not reach Agent. Loop over all RST definitions and
        if any our range is with-in network namespace, we add QoS as defined for RST
        """
        allIPs = getAllIPs()
        overlapServices = {}
        for _key, vals in self.activeDeltas.get('output', {}).get('rst', {}).items():
            for _, ipDict in vals.items():
                for iptype, routes in ipDict.items():
                    if 'hasService' not in routes:
                        continue
                    service = overlapServices.setdefault(routes['hasService']['bwuri'], {'ipv4': [],
                                                                                         'ipv6': [],
                                                                                         'rules': {}})
                    service['rules'] = routes['hasService']
                    for _, routeInfo in routes.get('hasRoute').items():
                        iprange = routeInfo.get('routeFrom', {}).get('%s-prefix-list' % iptype, {}).get('value', None)
                        findOverlaps(service, iprange, allIPs, iptype)
        self.findTotalRSTAllocation(overlapServices)
        for qosType in ['input', 'output']:
            params = copy.deepcopy(self.params)
            params['counter'] = 0
            params['type'] = qosType
            params['matchtype'] = 'dst' if qosType == 'input' else 'src'
            tmpFD.write("# SENSE Controlled Interface %(type)s %(intfName)s %(maxName)s\n" % params)
            tmpFD.write("interface46 %(intfName)s %(type)s-%(intfName)s %(type)s rate %(maxName)s\n" % params)
            for servName, servParams in overlapServices.items():
                if 'rules' not in servParams:
                    continue
                params['resvRate'], params['resvType'] = self.convertToRate(servParams['rules'])
                params['resvRate'] = self.calculateRSTFairshare(params['resvRate'])
                # Need to calculate the remaining traffic
                params['resvName'] = "%(resvRate)s%(resvType)s" % params
                tmpFD.write('  # priority%s belongs to %s service\n' % (params['counter'], servName))
                tmpFD.write('  class priority%(counter)s commit %(resvName)s max %(maxName)s\n' % params)
                for ipval in servParams.get('ipv4', []):
                    tmpFD.write('    match %s %s\n' % (params['matchtype'], ipval))
                for ipval in servParams.get('ipv6', []):
                    tmpFD.write('    match6 %s %s\n' % (params['matchtype'], ipval))
                tmpFD.write('\n')
            params['maxDefault'] = "%s%s" % (int(params['maxThrgIntf'] / (len(overlapServices)+1)), params['maxtype'])
            tmpFD.write('  # Default - all remaining traffic gets mapped to default class\n')
            tmpFD.write('  class default commit %(defThrgIntf)s%(defThrgType)s max %(maxDefault)s\n' % params)
            tmpFD.write('    match all\n\n')


    def startqos(self):
        """Main Start."""
        newFile = self.getAllQOSed()
        if not filecmp.cmp(newFile, '/etc/firehol/fireqos.conf'):
            self.logger.info("QoS rules are not equal. putting new config file")
            shutil.move(newFile, '/etc/firehol/fireqos.conf')
            self.restartQos()
        else:
            self.logger.info("QoS rules are equal. NTD")
            os.unlink(newFile)


def execute(config=None):
    """Execute main script for DTN-RM Agent output preparation."""
    qosruler = QOS(config)
    qosruler.startqos()

if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='QOS')
    execute()
