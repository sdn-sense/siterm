#!/usr/bin/env python3
"""
Throughput fairshare calculation:
In SENSE, there can be multiple QoS Requests:
End-to-End Path directly to a single DTN with QOS
L3 Path between Routers - where QoS is requested for an IP Range
(There might be 1 to many servers behind same IP Range)

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
It exceeds the requirement, Frontend will not accept the request.

Scenario 4:
Site uplink is 100gbps, 10 DTN - each 10gbps.
Once End-To-End QoS added - all remaining traffic can be fairshared for L3 QoS (L3 Path between Routers).
In this case:
If only 1 new L3 Path requested for 50gbps - Site Uplink is capable. Formula in this case on DTN is:
    TotalDTNSpeed = 10*10 = 100
    Requested = 50gbps
    NewRate = 5gbps/server (5gbps/yeach)
In this case - All Agents (which have that specific IPv6 address) -
will put 5gbps priority for matching ipv6 addresses.

Scenario 5:
Site uplink is 100gbps, 10 DTN - each 10gbps.
Once End-To-End QoS added - all remaining traffic can be fairshared for L3 QoS (L3 Path between Routers).
In this case:
Lets say we have 3 L3 Path requested for diff ranges (1st - 10gbps, 2nd - 20gbps, 3rd - 50gbps).
Site uplink is capable to support that, but DTNs each are limited to 10gbps. Formula in this case on DTN is:
    TotalDTNSpeed = 10*10 = 100
    NewRate1st = 1gbps
    NewRate2nd = 2gbps
    NewRate3rd = 5gbps

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/01/20
"""
import filecmp
import os
import shutil
import tempfile

from SiteRMLibs.CustomExceptions import ConfigException, OverSubscribeException
from SiteRMLibs.MainUtilities import execute as executeCmd
from SiteRMLibs.ipaddr import getInterfaceSpeed

COMPONENT = "QOS"


