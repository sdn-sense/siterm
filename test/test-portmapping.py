"""Unit tests for virtual (realportname) switch port handling across model, policy and provisioning names.

No SiteFE instance, config, or database required.
"""

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

# Backends.parsers and PolicyService load the startup config, Git config and DB at import; stub them.
with tempfile.NamedTemporaryFile("w", suffix=".yaml") as _conf:
    _conf.write("SITENAME: T0_TEST\n")
    _conf.flush()
    with (
        mock.patch.dict(os.environ, {"SITERM_CONFIG_FILE": _conf.name}),
        mock.patch("SiteRMLibs.GitConfig.getGitConfig", return_value={}),
        mock.patch("SiteRMLibs.MainUtilities.getDBConnObj"),
    ):
        from SiteFE.PolicyService.deltachecks import ConflictChecker
        from SiteFE.PolicyService.policyService import PolicyService
        from SiteRMLibs.Backends.main import Switch
        from SiteRMLibs.CustomExceptions import OverlapException

# pylint: disable=protected-access

SW = "sw0"
CONFPORTS = {
    "Ethernet23/1-wc411": {"realportname": "Ethernet23/1", "vlan_range_list": [1425, 1426], "isAlias": "urn:ogf:network:peer:2020:sw:Eth1"},
    "Ethernet12/1": {"vlan_range_list": [1500]},
}


def _switch(ports):
    """Switch with only port mapping state populated."""
    sw = Switch.__new__(Switch)
    sw.switches = {"output": {SW: {}}}
    sw.output = {"ports": {SW: ports}, "vlans": {}, "portMapping": {}}
    sw._getPortMapping()
    return sw


def _polcls():
    """Minimal PolicyService stand-in for ConflictChecker static checks."""
    config = SimpleNamespace(getraw=lambda _key: {SW: {"vlan_range_list": [1425, 1500, 4000], "ports": CONFPORTS}})
    ports = {"Ethernet23/1-wc411": {"realportname": "Ethernet23/1"}, "Ethernet12/1": {"realportname": "Ethernet12/1"}}
    return SimpleNamespace(config=config, switch=_switch(ports), hosts={})


class PortMappingTest(unittest.TestCase):
    """getSwitchPortName resolves model port names back to real device ports."""

    def test_virtual_port_sanitized_name(self):
        """Sanitized virtual config name (as sent by the orchestrator) maps to realportname."""
        sw = _switch({"Ethernet23/1-wc411": {"realportname": "Ethernet23/1"}})
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet23-1-wc411"), "Ethernet23/1")
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet23/1-wc411"), "Ethernet23/1")
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet23-1"), "Ethernet23/1")

    def test_physical_port(self):
        """Physical ports keep resolving by raw and sanitized name."""
        sw = _switch({"Ethernet12/1": {"realportname": "Ethernet12/1"}})
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet12-1"), "Ethernet12/1")
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet12/1"), "Ethernet12/1")

    def test_unknown_port_passthrough(self):
        """Unknown names are returned unchanged."""
        sw = _switch({})
        self.assertEqual(sw.getSwitchPortName(SW, "Ethernet99-1"), "Ethernet99-1")


class DeltaChecksPortTest(unittest.TestCase):
    """Delta checks find per-port config for sanitized model names."""

    def test_conf_port_lookup(self):
        """Sanitized and raw names find the config entry; unknown returns empty."""
        polcls = _polcls()
        self.assertIs(ConflictChecker._getConfPort(polcls, SW, "Ethernet23-1-wc411"), CONFPORTS["Ethernet23/1-wc411"])
        self.assertIs(ConflictChecker._getConfPort(polcls, SW, "Ethernet12-1"), CONFPORTS["Ethernet12/1"])
        self.assertEqual(ConflictChecker._getConfPort(polcls, SW, "Ethernet99-1"), {})

    def test_virtual_port_vlan_range_enforced(self):
        """Virtual port uses its own vlan range, not the device range."""
        polcls = _polcls()
        ConflictChecker._checkVlanInRange(polcls, {"vlan": 1425, "interface": "Ethernet23-1-wc411"}, SW)
        with self.assertRaises(OverlapException):
            ConflictChecker._checkVlanInRange(polcls, {"vlan": 4000, "interface": "Ethernet23-1-wc411"}, SW)

    def test_physical_port_vlan_range_enforced(self):
        """Physical port range keeps applying via sanitized name."""
        polcls = _polcls()
        ConflictChecker._checkVlanInRange(polcls, {"vlan": 1500, "interface": "Ethernet12-1"}, SW)
        with self.assertRaises(OverlapException):
            ConflictChecker._checkVlanInRange(polcls, {"vlan": 1425, "interface": "Ethernet12-1"}, SW)

    def test_virtual_port_alias_checked(self):
        """isAlias mismatch on a virtual port is rejected."""
        polcls = _polcls()
        ConflictChecker._checkIsAlias(polcls, SW, {"Ethernet23-1-wc411": {"isAlias": "urn:ogf:network:peer:2020:sw:Eth1"}})
        with self.assertRaises(OverlapException):
            ConflictChecker._checkIsAlias(polcls, SW, {"Ethernet23-1-wc411": {"isAlias": "urn:ogf:network:other:2020:sw:Eth9"}})


class DeltaStatePortsTest(unittest.TestCase):
    """Reported delta states (device port names) find the active-delta model port."""

    def setUp(self):
        self.pol = SimpleNamespace(switch=_polcls().switch)
        self.hostEntry = {"Ethernet23-1-wc411": {"hasLabel": {}}, "Ethernet12-1": {"hasLabel": {}}, "_params": {"x": 1}}

    def _ports(self, hostport):
        return PolicyService._deltaStatePorts(self.pol, self.hostEntry, SW, hostport)

    def test_exact_match(self):
        """Physical port names match directly."""
        self.assertEqual(self._ports("Ethernet12-1"), ["Ethernet12-1"])

    def test_device_port_maps_to_virtual(self):
        """Provisioning reports the real port; it maps back to the virtual model port."""
        self.assertEqual(self._ports("Ethernet23-1"), ["Ethernet23-1-wc411"])

    def test_unknown(self):
        """Unknown ports match nothing."""
        self.assertEqual(self._ports("Ethernet99-1"), [])


if __name__ == "__main__":
    unittest.main()
