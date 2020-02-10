#!/usr/bin/env python
"""
    Ruler component pulls all actions from Site-FE and applies these rules on DTN

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
import os
import glob
import json
import tempfile
import filecmp
import shutil
from DTNRMLibs.MainUtilities import getDefaultConfigAgent, createDirs, contentDB
from DTNRMLibs.MainUtilities import execute as executeCmd
from DTNRMLibs.MainUtilities import getStreamLogger

COMPONENT = 'QOS'

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
def convertToRate(inputRate, inputVal, logger):
    logger.info('Converting rate for QoS. Input %s %s' % (inputRate, inputVal))
    outRate = -1
    outType = ''
    if inputRate == 'bps':
        outRate = int(inputVal / 1000000000)
        outType = 'gbit'
    if outRate == 0:
        outRate = int(inputVal / 1000000)
        outType = 'mbit'
    if outRate == 0:
        outRate = int(inputVal / 1000)
        outType = 'bit'
    if outRate != -1:
        logger.info('Converted rate for QoS from %s %s to %s' % (inputRate, inputVal, outRate))
        return outRate, outType
    raise Exception('Unknown input rate parameter %s and %s' % (inputRate, inputVal))

class QOS(object):
    """ QOS class to install new limit rules """
    def __init__(self, config, logger):
        self.config, self.logger = getDefaultConfigAgent(COMPONENT, config, logger)
        self.workDir = self.config.get('general', 'private_dir') + "/DTNRM/QOS/"
        self.configDir = self.config.get('general', 'private_dir') + "/DTNRM/RulerAgent/"
        self.hostname = self.config.get('agent', 'hostname')
        createDirs(self.workDir)
        self.debug = self.config.getboolean('general', "debug")
        self.agentdb = contentDB(logger=self.logger, config=self.config)

    def restartQos(self):
        """ Restart QOS service """
        self.logger.info("Restarting fireqos rules")
        executeCmd("fireqos clear_all_qos", self.logger)
        executeCmd("fireqos start", self.logger)

    def getMaxThrg(self):
        """ Get Maximum set throughput and add QoS on it """
        if self.config.has_option('agent', 'public_intf') and self.config.has_option('agent', 'public_intf_max'):
            self.logger.info("Getting max interface throughput")
            intf = self.config.get('agent', 'public_intf')
            maxThrg = self.config.get('agent', 'public_intf_max')
            self.logger.info("Maximum throughput for %s is %s" % (intf, maxThrg))
            return intf, int(maxThrg)
        return None, None

    def getAllQOSed(self):
        """ Read all configs and prepare qos doc """
        self.logger.info("Getting All QoS rules.")
        tmpFile = tempfile.NamedTemporaryFile(delete=False)
        # {"ip": "10.0.0.54/24", "reservableCapacity": "1000000000", "vlan": "3610",
        #  "txqueuelen": 1000, "MTU": 1500, "priority": "0",
        # "http://schemas.ogf.org/mrs/2013/12/topology#BandwidthService": {}, "availableCapacity": "1000000000",
        # "granularity": "1000000", "maximumCapacity": "1000000000", "type": "guaranteedCapped",
        # "destport": "ens1", "unit": "mbps"}
        totalAllocated = 0
        for fileName in glob.glob("%s/*.json" % self.configDir):
            self.logger.info("Analyzing %s file" % fileName)
            inputDict = {}
            with open(fileName, 'r') as fd:
                inputDict = json.load(fd)
                if 'uid' not in inputDict.keys():
                    self.logger.info('Seems this dictionary is custom delta. Ignoring it.')
                    continue
                inputDict = inputDict[u'hosts'][self.hostname]
                # ['hosts'][self.hostname]
                self.logger.info("File %s content %s" % (fileName, inputDict))
                if 'routes' in inputDict.keys():
                    self.logger.info('This is L3 definition. Ignore QOS. Todo for future based on source/dest')
                    continue
                inputName = "%s%sIn" % (inputDict['destport'], inputDict['vlan'])
                outputName = "%s%sOut" % (inputDict['destport'], inputDict['vlan'])
                params = inputDict['params'][0]
                if not params:
                    self.logger.info('This specific vlan request did not provided any QOS. Ignoring QOS Rules for it')
                    continue
                outrate, outtype = convertToRate(params['unit'], int(params['reservableCapacity']), self.logger)
                tmpFile.write("# SPEEDLIMIT %s %s %s %s\n" % (inputDict['vlan'],
                                                              inputDict['destport'],
                                                              outrate, outtype))
                tmpFile.write("interface %s.%s %s input rate %s%s\n" % (inputDict['destport'], inputDict['vlan'],
                                                                        inputName, outrate, outtype))
                tmpFile.write("interface %s.%s %s output rate %s%s\n" % (inputDict['destport'], inputDict['vlan'],
                                                                         outputName, outrate, outtype))
                totalAllocated += int(params['reservableCapacity'])
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

    def start(self):
        """ Main Start """
        newFile = self.getAllQOSed()
        if not filecmp.cmp(newFile, '/etc/firehol/fireqos.conf'):
            self.logger.info("QoS rules are not equal. putting new config file")
            shutil.move(newFile, '/etc/firehol/fireqos.conf')
            self.restartQos()
        else:
            self.logger.info("QoS rules are equal. NTD")
            os.unlink(newFile)

def execute(config=None, logger=None):
    """ Execute main script for DTN-RM Agent output preparation """
    qosruler = QOS(config, logger)
    qosruler.start()

if __name__ == '__main__':
    execute(logger=getStreamLogger())
