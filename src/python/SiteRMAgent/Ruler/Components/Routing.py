"""Routing interface component. Applys route rules on DTN

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2021/01/20
"""
import re
from SiteRMLibs.MainUtilities import execute
from SiteRMLibs.MainUtilities import externalCommand
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.MainUtilities import getFullUrl
from SiteRMLibs.MainUtilities import publishToSiteFE
from SiteRMLibs.CustomExceptions import FailedRoutingCommand
from SiteRMLibs.CustomExceptions import FailedInterfaceCommand


def publishState(modtype, uuid, hostname, state, fullURL):
    """Publish Agent apply state to Frontend."""
    out = {'uuidtype': 'vsw',
           'uuid': uuid,
           'hostname': hostname,
           'hostport': modtype,
           'uuidstate': state}
    publishToSiteFE(out, fullURL, f"/sitefe/v1/deltatimestates", 'POST')


class Rules:
    """Rules Class"""
    def __init__(self):
        self.rule_id = []
        self.rule_from = []
        self.rule_to = []
        self.rule_lookup = []

    def clean(self):
        """Clean Rules class variables"""
        self.rule_id = []
        self.rule_from = []
        self.rule_to = []
        self.rule_lookup = []

    def add_rule(self, rule_id, rule_from, rule_to, rule_lookup):
        """Add Rule to list"""
        self.rule_id.append(rule_id.decode("utf-8") if isinstance(rule_id, bytes) else rule_id)
        self.rule_from.append(rule_from.decode("utf-8") if isinstance(rule_from, bytes) else rule_from)
        self.rule_to.append(rule_to.decode("utf-8") if isinstance(rule_to, bytes) else rule_to)
        self.rule_lookup.append(rule_lookup.decode("utf-8") if isinstance(rule_lookup, bytes) else rule_lookup)

    @staticmethod
    def indices(lst, element):
        """Find all indices for rule"""
        result = []
        offset = -1
        while True:
            try:
                offset = lst.index(element, offset+1)
            except ValueError:
                return result
            result.append(offset)

    def getvals(self, indices):
        """get all values for indices"""
        result = []
        if indices:
            for indx in indices:
                result.append([self.rule_id[indx], self.rule_from[indx], self.rule_to[indx], self.rule_lookup[indx]])
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


class Routing:
    """Virtual interface class."""
    def __init__(self, config, sitename):
        self.config = config
        self.hostname = self.config.get('agent', 'hostname')
        self.fullURL = getFullUrl(self.config, sitename)
        self.logger = getLoggingObject(config=self.config, service='Ruler')
        self.rules = Rules()
        self._refreshRuleList()

    def _refreshRuleList(self):
        """Refresh Rule list from System"""
        self.rules.clean()
        command = "ip -6 rule list"
        cmdOut = externalCommand(command, False)
        out, err = cmdOut.communicate()
        if cmdOut.returncode != 0:
            raise FailedRoutingCommand(f"Failed to get rule list. Out: {out}, Err: {err}")
        for line in out.split(b'\n'):
            match = re.match(br'(\d+):[ \t]+from ([^ \t]+) lookup ([^ \t]+)$', line)
            if match:
                matched = match.groups()
                self.rules.add_rule(matched[0], matched[1], None, matched[2])
                continue
            match = re.match(br'(\d+):[ \t]+from ([^ \t]+) to ([^ \t]+) lookup ([^ \t]+)', line)
            if match:
                matched = match.groups()
                self.rules.add_rule(matched[0], matched[1], matched[2], matched[3])

    def apply_rule(self, rule, raiseError=True):
        """Add specific rule."""
        return execute(rule, self.logger, raiseError)

    def terminate(self, route, uuid):
        """Terminate rules"""
        self._refreshRuleList()
        initialized = False
        try:
            if route.get('src_ipv6_intf', '') and route.get('dst_ipv6', '') and self.rules.lookup_to(route['dst_ipv6']):
                initialized = True
                self.apply_rule(f"ip -6 rule del to {route['dst_ipv6']} table {route['src_ipv6_intf']}")
            if route.get('src_ipv6', '') and route.get('src_ipv6_intf', ''):
                if self.rules.lookup_from_lookup(f"{route['src_ipv6']}/128", route['src_ipv6_intf']):
                    initialized = True
                    self.apply_rule(f"ip -6 rule del from {route['src_ipv6']}/128 table {route['src_ipv6_intf']}")
                if self.rules.lookup_to_lookup(f"{route['src_ipv6']}/128", route['src_ipv6_intf']):
                    initialized = True
                    self.apply_rule(f"ip -6 rule del to {route['src_ipv6']}/128 table {route['src_ipv6_intf']}")
            if initialized:
                publishState('ipv6', uuid, self.hostname, 'deactivated', self.fullURL)
        except FailedInterfaceCommand:
            if initialized:
                publishState('ipv6', uuid, self.hostname, 'deactivate-error', self.fullURL)

    def activate(self, route, uuid):
        """Activate routes"""
        self._refreshRuleList()
        initialized = False
        try:
            if route.get('src_ipv6_intf', '') and route.get('dst_ipv6', '') and not self.rules.lookup_to(route['dst_ipv6']):
                initialized = True
                self.apply_rule(f"ip -6 rule add to {route['dst_ipv6']} table {route['src_ipv6_intf']}")
            if route.get('src_ipv6', '') and route.get('src_ipv6_intf', ''):
                if not self.rules.lookup_from_lookup(route['src_ipv6'], route['src_ipv6_intf']):
                    initialized = True
                    self.apply_rule(f"ip -6 rule add from {route['src_ipv6']}/128 table {route['src_ipv6_intf']}")
                if not self.rules.lookup_to_lookup(route['src_ipv6'], route['src_ipv6_intf']):
                    initialized = True
                    self.apply_rule(f"ip -6 rule add to {route['src_ipv6']}/128 table {route['src_ipv6_intf']}")
            if initialized:
                publishState('ipv6', uuid, self.hostname, 'activated', self.fullURL)
        except FailedInterfaceCommand:
            if initialized:
                publishState('ipv6', uuid, self.hostname, 'activate-error', self.fullURL)
