#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Virtual interfaces component, which creates or tierdowns virtual interface.
This is called from a Ruler component.

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/01/20
"""
from dataclasses import dataclass

from pyroute2 import IPRoute
from SiteRMLibs.CustomExceptions import FailedInterfaceCommand
from SiteRMLibs.ipaddr import (
    getBroadCast,
    getIfAddrStats,
    getInterfaceIP,
    getInterfaces,
    getInterfaceTxQueueLen,
    normalizedip,
    normalizedipwithnet,
)
from SiteRMLibs.MainUtilities import execute


@dataclass
class PublishStateInput:
    """Data class for publish state input parameters."""

    vlan: dict
    inParams: dict
    uuid: str
    hostname: str
    state: str
    sitename: str


def publishState(reqHandler, item: PublishStateInput):
    """Publish Agent apply state to Frontend."""
    oldState = item.inParams.get(item.vlan["destport"], {}).get("_params", {}).get("networkstatus", "unknown")
    if item.state != oldState:
        out = {
            "uuidtype": "vsw",
            "uuid": item.uuid,
            "hostname": item.hostname,
            "hostport": item.vlan["destport"],
            "uuidstate": item.state,
        }
        reqHandler.makeHttpCall("POST", f"/api/{item.sitename}/deltas/{item.uuid}/timestates", data=out, retries=1, raiseEx=False, useragent="Ruler")


def getDefaultMTU(config, intfKey):
    """Get Default MTU"""
    if config.has_section(intfKey):
        if config.has_option(intfKey, "defaultMTU"):
            return int(config.get(intfKey, "defaultMTU"))
    elif config.has_section("agent"):
        if config.has_option("agent", "defaultMTU"):
            return int(config.get("agent", "defaultMTU"))
    defaultMTU = 1500
    _, ifstats = getIfAddrStats()
    try:
        defaultMTU = ifstats[intfKey].mtu
    except Exception as ex:
        print(f"Failed to get mtu for {intfKey}. Error: {ex}. Use default 1500.")
    return defaultMTU


def getDefaultTXQ(config, intfKey):
    """Get Default Txqueuelen"""
    if config.has_section(intfKey):
        if config.has_option(intfKey, "defaultTXQueuelen"):
            return int(config.get(intfKey, "defaultTXQueuelen"))
    elif config.has_section("agent"):
        if config.has_option("agent", "defaultTXQueuelen"):
            return int(config.get("agent", "defaultTXQueuelen"))
    # If we reach here, means not set in config.
    # We try to get it from system and use same as master intf;
    # if unable, use 1000 by default
    defaultTXQ = 1000
    try:
        defaultTXQ = getInterfaceTxQueueLen(intfKey)
    except Exception as ex:
        print(f"Failed to get txqueuelen for {intfKey}. Error: {ex}. Use default 1000.")
    return defaultTXQ


def intfUp(intf):
    """Check if Interface is up"""
    state = "DOWN"
    with IPRoute() as ipObj:
        state = ipObj.get_links(ipObj.link_lookup(ifname=intf)[0])[0].get_attr("IFLA_OPERSTATE")
    return state == "UP"


class VInterfaces:
    """Virtual interface class."""

    def __init__(self, config, sitename, logger, rulercli):
        self.config = config
        self.sitename = sitename
        self.hostname = self.config.get("agent", "hostname")
        self.logger = logger
        self.requestHandler = rulercli.requestHandler

    def _add(self, vlan, raiseError=False):
        """Add specific vlan."""
        self.logger.info(f"Called VInterface add L2 for {str(vlan)}")
        command = f"ip link add link {vlan['destport']} name vlan.{vlan['vlan']} type vlan id {vlan['vlan']}"
        return execute(command, self.logger, raiseError)

    def _setup(self, vlan, raiseError=False):
        """Setup vlan."""
        if "ip" in vlan.keys() and vlan["ip"]:
            self.logger.info(f"Called VInterface IPv4 setup L2 for {str(vlan)}")
            command = f"ip addr add {vlan['ip']} broadcast {getBroadCast(vlan['ip'])} dev vlan.{vlan['vlan']}"
            execute(command, self.logger, raiseError)
        elif "ipv6" in vlan.keys() and vlan["ipv6"]:
            self.logger.info(f"Called VInterface IPv6 setup L2 for {str(vlan)}")
            command = f"ip addr add {vlan['ipv6']} broadcast {getBroadCast(vlan['ipv6'])} dev vlan.{vlan['vlan']}"
            execute(command, self.logger, raiseError)
        else:
            self.logger.info(f"Called VInterface setup for {str(vlan)}, but ip/ipv6 keys are not present.")
            self.logger.info("Continue as nothing happened")
        # Set MTU and Txqueuelen
        if "mtu" in vlan.keys() and vlan["mtu"]:
            command = f"ip link set dev vlan.{vlan['vlan']} mtu {vlan['mtu']}"
            execute(command, self.logger, raiseError)
        if "txqueuelen" in vlan.keys() and vlan["txqueuelen"]:
            command = f"ip link set dev vlan.{vlan['vlan']} txqueuelen {vlan['txqueuelen']}"
            execute(command, self.logger, raiseError)

    # def _removeIP(self, vlan, raiseError=False):
    #    """Remove IP from vlan"""
    #    if "ip" in vlan.keys() and vlan["ip"]:
    #        self.logger.info(f"Called VInterface IPv4 remove IP for {str(vlan)}")
    #        command = f"ip addr del {vlan['ip']} broadcast {getBroadCast(vlan['ip'])} dev vlan.{vlan['vlan']}"
    #        execute(command, self.logger, raiseError)
    #    elif "ipv6" in vlan.keys() and vlan["ipv6"]:
    #        self.logger.info(f"Called VInterface IPv6 remote IP for {str(vlan)}")
    #        command = f"ip addr del {vlan['ipv6']} broadcast {getBroadCast(vlan['ipv6'])} dev vlan.{vlan['vlan']}"
    #        execute(command, self.logger, raiseError)
    #    else:
    #        self.logger.info(f"Called VInterface remove ip for {str(vlan)}, but ip/ipv6 keys are not present.")
    #        self.logger.info("Continue as nothing happened")

    def _start(self, vlan, raiseError=False):
        """Start specific vlan."""
        self.logger.info(f"Called VInterface start L2 for {str(vlan)}")
        command = f"ip link set dev vlan.{vlan['vlan']} up"
        return execute(command, self.logger, raiseError)

    def _stop(self, vlan, raiseError=False):
        """Stop specific vlan."""
        out = []
        self.logger.info(f"Called VInterface L2 stop for {str(vlan)}")
        for command in [f"ip link set dev vlan.{vlan['vlan']} down"]:
            out.append(execute(command, self.logger, raiseError))
        return out

    def _remove(self, vlan, raiseError=False):
        """Remove specific vlan."""
        out = []
        self.logger.info(f"Called VInterface remove for {str(vlan)}")
        for command in [f"ip link delete dev vlan.{vlan['vlan']}"]:
            out.append(execute(command, self.logger, raiseError))
        return out

    @staticmethod
    def _statusvlan(vlan, raiseError=False):
        """Get status of specific vlan."""
        del raiseError
        if f"vlan.{vlan['vlan']}" not in getInterfaces():
            return False
        return True

    @staticmethod
    def _statusvlanIP(vlan, raiseError=False):
        """Check if IP set on vlan"""
        del raiseError
        allIPs = getInterfaceIP(f"vlan.{vlan['vlan']}")
        ip4Exists = False
        if "ip" in vlan and vlan["ip"]:
            serviceIp = vlan["ip"].split("/")[0]
            for ipv4m in allIPs.get(2, {}):
                if serviceIp == ipv4m["addr"]:
                    ip4Exists = True
                    break
        else:
            # IPv4 IP was not requested.
            ip4Exists = True
        ip6Exists = False
        if "ipv6" in vlan and vlan["ipv6"]:
            vlan["ipv6"] = normalizedip(vlan["ipv6"])
            for ipv6m in allIPs.get(10, {}):
                if vlan["ipv6"] == normalizedipwithnet(ipv6m.get("addr", ""), ipv6m.get("netmask", "")):
                    ip6Exists = True
        else:
            # IPv6 IP was not requested.
            ip6Exists = True
        return ip4Exists and ip6Exists

    def _getvlanlist(self, inParams):
        """Get All Vlan List"""
        vlans = []
        for key, vals in inParams.items():
            uri = vals.get("uri", "")
            if uri and uri.endswith(f"{self.hostname}:{key}"):
                continue
            netInfo = vals.get("hasNetworkAddress", {})
            vlan = {
                "destport": key,
                "vlan": vals.get("hasLabel", {}).get("value", ""),
                "ip": netInfo.get("ipv4-address", {}).get("value", ""),
                "ipv6": netInfo.get("ipv6-address", {}).get("value", ""),
                "mtu": netInfo.get("mtu", {}).get("value", getDefaultMTU(self.config, key)),
                "txqueuelen": netInfo.get("txqueuelen", {}).get("value", getDefaultTXQ(self.config, key)),
            }
            if not vlan["vlan"]:
                self.logger.error(f"VLAN ID is not set for {key}. Skipping this interface. All info: {inParams}")
                continue
            if uri.endswith(f'{self.hostname}:{key}:vlanport+{vlan["vlan"]}'):
                continue
            vlans.append(vlan)
        return vlans

    def activate(self, inParams, uuid):
        """Activate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            try:
                if self._statusvlan(vlan, True):
                    if not self._statusvlanIP(vlan, True):
                        self._setup(vlan, True)
                else:
                    self._add(vlan, True)
                    self._setup(vlan, True)
                if not intfUp(f"vlan.{vlan['vlan']}"):
                    self._start(vlan, True)
                publishState(self.requestHandler, PublishStateInput(vlan, inParams, uuid, self.hostname, "activated", self.sitename))
            except FailedInterfaceCommand:
                publishState(self.requestHandler, PublishStateInput(vlan, inParams, uuid, self.hostname, "activate-error", self.sitename))
        return vlans

    def terminate(self, inParams, uuid):
        """Terminate Virtual Interface resources"""
        vlans = self._getvlanlist(inParams)
        for vlan in vlans:
            try:
                if self._statusvlan(vlan, False):
                    self._stop(vlan, False)
                    self._remove(vlan, False)
                publishState(self.requestHandler, PublishStateInput(vlan, inParams, uuid, self.hostname, "deactivated", self.sitename))
            except FailedInterfaceCommand:
                publishState(self.requestHandler, PublishStateInput(vlan, inParams, uuid, self.hostname, "deactivate-error", self.sitename))
        return vlans

    def modify(self, oldParams, newParams, uuid):
        """Modify Virtual Interface resources"""
        old = self._getvlanlist(oldParams)
        new = self._getvlanlist(newParams)
        if old == new:
            # This can happen if we modify QOS only. So there is no IP or VLAN change.
            return []
        if old:
            self.terminate(oldParams, uuid)
        if new:
            self.activate(newParams, uuid)
        return new