class QOS:
    """QOS class to install new limit rules."""

    # pylint: disable=E1101
    def __init__(self):
        self.activeDeltas = {}
        self.activeL2 = []
        self.params = {}
        self.qosPolicy = self.config.get("qos", "policy")
        self.qosparams = self.config.get("qos", "qos_params")
        self.classmax = self.config.get("qos", "class_max")
        self.qosTotals = []

    def restartQos(self):
        """Restart QOS service"""
        self.logger.info("Restarting fireqos rules")
        executeCmd("fireqos clear_all_qos", self.logger)
        executeCmd("fireqos start", self.logger)

    def getQoSTotals(self):
        """Get Delta information."""
        self.qosTotals = self.getData("/sitefe/json/frontend/getqosdata/")

    def _getvlanlistqos(self):
        """Get vlan qos dict"""
        self.activeL2 = []
        for actkey in ["vsw", "kube", "singleport"]:
            for _key, vals in self.activeDeltas.get("output", {}).get(actkey, {}).items():
                if self.hostname not in vals:
                    continue
                if not self._started(vals):
                    # This resource has not started yet. Continue.
                    continue
                for key, vals1 in vals[self.hostname].items():
                    if not vals1.get("hasLabel", {}).get("value", ""):
                        self.logger.warning("This specific vlan request did not provided vlan id.Ignoring QOS Rules for it")
                        self.logger.warning(f"Resource: {vals1}")
                        continue
                    self.activeL2.append(
                        {
                            "destport": key,
                            "vlan": vals1.get("hasLabel", {}).get("value", ""),
                            "params": vals1.get("hasService", {}),
                        }
                    )

    def getParams(self):
        """Get all params from Host Config"""
        self.logger.info("Getting All Params from config file.")
        self.params = {}
        for interface in self.config.get("agent", "interfaces"):
            params = self.params.setdefault(interface, {})
            params["intf_max"] = int(self.config.get(interface, "bwParams").get("maximumCapacity", getInterfaceSpeed(interface)))
            params["intf_reserve"] = int(self.config.get(interface, "bwParams").get("reservedCapacity", 1000))
            # Take out reserved from intf_max
            self.params[interface]["intf_max"] -= self.params[interface]["intf_reserve"]

    def calculateTotalPerInterface(self):
        """Calculate total allocated per interface"""
        for intf, intfDict in self.activeNow.items():
            for _, bwDict in intfDict.items():
                self.params.setdefault(bwDict["master_intf"], {})
                self.params[bwDict["master_intf"]].setdefault("total_allocated", 0)
                self.params[bwDict["master_intf"]].setdefault("total_requests", 0)
                rate = self.convertToRate(bwDict["rules"])
                self.params[bwDict["master_intf"]]["total_allocated"] += rate[0]
                self.params[bwDict["master_intf"]]["total_requests"] += 1
                self.params[bwDict["master_intf"]].setdefault(intf, 0)
                self.params[bwDict["master_intf"]][intf] += rate[0]

    def getTotalAvailableForIP(self, ipaddr):
        """Get total Available for specific IP Rangein range"""
        if ipaddr:
            for iprange, thrg in self.qosTotals[0].items():
                if self.networkOverlap(iprange, ipaddr):
                    return thrg
        return None

    @staticmethod
    def reqRatio(nicAvail, totalReq, reqVal):
        """Calculate request Ratio"""
        return (nicAvail * totalReq) / reqVal

    def calculateRSTFairshare(self, reqRules):
        """Calculate L3 RST Fairshare throughput. Equivalent Fractions finding."""
        self.getQoSTotals()
        reqRate, _ = self.convertToRate(reqRules["rules"])
        totalRate = None
        for key in ["src_ipv4", "src_ipv6"]:
            totalRate = self.getTotalAvailableForIP(reqRules[key])
            if totalRate:
                break
        if not totalRate:
            return None
        reserved = int(self.params[reqRules["master_intf"]]["intf_reserve"])
        totalAll = self.params[reqRules["master_intf"]]["total_allocated"]
        intfMax = self.params[reqRules["master_intf"]]["intf_max"]
        # Formula 1: Find ratio between all servers total capacity
        # (individualRate/totalRates) = ratio
        ratio = round(float(intfMax) / float(totalRate), 4)
        # Formula 2: Find individual node fairshare
        # ratio * reqRate = nodeThrgShare
        nodeThrgShare = int(ratio * reqRate)
        # Condition 1: If not enough capacity on all Nodes,
        # do a fractional calculation for fairshare
        if nodeThrgShare >= intfMax or nodeThrgShare > totalAll:
            fractReq = self.reqRatio(intfMax, reqRate, totalAll)
            reqRate = fractReq
        # Min for QoS we use 1Gb/s.
        reqRate = max(int(nodeThrgShare), 1000)
        return {"reqRate": reqRate, "reserved": reserved}

    @staticmethod
    def addMatchEntry(tmpFD, match, mtype, val):
        """Add match entry for ip"""
        tmpFD.write(f"    {match} {mtype} {val}\n")

    def _calcTotalMax(self, item, masterIntf, slaveIntf):
        """Calculate total Max based on flags in config"""
        if self.classmax:
            total = int(
                (
                    self.params[masterIntf]["intf_max"]
                    * self.params[masterIntf][slaveIntf]
                )
            )
            total = (
                int(total / self.params[masterIntf]["total_allocated"])
                + item["reserved"]
            )
            totalAll = item["reqRate"] + item["reserved"]
            return max(total, totalAll)
        return item["reqRate"] + item["reserved"]

    def _overcommitCheck(self, intf, reqRate, totalRate):
        """Allow QoS Overcommit. Default, yes (return totalRate)
        If allowOvercommit flag defined, then:
          true - means yes (return totalRate)
          false - means no (return reqRate)
        """
        if self.config.has_option(intf, "allowOvercommit"):
            if self.config.getboolean(intf, "allowOvercommit"):
                return totalRate
            return reqRate
        return totalRate

    def prepareQoSFileL3(self, tmpFD, allQoS):
        """Add L3 QoS TC Rules"""
        added = {}
        for qosType, mtype in {"input": "src", "output": "dst"}.items():
            for intf, items in allQoS.items():
                for item in items["items"]:
                    if intf not in added or added[intf][qosType] == 0:
                        added.setdefault(intf, {"input": 0, "output": 0})
                        tmpFD.write("\n# SENSE L3 Routing Private NS Request\n")
                        tmpFD.write(
                            f"interface46 {intf} {intf}-{qosType} {qosType} rate {items['total']}mbit {self.qosparams}\n"
                        )
                    tmpFD.write(
                        f"  # priority{added[intf][qosType]} belongs to {item['uri']} service\n"
                    )
                    totalRate = self._overcommitCheck(
                        items["master_intf"], item["reqRate"], items["total"]
                    )
                    tmpFD.write(
                        f"  class priority{added[intf][qosType]} commit {item['reqRate']}mbit max {totalRate}mbit\n"
                    )
                    added[intf][qosType] += 1
                    for key, match in {
                        "dst_ipv4": "match",
                        "dst_ipv6": "match6",
                    }.items():
                        tmpVals = item["bwDict"].get(key, [])
                        if tmpVals and isinstance(tmpVals, str):
                            self.addMatchEntry(tmpFD, match, mtype, tmpVals)
                        elif tmpVals and isinstance(tmpVals, list):
                            for ipval in tmpVals:
                                self.addMatchEntry(tmpFD, match, mtype, ipval)
                tmpFD.write(
                    "  # Default - all remaining traffic gets mapped to default class\n"
                )
                tmpFD.write(
                    f"  class default commit {items['reserved']}mbit max {items['total']}mbit\n"
                )
                tmpFD.write("    match all\n")

    def _calculateQoS(self, tmpFD, useMasterIntf=False):
        """Calculate and Prepare QoS File"""
        self.calculateTotalPerInterface()
        allQoS = {}
        for intf, intfDict in self.activeNow.items():
            newThrg = {}
            for uri, bwDict in intfDict.items():
                newThrg = self.calculateRSTFairshare(bwDict)
                if not newThrg:
                    continue
                newThrg["uri"] = uri
                newThrg["bwDict"] = bwDict
                intfKey = bwDict["master_intf"] if useMasterIntf else intf
                allQoS.setdefault(intf, {"items": [], "total": 0, "reserved": 0})
                allQoS[intfKey]["total"] += newThrg["reqRate"]
                allQoS[intfKey]["reserved"] = newThrg["reserved"]
                allQoS[intfKey]["master_intf"] = bwDict["master_intf"]
                allQoS[intfKey]["items"].append(newThrg)
        for intf, items in allQoS.items():
            for item in items["items"]:
                total = self._calcTotalMax(item, items["master_intf"], intf)
                allQoS[intf]["total"] = total
        if allQoS:
            self.prepareQoSFileL3(tmpFD, allQoS)

    def addRSTQoS(self, tmpFD):
        """BW Requests do not reach Agent. Loop over all RST definitions and
        if any our range is with-in network namespace, we add QoS as defined for RST
        """
        if self.qosPolicy == "privatens":
            self._calculateQoS(tmpFD)
        elif self.qosPolicy == "hostlevel":
            self._calculateQoS(tmpFD)
        elif self.qosPolicy == "default-not-set":
            self.logger.info(
                "QoS Policy not set in configuration. set one of privatens or hostlevel."
            )
        else:
            raise ConfigException(f"QoS Policy {self.qosPolicy} is not supported.")

    def addVlanQoS(self, tmpFD):
        """Add Vlan BW Request parameters"""
        self._getvlanlistqos()
        alllines = {}
        counter = 0
        for l2req in self.activeL2:
            interface = l2req["destport"]
            name = f"{interface}-{l2req['vlan']}"
            if not l2req["params"]:
                self.logger.info(
                    "This specific vlan request did not provided any QOS. \
                                 Ignoring QOS Rules for it"
                )
                continue
            outrate, outtype = self.convertToRate(l2req["params"])
            if self.params[interface]["intf_max"] - outrate <= 0:
                raise OverSubscribeException(f"Node is oversubscribed. Will not modify present QoS Rules. Max Rate: {self.params[interface]['intf_max']} Requested Rate: {outrate}")
            self.params[interface]["intf_max"] -= outrate
            # Get params from request
            reqclass = l2req["params"].get("type", "undefined")
            uri = l2req["params"].get("uri", "undefined")
            outlines = []
            outlines.append(f"# SENSE VLAN {l2req['vlan']} {l2req['destport']} {outrate}{outtype} Class: {reqclass}\n")
            outlines.append(f"# Request: {uri}\n")
            outlines.append("# " + "-"*80 + "\n")
            # In case it is: guaranteedCapped,softCapped,bestEffort - we add diff class
            if reqclass == "guaranteedCapped":
                outlines.append(f"interface vlan.{l2req['vlan']} {name} bidirectional rate {outrate}{outtype}\n")
            elif reqclass == "softCapped":
                outlines.append(f"interface vlan.{l2req['vlan']} {name} bidirectional rate ##REPLACEME##mbit\n")
                outlines.append(f"  class default rate {outrate}{outtype}\n")
                # interface vlan.2074 bond0-2074 bidirectional rate 20gbit
                #   class default commit 100mbit
            elif reqclass == "bestEffort":
                outlines.append(f"interface vlan.{l2req['vlan']} {name} bidirectional rate ##REPLACEME##mbit\n")
                outlines.append(f"  class default rate {outrate}{outtype}\n")
            else:
                outlines.append(f"interface vlan.{l2req['vlan']} {name} bidirectional rate {outrate}{outtype}\n")
                outlines.append(f"  class default rate {outrate}{outtype}\n")
            outlines.append("# " + "-"*80 + "\n\n")
            alllines[counter] = {"outlines": outlines, "outrate": outrate, "destport": interface,
                                 "outtype": outtype, "uri": uri, "reqclass": reqclass}
            counter += 1
        # Write everything into file
        for counter, l2req in alllines.items():

            maxintf = self.params[l2req["destport"]]["intf_max"] + l2req["outrate"]
            # In case request is bestEffort, we want it to be lower than softCapped or guaranteedCapped
            # So we check which ones evaluates first 1/10, 1/9, 1/8, 1/7, 1/6, 1/5, 1/4, 1/3, 1/2 (and last one is 1)
            # and take the max
            # Loop via range from 10 to 1
            if l2req["reqclass"] == "bestEffort":
                for i in range(10, 0, -1):
                    maxintf = max(maxintf//i, l2req["outrate"])
                    if maxintf > l2req["outrate"]:
                        break
            for line in l2req["outlines"]:
                line = line.replace("##REPLACEME##", str(maxintf))
                tmpFD.writelines(line)


    def getAllQOSed(self):
        """Read all configs and prepare qos doc."""
        self.logger.info("Getting All QoS rules.")
        self.getParams()
        fName = ""
        with tempfile.NamedTemporaryFile(delete=False, mode="w+") as tmpFile:
            fName = tmpFile.name
            self.addVlanQoS(tmpFile)
            self.addRSTQoS(tmpFile)
        return fName

    def startqos(self):
        """Main Start."""
        newFile = self.getAllQOSed()
        if not filecmp.cmp(newFile, "/etc/firehol/fireqos.conf"):
            self.logger.info("QoS rules are not equal. putting new config file")
            shutil.move(newFile, "/etc/firehol/fireqos.conf")
            self.restartQos()
        else:
            self.logger.info("QoS rules are equal. NTD")
            os.unlink(newFile)
