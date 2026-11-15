"""Unit tests for Switch port-name mapping (model name -> device port name).

No SiteFE instance, config, or database required.
"""

import os
import tempfile
import unittest
from unittest import mock

# Backends.parsers loads the startup and Git config at import; stub both.
with tempfile.NamedTemporaryFile("w", suffix=".yaml") as _conf:
    _conf.write("SITENAME: T0_TEST\n")
    _conf.flush()
    with (
        mock.patch.dict(os.environ, {"SITERM_CONFIG_FILE": _conf.name}),
        mock.patch("SiteRMLibs.GitConfig.getGitConfig", return_value={}),
    ):
        from SiteRMLibs.Backends.main import Switch


class PortMappingTest(unittest.TestCase):
    """Verify getSwitchPortName resolves model port names back to real device ports."""

    @staticmethod
    def _switch(ports):
        sw = Switch.__new__(Switch)
        sw.switches = {"output": {"sw0": {}}}
        sw.output = {"ports": {"sw0": ports}, "vlans": {}, "portMapping": {}}
        sw._getPortMapping()  # pylint: disable=protected-access
        return sw

    def test_virtual_port_sanitized_name(self):
        """Sanitized virtual config name (as sent by the orchestrator) maps to realportname."""
        sw = self._switch({"Ethernet23/1-wc411": {"realportname": "Ethernet23/1"}})
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet23-1-wc411"), "Ethernet23/1")
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet23/1-wc411"), "Ethernet23/1")
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet23-1"), "Ethernet23/1")

    def test_physical_port(self):
        """Physical ports keep resolving by raw and sanitized name."""
        sw = self._switch({"Ethernet12/1": {"realportname": "Ethernet12/1"}})
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet12-1"), "Ethernet12/1")
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet12/1"), "Ethernet12/1")

    def test_unknown_port_passthrough(self):
        """Unknown names are returned unchanged."""
        sw = self._switch({})
        self.assertEqual(sw.getSwitchPortName("sw0", "Ethernet99-1"), "Ethernet99-1")


if __name__ == "__main__":
    unittest.main()
