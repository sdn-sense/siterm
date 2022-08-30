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
from DTNRMLibs.MainUtilities import createDirs, contentDB
from DTNRMLibs.MainUtilities import execute as executeCmd
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getFileContentAsJson
from DTNRMLibs.MainUtilities import getUTCnow
from DTNRMLibs.CustomExceptions import ConfigException
from DTNRMLibs.CustomExceptions import OverSubscribeException
from DTNRMAgent.Ruler.OverlapLib import getAllOverlaps

COMPONENT = 'QOS'


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
        """Convert input to rate understandable to fireqos."""
        self.logger.info(f'Converting rate for QoS. Input {params}')
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
            self.logger.info(f'Converted rate for QoS from {inputRate} {inputVal} to {outRate}')
            return outRate, outType
        raise Exception(f'Unknown input rate parameter {inputRate} and {inputVal}')

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
                    raise ConfigException(f"ConfigError: Remaining throughtput is <= 0: {self.params['maxThrgIntf']}")
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
        activeDeltasFile = f"{self.workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)

    @staticmethod
    def _getvlanlistqos(inParams):
        """Get vlan qos dict"""
        vlans = []
        for key, vals in inParams.items():
            vlans.append({'destport': key,
                          'vlan': vals.get('hasLabel', {}).get('value', ''),
                          'params': vals.get('hasService', {})})
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
            self.params['maxName'] = f"{self.params['maxThrgIntf']}{self.params['maxtype']}"
            self.params['l3enabled'] = True
        except ConfigException as ex:
            print(f'L3 DTN Config public intf not defined. Will not add QoS for L3. Exception {ex}')
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
            inputName = f"{inputDict['destport']}{inputDict['vlan']}In"
            outputName = f"{inputDict['destport']}{inputDict['vlan']}Out"
            if not inputDict['params']:
                self.logger.info('This specific vlan request did not provided any QOS. Ignoring QOS Rules for it')
                continue
            outrate, outtype = self.convertToRate(inputDict['params'])
            if 'maxThrgRemaining' in self.params:
                if self.params['maxThrgRemaining'] - outrate <= 0:
                    raise OverSubscribeException("Node is oversubscribed. Will not modify present QoS.")
                self.params['maxThrgRemaining'] -= outrate
            tmpFD.write("# SENSE CREATED VLAN %s %s %s %s\n" % (inputDict['vlan'],
                                                                inputDict['destport'],
                                                                outrate, outtype))
            tmpFD.write("interface vlan.%s %s input rate %s%s\n" % (inputDict['vlan'],
                                                                    inputName, outrate, outtype))
            tmpFD.write("interface vlan.%s %s output rate %s%s\n" % (inputDict['vlan'],
                                                                     outputName, outrate, outtype))

    def calculateRSTFairshare(self, reqRate):
        """Calculate L3 RST Fairshare throughput. Equivalent Fractions finding."""
        if int(self.params['maxThrgRemaining']) >= int(self.params['totalRSTThrg']):
            self.logger.debug('ThrgRemaining >= than totalRST. Return requested rate')
            return reqRate
        self.logger.debug('RST Throughput is more than server capable. Returning fairshare.')
        newRate = float(reqRate) * float(self.params['maxThrgRemaining'])
        newRate = newRate // float(self.params['totalRSTThrg'])
        self.logger.debug(f"Requested: {reqRate}, TotalRST: {self.params['totalRSTThrg']}, MaxRemaining: {self.params['maxThrgRemaining']}, NewRate: {newRate}")
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
        overlapServices = getAllOverlaps(self.activeDeltas)
        self.findTotalRSTAllocation(overlapServices)
        for qosType in ['input', 'output']:
            params = copy.deepcopy(self.params)
            params['counter'] = 0
            params['type'] = qosType
            params['matchtype'] = 'dst' if qosType == 'input' else 'src'
            tmpFD.write(f"# SENSE Controlled Interface {params['type']} {params['intfName']} {params['maxName']}\n")
            tmpFD.write(f"interface46 {params['intfName']} {params['type']}-{params['intfName']} {params['type']} rate {params['maxName']}\n")
            for servName, servParams in overlapServices.items():
                if 'rules' not in servParams:
                    continue
                params['resvRate'], params['resvType'] = self.convertToRate(servParams['rules'])
                params['resvRate'] = self.calculateRSTFairshare(params['resvRate'])
                # Need to calculate the remaining traffic
                params['resvName'] = f"{params['resvRate']}{params['resvType']}"
                tmpFD.write(f"  # priority{params['counter']} belongs to {servName} service\n")
                tmpFD.write(f"  class priority{params['counter']} commit {params['resvName']} max {params['maxName']}\n")
                for ipval in servParams.get('src_ipv4', []):
                    tmpFD.write(f"    match {params['matchtype']} {ipval}\n")
                for ipval in servParams.get('src_ipv6', []):
                    tmpFD.write(f"    match6 {params['matchtype']} {ipval}\n")
                tmpFD.write('\n')
            params['maxDefault'] = f"{int(params['maxThrgIntf'] / (len(overlapServices) + 1))}{params['maxtype']}"
            tmpFD.write('  # Default - all remaining traffic gets mapped to default class\n')
            tmpFD.write(f"  class default commit {params['defThrgIntf']}{params['defThrgType']} max {params['maxDefault']}\n")
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
