"""Routing interface component. Applys route rules on DTN

Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2021/01/20
"""

import re

from SiteRMLibs.CustomExceptions import (FailedInterfaceCommand, FailedRoutingCommand)
from SiteRMLibs.MainUtilities import (
    execute,
    externalCommand,
    getFullUrl,
    getLoggingObject,
    callSiteFE,
)


def publishState(modtype, uuid, hostname, state, fullURL):
    """Publish Agent apply state to Frontend."""
    out = {
        "uuidtype": "vsw",
        "uuid": uuid,
        "hostname": hostname,
        "hostport": modtype,
        "uuidstate": state,
    }
    callSiteFE(out, fullURL, "/sitefe/v1/deltatimestates", "POST")


class Rules:
    """Rules Class"""

    def __init__(self, rulercli):
        self.rulercli = rulercli
        self.rule_id = []
        self.rule_from = []
        self.rule_to = []
        self.rule_lookup = []
        self.rule_ip_table = []

    def clean(self):
        """Clean Rules class variables"""
        self.rule_id = []
        self.rule_from = []
        self.rule_to = []
        self.rule_lookup = []
        self.rule_ip_table = []

    def _add_iprange(self, rule_from):
        """Add IP range to rule"""
        # if it is all, then add None;
        rule_from = rule_from.decode("utf-8") if isinstance(rule_from, bytes) else rule_from
        if rule_from == "all":
            self.rule_ip_table.append(None)
        # if it is with / then it is already a range;
        elif "/" in rule_from:
            self.rule_ip_table.append(rule_from)
        overlaprange, _ = self.rulercli.findOverlapsRange(rule_from, "ipv6")
        if overlaprange:
            self.rule_ip_table.append(overlaprange)
        else:
            # if it is not a range, then add it as /128;
            self.rule_ip_table.append(None)

    def add_rule(self, rule_id, rule_from, rule_to, rule_lookup):
        """Add Rule to list"""
        def __to_str(val):
            """Convert value to string"""
            return val.decode("utf-8") if isinstance(val, bytes) else val

        self.rule_id.append(__to_str(rule_id))
        self.rule_from.append(__to_str(rule_from))
        self.rule_to.append(__to_str(rule_to))
        self.rule_lookup.append(__to_str(rule_lookup))
        # Identify from rule_from and IP range on the host;
        self._add_iprange(rule_from)


    @staticmethod
    def indices(lst, element):
        """Find all indices for rule"""
        result = []
        offset = -1
        while True:
            try:
                offset = lst.index(element, offset + 1)
            except ValueError:
                return result
            result.append(offset)

    def getvals(self, indices):
        """get all values for indices"""
        result = []
        if indices:
            for indx in indices:
                result.append(
                    [
                        self.rule_id[indx],
                        self.rule_from[indx],
                        self.rule_to[indx],
                        self.rule_lookup[indx],
                    ]
                )
        return result

    def lookup_id(self, val):
        """Lookup and get all values for id key"""
        return self.getvals(self.indices(self.rule_id, val))

    def lookup_from(self, val):
        """Lookup and get all values for from key"""
        return self.getvals(self.indices(self.rule_from, val))

    def lookup_to(self, val):
        """Lookup and get all values for to key"""
        return self.getvals(self.indices(self.rule_to, val))

    def lookup_lookup(self, val):
        """Lookup and get all values for lookup key"""
        return self.getvals(self.indices(self.rule_lookup, val))

    def lookup_from_lookup(self, rule_from, rule_lookup):
        """Lookup for from and lookup keys and get all values"""
        from_indx = self.indices(self.rule_from, rule_from)
        lookup_indx = self.indices(self.rule_lookup, rule_lookup)
        return self.getvals(list(set(from_indx) & set(lookup_indx)))

    def lookup_to_lookup(self, rule_to, rule_lookup):
        """Lookup for to and lookup keys and get all values"""
        to_indx = self.indices(self.rule_to, rule_to)
        lookup_indx = self.indices(self.rule_lookup, rule_lookup)
        return self.getvals(list(set(to_indx) & set(lookup_indx)))

    def lookup_iprange(self, ip_find):
        """Identify if ip_find is in any of the ranges"""
        overlaprange, _ = self.rulercli.findOverlapsRange(ip_find, "ipv6")
        if overlaprange:
            return self.getvals(
                self.indices(self.rule_ip_table, overlaprange)
            )
        return []

