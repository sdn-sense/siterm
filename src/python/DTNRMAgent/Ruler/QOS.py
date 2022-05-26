#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
from __future__ import division
import os
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
        self.totalAllocated = 0

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
            outRate = int(inputVal // 1000000000)
            outType = 'gbit'
        if outRate == 0:
            outRate = int(inputVal // 1000000)
            outType = 'mbit'
        if outRate == 0:
            outRate = int(inputVal // 1000)
            outType = 'bit'
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
        if self.config.has_option('agent', 'public_intf') and self.config.has_option('agent', 'public_intf_max'):
            self.logger.info("Getting max interface throughput")
            intf = self.config.get('agent', 'public_intf')
            maxThrg = self.config.get('agent', 'public_intf_max')
            self.logger.info("Maximum throughput for %s is %s" % (intf, maxThrg))
            return intf, int(maxThrg)
        return None, None

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
        self.totalAllocated = 0
        fName = ""
        with tempfile.NamedTemporaryFile(delete=False, mode="w+") as tmpFile:
            fName = tmpFile.name
            self.addVlanQoS(tmpFile)
            self.addRSTQoS(tmpFile)
        return fName

    def getParams(self):
        """Get all params from Host Config"""
        params = {}
        params['intfName'], params['maxThrgIntf'] = self.getMaxThrg()
        if params['intfName'] and params['maxThrgIntf']:
            params['maxThrgIntf'] = params['maxThrgIntf'] - self.totalAllocated
            if params['maxThrgIntf'] <= 0:
                params['maxThrgIntf'] = 100  # We set by default 100MB/s for any ssh access if needed.
            # as size is reported in bits, we need to get final size in gbit.
            params['maxThrgIntf'] = int(params['maxThrgIntf'] / 1000000000.0)
            params['maxtype'] = 'gbit'
            if params['maxThrgIntf'] <= 0:
                params['maxThrgIntf'] = 100
                params['maxtype'] = 'mbit'
        params['maxName'] =  "%(maxThrgIntf)s%(maxtype)s" % params
        return params

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
            tmpFD.write("# SENSE CREATED VLAN %s %s %s %s\n" % (inputDict['vlan'],
                                                                inputDict['destport'],
                                                                outrate, outtype))
            tmpFD.write("interface vlan.%s %s input rate %s%s\n" % (inputDict['vlan'],
                                                                    inputName, outrate, outtype))
            tmpFD.write("interface vlan.%s %s output rate %s%s\n" % (inputDict['vlan'],
                                                                     outputName, outrate, outtype))
            self.totalAllocated += int(inputDict['params']['reservableCapacity'])

    def addRSTQoS(self, tmpFD):
        """BW Requests do not reach Agent. Loop over all RST definitions and
        if any our range is with-in network namespace, we add QoS as defined for RST
        """
        params = self.getParams()
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
        for qosType in ['input', 'output']:
            params['counter'] = 0
            params['type'] = qosType
            params['matchtype'] = 'dst' if qosType == 'input' else 'src'
            params['remainingRate'] = params['maxThrgIntf']
            params['remainingType'] = params['maxtype']
            tmpFD.write("# SENSE Controlled Interface %(type)s %(intfName)s %(maxName)s\n" % params)
            tmpFD.write("interface46 %(intfName)s %(type)s-%(intfName)s %(type)s rate %(maxName)s balanced\n" % params)
            for servName, servParams in overlapServices.items():
                if 'rules' not in servParams:
                    continue
                params['resvRate'], params['resvType'] = self.convertToRate(servParams['rules'])
                params['remainingRate'] =  params['remainingRate'] - params['resvRate']
                # Need to calculate the remaining traffic
                params['resvName'] = "%(resvRate)s%(resvType)s" % params
                tmpFD.write('  # priority%s belongs to %s service\n' % (params['counter'], servName))
                tmpFD.write('  class priority%(counter)s commit %(resvName)s max %(maxName)s\n' % params)
                for ipval in servParams.get('ipv4', []):
                    tmpFD.write('    match %s %s\n' % (params['matchtype'], ipval))
                for ipval in servParams.get('ipv6', []):
                    tmpFD.write('    match6 %s %s\n' % (params['matchtype'], ipval))
                tmpFD.write('\n')
            tmpFD.write('  # Default - all remaining traffic gets mapped to default class\n')
            tmpFD.write('  class default commit %(remainingRate)s%(remainingType)s max %(maxName)s\n' % params)
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
