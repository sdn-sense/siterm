#!/usr/bin/env python3
"""Ruler component pulls all actions from Site-FE and applies these rules on
DTN.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/01/20
"""
import os
from SiteRMAgent.Ruler.Components.QOS import QOS
from SiteRMAgent.Ruler.Components.VInterfaces import VInterfaces
from SiteRMAgent.Ruler.Components.Routing import Routing
from SiteRMAgent.Ruler.OverlapLib import OverlapLib
from SiteRMLibs.MainUtilities import getDataFromSiteFE, evaldict
from SiteRMLibs.MainUtilities import createDirs, getFullUrl, contentDB, getFileContentAsJson
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.MainUtilities import getUTCnow
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.CustomExceptions import FailedGetDataFromFE
from SiteRMLibs.ipaddr import checkOverlap

COMPONENT = 'Ruler'


class Ruler(contentDB, QOS, OverlapLib):
    """Ruler class to create interfaces on the system."""
    def __init__(self, config, sitename):
        self.config = config if config else getGitConfig()
        self.logger = getLoggingObject(config=self.config, service='Ruler')
        self.workDir = self.config.get('general', 'privatedir') + "/SiteRM/RulerAgent/"
        createDirs(self.workDir)
        self.fullURL = getFullUrl(self.config, sitename)
        self.hostname = self.config.get('agent', 'hostname')
        self.logger.info("====== Ruler Start Work. Hostname: %s", self.hostname)
        # L2,L3 move it to Class Imports at top.
        self.layer2 = VInterfaces(self.config, sitename)
        self.layer3 = Routing(self.config, sitename)
        self.activeIPs = {'ipv4': [], 'ipv6': []}
        self.activeDeltas = {}
        self.activeFromFE = {}
        self.activeNew = {}
        self.activeNow = {}
        QOS.__init__(self)
        OverlapLib.__init__(self)

    def __clean(self):
        """Clean variables before run"""
        self.activeIPs = {'ipv4': {}, 'ipv6': {}}

    def getData(self, url):
        """Get data from FE."""
        out = getDataFromSiteFE({}, self.fullURL, url)
        if out[2] != 'OK':
            msg = f'Received a failure getting information from Site Frontend {str(out)}'
            self.logger.critical(msg)
            raise FailedGetDataFromFE(msg)
        return evaldict(out[0])

    def getActiveDeltas(self):
        """Get Delta information."""
        return self.getData("/sitefe/v1/activedeltas/")

    @staticmethod
    def _started(inConf):
        """Check if service started"""
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return True
        if 'start' in timings and getUTCnow() < timings['start']:
            return False
        return True

    @staticmethod
    def _ended(inConf):
        """Check if service ended"""
        timings = inConf.get('_params', {}).get('existsDuring', {})
        if not timings:
            return False
        if 'end' in timings and getUTCnow() > timings['end']:
            return True
        return False

    def logIPs(self, tmpvlans):
        """Log all Active IPs"""
        for vlan in tmpvlans:
            if 'ip' in vlan and vlan['ip']:
                tmpd = self.activeIPs['ipv4'].setdefault(f"vlan.{vlan['vlan']}", [])
                tmpd.append(vlan['ip'])
            if 'ipv6' in vlan and vlan['ipv6']:
                tmpd = self.activeIPs['ipv6'].setdefault(f"vlan.{vlan['vlan']}", [])
                tmpd.append(vlan['ipv6'])

    def checkIfOverlap(self, ip, intf, iptype):
        """Check if IPs overlap with what is set in configuration"""
        print(ip, intf, iptype)
        vlan = intf.split('.')
        if len(vlan) == 2:
            vlan = int(vlan[1])
        overlap = False
        for mintf in self.config['MAIN']['agent']['interfaces']:
            if vlan in self.config['MAIN'][mintf].get('all_vlan_range_list', []):
                if f'{iptype}-address-pool' in self.config['MAIN'][mintf]:
                    overlap = checkOverlap(self.config['MAIN'][mintf][f'{iptype}-address-pool'],
                                           ip,
                                           iptype)
                    if overlap:
                        break
        return overlap

    def ipConsistency(self, iptype):
        """Do IP Consistency. In case of Modify call, vlan remains, just IP changes."""
        self.getAllIPs()
        # Consistency for IPv4
        for key, values in self.allIPs[iptype].items():
            if iptype == 'ipv4':
                tmpip = key.split('/')
                tmpip[1] = str(self._getNetmaskBit(tmpip[1]))
                ip = "/".join(tmpip)
            else:
                ip = key
            for intf in values:
                if intf['master'] in self.activeIPs[iptype]:
                    # Check if IP is in the list of active:
                    if ip not in self.activeIPs[iptype][intf['master']]:
                        overlap = self.checkIfOverlap(ip, intf['master'], iptype)
                        if overlap:
                            self.logger.info(f"Removing {ip} from {intf['master']}. Not in active delta.")
                            self.layer2._removeIP({'ip': ip,
                                                   'vlan': intf['master'].split('.')[1]})
                        else:
                            self.logger.info(f"Not removing {ip} from {intf['master']} as it is not from configuration. Manual set IP?")

    def activeComparison(self, actKey, actCall):
        """Compare active vs file on node config"""
        self.logger.info(f'Active Comparison for {actKey}')
        if actKey == 'vsw':
            for key, vals in self.activeDeltas.get('output', {}).get(actKey, {}).items():
                if self.hostname in vals:
                    if not self._started(vals):
                        # This resource has not started yet. Continue.
                        continue
                    if key in self.activeFromFE.get('output', {}).get(actKey, {}).keys() and \
                    self.hostname in self.activeFromFE['output'][actKey][key].keys():
                        if vals[self.hostname] == self.activeFromFE['output'][actKey][key][self.hostname]:
                            continue
                        tmpret = actCall.modify(vals[self.hostname], self.activeFromFE['output'][actKey][key][self.hostname], key)
                        self.logIPs(tmpret)
                    else:
                        actCall.terminate(vals[self.hostname], key)
        if actKey == 'rst' and self.qosPolicy == 'hostlevel':
            for key, val in self.activeNow.items():
                if key not in self.activeNew:
                    actCall.terminate(val, key)
                    continue
                if val != self.activeNew[key]:
                    actCall.terminate(val, key)
            return

    def activeEnsure(self, actKey, actCall):
        """Ensure all active resources are enabled, configured"""
        self.logger.info(f'Active Ensure for {actKey}')
        if actKey == 'vsw':
            for key, vals in self.activeFromFE.get('output', {}).get(actKey, {}).items():
                if self.hostname in vals:
                    if self._started(vals) and not self._ended(vals):
                        # Means resource is active at given time.
                        tmpret = actCall.activate(vals[self.hostname], key)
                        self.logIPs(tmpret)
                    else:
                        # Termination. Here is a bit of an issue
                        # if FE is down or broken - and we have multiple deltas
                        # for same vlan, but different times.
                        # So we are not doing anything to terminate it and termination
                        # will happen at activeComparison - once delta is removed in FE.
                        continue
        if actKey == 'rst' and self.qosPolicy == 'hostlevel':
            for key, val in self.activeNew.items():
                actCall.activate(val, key)
            return

    def startwork(self):
        """Start execution and get new requests from FE."""
        self.__clean()
        # if activeDeltas did not change - do not do any comparison
        # Comparison is needed to identify if any param has changed.
        # Otherwise - do precheck if all resources are active
        # And start QOS Ruler if it is configured so.
        activeDeltasFile = f"{self.workDir}/activedeltas.json"
        if os.path.isfile(activeDeltasFile):
            self.activeDeltas = getFileContentAsJson(activeDeltasFile)
        self.activeNow = self.getAllOverlaps(self.activeDeltas)

        self.activeFromFE = self.getActiveDeltas()
        self.activeNew = self.getAllOverlaps(self.activeFromFE)
        if self.activeDeltas != self.activeFromFE:
            self.dumpFileContentAsJson(activeDeltasFile, self.activeFromFE)

        if not self.config.getboolean('agent', 'norules'):
            self.logger.info('Agent is configured to apply rules')
            for actKey, actCall in {'vsw': self.layer2, 'rst': self.layer3}.items():
                if self.activeDeltas != self.activeFromFE:
                    self.activeComparison(actKey, actCall)
                self.activeEnsure(actKey, actCall)
            # QoS Can be modified and depends only on Active
            self.activeNow = self.activeNew
            self.startqos()
        else:
            self.logger.info('Agent is not configured to apply rules')
        self.logger.info('Ended function start')
        self.logger.info('Started IP Consistency Check')
        self.ipConsistency('ipv4')


def execute(config=None):
    """Execute main script for SiteRM Agent output preparation."""
    if not config:
        config = getGitConfig()
    for sitename in config.get('general', 'sitename'):
        ruler = Ruler(config, sitename)
        ruler.startwork()


if __name__ == '__main__':
    getLoggingObject(logType='StreamLogger', service='Ruler')
    execute()
