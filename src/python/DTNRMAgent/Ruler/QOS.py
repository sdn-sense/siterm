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
from DTNRMLibs.MainUtilities import createDirs, contentDB
from DTNRMLibs.MainUtilities import execute as executeCmd
from DTNRMLibs.MainUtilities import getLoggingObject
from DTNRMLibs.MainUtilities import getConfig
from DTNRMLibs.MainUtilities import getFileContentAsJson
from DTNRMLibs.MainUtilities import getUTCnow

COMPONENT = 'QOS'

class QOS():
    """QOS class to install new limit rules."""
    def __init__(self, config):
        self.config = config if config else getConfig()
        self.logger = getLoggingObject()
        self.workDir = self.config.get('general', 'private_dir') + "/DTNRM/RulerAgent/"
        self.hostname = self.config.get('agent', 'hostname')
        createDirs(self.workDir)
        self.debug = self.config.getboolean('general', "debug")
        self.agentdb = contentDB(config=self.config)

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
    def convertToRate(self, inputRate, inputVal):
        """Convert input to rate understandable to fireqos."""
        self.logger.info('Converting rate for QoS. Input %s %s' % (inputRate, inputVal))
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
        """Restart QOS service ."""
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
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return True
        if 'start' in timings and getUTCnow() < timings['start']:
            return False
        return True

    def getConf(self, activeDeltas=None):
        """ Get conf from local file """
        if activeDeltas:
            return activeDeltas
        activeDeltasFile = "%s/activedeltas.json" % self.workDir
        if os.path.isfile(activeDeltasFile):
            activeDeltas = getFileContentAsJson(activeDeltasFile)
        return activeDeltas

    @staticmethod
    def _getvlanlistqos(inParams):
        """ Get vlan qos dict """
        vlans = []
        for key, vals in inParams.items():
            vlan = {}
            vlan['destport'] = key
            vlan['vlan'] = vals.get('hasLabel', {}).get('value', '')
            vlan['params'] = vals.get('hasService', {})
            vlans.append(vlan)
        return vlans

    def getAllQOSed(self, newConf=None):
        """Read all configs and prepare qos doc."""
        self.logger.info("Getting All QoS rules.")
        activeDeltas = self.getConf(newConf)
        totalAllocated = 0
        inputDicts = []
        for _key, vals in activeDeltas.get('output', {}).get('vsw', {}).items():
            if self.hostname in vals:
                if not self._started(vals):
                    # This resource has not started yet. Continue.
                    continue
                inputDicts += self._getvlanlistqos(vals[self.hostname])

        tmpFile = tempfile.NamedTemporaryFile(delete=False, mode="w+")
        for inputDict in inputDicts:
            inputName = "%s%sIn" % (inputDict['destport'], inputDict['vlan'])
            outputName = "%s%sOut" % (inputDict['destport'], inputDict['vlan'])
            if not inputDict['params']:
                self.logger.info('This specific vlan request did not provided any QOS. Ignoring QOS Rules for it')
                continue
            outrate, outtype = self.convertToRate(inputDict['params']['unit'], int(inputDict['params']['reservableCapacity']))
            tmpFile.write("# SPEEDLIMIT %s %s %s %s\n" % (inputDict['vlan'],
                                                          inputDict['destport'],
                                                          outrate, outtype))
            tmpFile.write("interface vlan.%s %s input rate %s%s\n" % (inputDict['vlan'],
                                                                      inputName, outrate, outtype))
            tmpFile.write("interface vlan.%s %s output rate %s%s\n" % (inputDict['vlan'],
                                                                       outputName, outrate, outtype))
            totalAllocated += int(inputDict['params']['reservableCapacity'])
        intfName, maxThrgIntf = self.getMaxThrg()
        if intfName and maxThrgIntf:
            maxThrgIntf = maxThrgIntf - totalAllocated
            if maxThrgIntf <= 0:
                maxThrgIntf = 100  # We set by default 100MB/s for any ssh access if needed.
            # as size is reported in bits, we need to get final size in gbit.
            maxThrgIntf = int(maxThrgIntf / 1000000000.0)
            maxtype = 'gbit'
            if maxThrgIntf <= 0:
                maxThrgIntf = 100
                maxtype = 'mbit'
            self.logger.info("Appending at the end default interface QoS. Settings %s %s %s" % (intfName, maxThrgIntf, maxtype))
            tmpFile.write("# SPEEDLIMIT MAIN  input %s %s %s\n" % (maxThrgIntf, intfName, maxtype))
            tmpFile.write("interface %s mainInput input rate %s%s\n" % (intfName, maxThrgIntf, maxtype))
            tmpFile.write("interface %s mainOutput output rate %s%s\n" % (intfName, maxThrgIntf, maxtype))
        tmpFile.close()
        return tmpFile.name

    def startqos(self, newConf=None):
        """Main Start."""
        newFile = self.getAllQOSed(newConf)
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
    getLoggingObject(logType='StreamLogger')
    execute()