class Routing:
    """Virtual interface class."""

    def __init__(self, config, sitename, rulercli=None):
        self.config = config
        self.routingpolicy = self.config.get("qos", "policy")
        self.hostname = self.config.get("agent", "hostname")
        self.fullURL = getFullUrl(self.config, sitename)
        self.logger = getLoggingObject(config=self.config, service="Ruler")
        self.rules = Rules(rulercli)
        self._refreshRuleList()

    def _refreshRuleList(self):
        """Refresh Rule list from System"""
        self.rules.clean()
        command = "ip -6 rule list"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        if cmdOut.returncode != 0:
            raise FailedRoutingCommand(
                f"Failed to get rule list. Out: {out}, Err: {err}"
            )
        for line in out.split(b"\n"):
            match = re.match(rb"(\d+):[ \t]+from ([^ \t]+) lookup ([^ \t]+)$", line)
            if match:
                matched = match.groups()
                self.rules.add_rule(matched[0], matched[1], None, matched[2])
                continue
            match = re.match(
                rb"(\d+):[ \t]+from ([^ \t]+) to ([^ \t]+) lookup ([^ \t]+)$", line
            )
            if match:
                matched = match.groups()
                self.rules.add_rule(matched[0], matched[1], matched[2], matched[3])
            match = re.match(rb"(\d+):[ \t]+from ([^ \t]+) lookup ([^ \t]+)", line)
            if match:
                matched = match.groups()
                self.rules.add_rule(matched[0], matched[1], None, matched[2])

    def apply_rule(self, rule, deftable, findIp, raiseError=True):
        """Add specific rule."""
        tmprule = rule + f" table {deftable}"
        maineError = None
        try:
            return execute(tmprule, self.logger, raiseError)
        except FailedInterfaceCommand as exc:
            maineError = exc
        if findIp:
            # Identify table from rule lookup
            ruleentry = self.rules.lookup_iprange(findIp)
            if ruleentry:
                tmprule = rule + f" table {ruleentry[0][3]}"
                return execute(tmprule, self.logger, raiseError)
        # If we reach here, it means we couldn't find a suitable table
        raise maineError

    def terminate(self, route, uuid):
        """Terminate rules"""
        if self.routingpolicy != "hostlevel":
            self.logger.info(
                "Routing policy is not host level. Will not apply routing rules."
            )
            return []
        self._refreshRuleList()
        initialized = False
        try:
            if (
                route.get("src_ipv6_intf", "")
                and route.get("dst_ipv6", "")
                and self.rules.lookup_to(route["dst_ipv6"])
            ):
                initialized = True
                self.apply_rule(f"ip -6 rule del to {route['dst_ipv6']}", route['src_ipv6_intf'], route['src_ipv6'])
            if route.get("src_ipv6", "") and route.get("src_ipv6_intf", ""):
                if self.rules.lookup_from_lookup(f"{route['src_ipv6']}/128", route["src_ipv6_intf"]):
                    initialized = True
                    self.apply_rule(
                        f"ip -6 rule del from {route['src_ipv6']}/128", route['src_ipv6_intf'], route['src_ipv6']
                    )
                if self.rules.lookup_to_lookup(
                    f"{route['src_ipv6']}/128", route["src_ipv6_intf"]
                ):
                    initialized = True
                    self.apply_rule(
                        f"ip -6 rule del to {route['src_ipv6']}/128", route['src_ipv6_intf'], route['src_ipv6']
                    )
            if initialized:
                publishState("ipv6", uuid, self.hostname, "deactivated", self.fullURL)
        except FailedInterfaceCommand:
            if initialized:
                publishState(
                    "ipv6", uuid, self.hostname, "deactivate-error", self.fullURL
                )
        return []

    def activate(self, route, uuid):
        """Activate routes"""
        if self.routingpolicy != "hostlevel":
            self.logger.info(
                "Routing policy is not host level. Will not apply routing rules."
            )
            return []
        self._refreshRuleList()
        initialized = False
        try:
            if route.get("src_ipv6_intf", "") and route.get("dst_ipv6", ""):
                rules = self.rules.lookup_to_lookup(
                    route["dst_ipv6"], route["src_ipv6_intf"]
                )
                if not rules:
                    initialized = True
                    self.apply_rule(
                        f"ip -6 rule add to {route['dst_ipv6']}", route['src_ipv6_intf'], route['src_ipv6']
                    )

            if route.get("src_ipv6", "") and route.get("src_ipv6_intf", ""):
                rules = self.rules.lookup_from_lookup(
                    route["src_ipv6"], route["src_ipv6_intf"]
                )
                if not rules:
                    initialized = True
                    self.apply_rule(
                        f"ip -6 rule add from {route['src_ipv6']}/128", route['src_ipv6_intf'], route['src_ipv6']
                    )
                rules = self.rules.lookup_to_lookup(
                    route["src_ipv6"], route["src_ipv6_intf"]
                )
                if not rules:
                    initialized = True
                    self.apply_rule(
                        f"ip -6 rule add to {route['src_ipv6']}/128", route['src_ipv6_intf'], route['src_ipv6']
                    )
            if initialized:
                publishState("ipv6", uuid, self.hostname, "activated", self.fullURL)
        except FailedInterfaceCommand:
            if initialized:
                publishState(
                    "ipv6", uuid, self.hostname, "activate-error", self.fullURL
                )
        return []
