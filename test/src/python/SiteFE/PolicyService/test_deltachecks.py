#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Unit test for deltachecks

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/04/10
"""
import os
import unittest
import simplejson as json
import yaml
from SiteFE.PolicyService import policyService as polS
from SiteFE.PolicyService.deltachecks import ConflictChecker
from SiteRMLibs.MainUtilities import getGitConfig
from SiteRMLibs.CustomExceptions import OverlapException
from SiteRMLibs.CustomExceptions import WrongIPAddress

def loadJsonFile(inputFile):
    """Load Json File"""
    fname = f"{os.path.dirname(__file__)}/{inputFile}"
    with open(fname, 'r', encoding='utf-8') as fd:
        return json.load(fd)


class TestUtils(unittest.TestCase):
    """UnitTest"""
    PARAMS = {}

    @classmethod
    def setUpClass(cls):
        """Set Up Class. Load Git Config and PolicyService"""
        cls.rmConfig = getGitConfig()
        cls.polS = polS.PolicyService(cls.rmConfig, cls.PARAMS['sitename'])
        cls.conflictChecker = ConflictChecker()

    def test_checkConflicts_empty(self):
        """Check Conflicts between diff inputs"""
        # Check Empty Input. Expect: False
        out = self.conflictChecker.checkConflicts(self.polS, {}, {})
        self.assertFalse(out)

    def test_checkConflicts_newdata(self):
        """Check Conflicts when new data is received, but no config present"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/good-check.json')
        out = self.conflictChecker.checkConflicts(self.polS, inJson, {})
        self.assertFalse(out)

    def test_checkConflicts_olddata(self):
        """Check Conflicts when old data is present, but no new config"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/good-check.json')
        out = self.conflictChecker.checkConflicts(self.polS, {}, inJson)
        self.assertFalse(out)

    def test_checkConflicts_samedata(self):
        """Check Conflicts when old data is present, and new config is same"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/good-check.json')
        out = self.conflictChecker.checkConflicts(self.polS, inJson, inJson)
        self.assertFalse(out)

    def test_checkConflicts_badvlan(self):
        """Check Conflicts when vlan (1000) is provided and not accepted by config/site"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-vlan.json')
        self.assertRaises(OverlapException,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_badhostname(self):
        """Check Conflicts when hostname (dummyhostname.ultralight.org) is provided and not accepted by config/site"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-hostname.json')
        self.assertRaises(OverlapException,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_badswitchname(self):
        """Check Conflicts when switchname (dummyswitch_nameS1) is provided and not accepted by config/site"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-switchname.json')
        self.assertRaises(OverlapException,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_badipv4(self):
        """Check Conflicts when ipv4 (10.300.300.300/24) is provided and not valid"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-ipv4.json')
        self.assertRaises(WrongIPAddress,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_badipv6(self):
        """Check Conflicts when ipv6 (abcd:efgh::/64) is provided and not valid"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-ipv6.json')
        self.assertRaises(WrongIPAddress,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_badoverlap(self):
        """Check Conflicts once 2 deltas conflict"""
        # Check good input. Expect: False
        inJson = loadJsonFile('files_deltachecks/bad-overlap-1.json')
        in1Json = loadJsonFile('files_deltachecks/bad-overlap-2.json')
        self.assertRaises(OverlapException,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, in1Json)

    def test_checkConflicts_rstbadHostname(self):
        """Check Routing Service and provide bad next hop IP"""
        inJson = loadJsonFile('files_deltachecks/bad-rsthostname.json')
        self.assertRaises(OverlapException,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_rstnextHop(self):
        """Check Routing Service and provide bad next hop IP"""
        inJson = loadJsonFile('files_deltachecks/bad-rstnexthop.json')
        self.assertRaises(WrongIPAddress,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})

    def test_checkConflicts_rstRouteFrom(self):
        """Check Routing Service and provide RouteFrom not from configuration"""
        inJson = loadJsonFile('files_deltachecks/bad-rstroutefrom.json')
        self.assertRaises(WrongIPAddress,
                          self.conflictChecker.checkConflicts,
                          self.polS, inJson, {})


if __name__ == '__main__':
    conf = {}
    if not os.path.isfile('test-config.yaml'):
        raise Exception('Configuration file not available for unit test')
    with open('test-config.yaml', 'r', encoding='utf-8') as filed:
        conf = yaml.safe_load(filed)
    TestUtils.PARAMS = conf
    unittest.main()
