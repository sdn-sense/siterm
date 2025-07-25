"""Test Frontend"""

import http.client
import os
import time
import unittest

import yaml
from SiteRMLibs.HTTPLibrary import Requests


def makeRequest(cls, url, params):
    """Make HTTP Request"""
    # pylint: disable=no-member
    req = Requests(cls.PARAMS["hostname"], {})
    try:
        out = req.makeRequest(url, **params)
    except http.client.HTTPException as ex:
        return ex.result, ex.status, ex.reason, ex
    return out


def debugActions(cls):
    """Test Debug Actions: submit, get update"""
    # SUBMIT
    data = {
        "dynamicfrom": "2001:48d0:3001:114::/64",
        "type": "iperf-server",
        "sitename": "",
        "hostname": "undefined",
        "onetime": "True",
        "ip": "0.0.0.0",
        "port": "12345",
        "time": "300",
    }  # Random between high ones
    urls = f"/api/{cls.PARAMS['sitename']}/debug"
    outs = makeRequest(cls, urls, {"verb": "POST", "data": data})
    cls.assertEqual(outs[1], 200, msg=f"Failed to POST {data} to {urls}. Output: {outs}")
    cls.assertEqual(outs[2], "OK", msg=f"Failed to POST {data} to {urls}. Output: {outs}")
    # GET (and wait for selectedip parameter)
    while True:
        urlg = f"/api/{cls.PARAMS['sitename']}/debug/{outs[0]['ID']}"
        outg = makeRequest(cls, urlg, {"verb": "GET", "data": {}})
        cls.assertEqual(outg[1], 200, msg=f"Failed to GET {urlg}. Output: {outs}")
        cls.assertEqual(outg[2], "OK", msg=f"Failed to GET {urlg}. Output: {outs}")
        print(outg)
        if outg[0].get("requestdict", {}).get("selectedip", ""):
            selectedip = outg[0]["requestdict"]["selectedip"]
            break
        time.sleep(5)
    # Now here we have selected IP, need to submit iperf-client
    data = {
        "dynamicfrom": "2001:48d0:3001:11a::/64",
        "type": "iperf-client",
        "sitename": "",
        "hostname": "undefined",
        "onetime": "True",
        "ip": selectedip,
        "port": "12345",
        "time": "300",
    }  # Random between high ones
    urls = f"/api/{cls.PARAMS['sitename']}/debug"
    outs = makeRequest(cls, urls, {"verb": "POST", "data": data})
    cls.assertEqual(outs[1], 200, msg=f"Failed to POST {data} to {urls}. Output: {outs}")
    cls.assertEqual(outs[2], "OK", msg=f"Failed to POST {data} to {urls}. Output: {outs}")
    time.sleep(5)
    urlg = f"/api/{cls.PARAMS['sitename']}/debug/{outs[0]['ID']}"
    outg = makeRequest(cls, urlg, {"verb": "GET", "data": {}})
    cls.assertEqual(outg[1], 200, msg=f"Failed to GET {urlg}. Output: {outs}")
    cls.assertEqual(outg[2], "OK", msg=f"Failed to GET {urlg}. Output: {outs}")
    print(outg)


class TestUtils(unittest.TestCase):
    """UnitTest"""

    PARAMS = {}

    @classmethod
    def setUpClass(cls):
        """Set Up Class. Set CERT/KEY env params"""
        os.environ["X509_USER_KEY"] = cls.PARAMS["key"]
        os.environ["X509_USER_CERT"] = cls.PARAMS["cert"]

    def test_dynamic_debug_iperf_server(self):
        """Test Debug IperfServer API"""
        debugActions(self)


if __name__ == "__main__":
    conf = {}
    if not os.path.isfile("test-config.yaml"):
        raise Exception("Configuration file not available for unit test")
    with open("test-config.yaml", "r", encoding="utf-8") as fd:
        conf = yaml.safe_load(fd)
    TestUtils.PARAMS = conf
    unittest.main()
