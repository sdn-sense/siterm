"""Test Frontend"""

import http.client
import os
import pathlib
import unittest

import simplejson as json
import yaml
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import getUTCnow


def makeRequest(cls, url, params):
    """Make HTTP Request"""
    req = Requests(cls.PARAMS["hostname"], {})
    try:
        out = req.makeRequest(url, **params)
    except http.client.HTTPException as ex:
        return ex.result, ex.status, ex.reason, ex
    return out


def debugActions(cls, dataIn, dataUpd):
    """Test Debug Actions: submit, get update"""
    # SUBMIT
    urls = f"/api/{cls.PARAMS['sitename']}/debug"
    outs = makeRequest(cls, urls, {"verb": "POST", "data": dataIn})
    cls.assertEqual(outs[1], 200, msg=f"Failed to POST {dataIn} to {urls}. Output: {outs}")
    cls.assertEqual(outs[2], "OK", msg=f"Failed to POST {dataIn} to {urls}. Output: {outs}")
    # GET
    urlg = f"/api/{cls.PARAMS['sitename']}/debug/{outs[0]['ID']}"
    outg = makeRequest(cls, urlg, {"verb": "GET", "data": {}})
    cls.assertEqual(outg[1], 200, msg=f"Failed to GET {urlg}. Output: {outs}")
    cls.assertEqual(outg[2], "OK", msg=f"Failed to GET {urlg}. Output: {outs}")
    # UPDATE
    urlu = f"/api/{cls.PARAMS['sitename']}/debug/{outs[0]['ID']}"
    outu = makeRequest(cls, urlu, {"verb": "PUT", "data": dataUpd})
    cls.assertEqual(outu[1], 200, msg=f"Failed to PUT {dataUpd} to {urlu}. Output: {outs}")
    cls.assertEqual(outu[2], "OK", msg=f"Failed to PUT {dataUpd} to {urlu}. Output: {outs}")
    # DELETE
    urld = f"/api/{cls.PARAMS['sitename']}/debug/{outs[0]['ID']}"
    outd = makeRequest(cls, urld, {"verb": "DELETE", "data": {}})
    cls.assertEqual(outd[1], 200, msg=f"Failed to DELETE on {urld}. Output: {outs}")
    cls.assertEqual(outd[2], "OK", msg=f"Failed to DELETE on {urld}. Output: {outs}")


class TestUtils(unittest.TestCase):
    """UnitTest"""

    PARAMS = {}

    @classmethod
    def setUpClass(cls):
        """Set Up Class. Set CERT/KEY env params"""
        os.environ["X509_USER_KEY"] = cls.PARAMS["key"]
        os.environ["X509_USER_CERT"] = cls.PARAMS["cert"]

    def test_fake_url(self):
        """Test Fake Url"""
        url = "/api/NoSiteName/no/url/"
        for action in ["GET", "POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {"verb": action, "data": {}})
            self.assertIn(out[1], [404, 405], msg=f"Failed to {action} on {url}. Output: {out}")

    def test_config(self):
        """Test to get Config"""
        url = "/frontend/configuration"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {"verb": action, "data": {}})
            self.assertEqual(out[1], 405, msg=f"Failed to {action} on {url}. Output: {out}")

    def test_metrics(self):
        """Test metrics API"""
        url = f"/api/{self.PARAMS['sitename']}/prometheus/metrics"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {"verb": action, "data": {}})
            self.assertEqual(out[1], 405, msg=f"Failed to {action} on {url}. Output: {out}")
            self.assertEqual(
                out[2],
                "Method Not Allowed",
                msg=f"Failed to {action} on {url}. Output: {out}",
            )

    def test_getdebug(self):
        """Test getdebug API"""
        url = f"/api/{self.PARAMS['sitename']}/debug"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {"verb": action, "data": {}})
            self.assertIn(out[1], [400, 405], msg=f"Failed to {action} on {url}. Output: {out}")
            self.assertIn(
                out[2],
                ["Bad Request", "Method Not Allowed"],
                msg=f"Failed to {action} on {url}. Output: {out}",
            )

    def test_getalldebughostname(self):
        """Test getalldebughostname API"""
        for item in ["new", "active", "failed"]:
            url = f"/api/{self.PARAMS['sitename']}/debug?hostname=dummyhostname&state={item}"
            out = makeRequest(self, url, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
            self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
            for action in ["POST", "PUT", "DELETE"]:
                out = makeRequest(self, url, {"verb": action, "data": {}})
                self.assertIn(
                    out[1],
                    [400, 405],
                    msg=f"Failed to {action} on {url}. Output: {out}",
                )
                self.assertIn(
                    out[2],
                    ["Bad Request", "Method Not Allowed"],
                    msg=f"Failed to {action} on {url}. Output: {out}",
                )

    def test_debug_ping(self):
        """Test Debug ping API"""
        # rapidping, tcpdump, arptable, iperf, iperfserver
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "rapid-ping"],
            ["dellos9_s0", "switch", "rapid-ping"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "ip": "1.2.3.4",
                "packetsize": "32",
                "interval": "1",
                "interface": "dummyinterface",
                "time": "60",
            }
            outsuc = {
                "out": ["ping success", "from unittest"],
                "err": "",
                "exitCode": 0,
            }
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_arptable(self):
        """Test Debug arptable API"""
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "arp-table"],
            ["dellos9_s0", "switch", "arp-table"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "interface": "dummyinterface",
            }
            outsuc = {"out": ["arp success", "from unittest"], "err": "", "exitCode": 0}
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
            debugActions(self, data, dataupd)

    def test_debug_tcpdump(self):
        """Test Debug TCPDump API"""
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "tcpdump"],
            ["dellos9_s0", "switch", "tcpdump"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "interface": "dummyinterface",
            }
            outsuc = {
                "out": ["tcpdump success", "from unittest"],
                "err": "",
                "exitCode": 0,
            }
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
            debugActions(self, data, dataupd)

    def test_debug_traceroute(self):
        """Test Debug Traceroute API"""
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "traceroute"],
            ["dellos9_s0", "switch", "traceroute"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "from_interface": "dummyinterface",
                "from_ip": "1.2.3.4",
                "ip": "8.8.8.8",
            }
            outsuc = {
                "out": ["traceroute success", "from unittest"],
                "err": "",
                "exitCode": 0,
            }
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
            debugActions(self, data, dataupd)

    def test_debug_iperf_client(self):
        """Test Debug Iperf API"""
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "iperf-client"],
            ["dellos9_s0", "switch", "iperf-client"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "interface": "dummyinterface",
                "ip": "1.2.3.4",
                "port": "1234",
                "time": "60",
            }
            outsuc = {
                "out": ["iperf success", "from unittest"],
                "err": "",
                "exitCode": 0,
            }
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
            debugActions(self, data, dataupd)

    def test_debug_iperf_server(self):
        """Test Debug IperfServer API"""
        hostdata = [
            ["sdn-dtn-1-7.ultralight.org", "host", "iperf-server"],
            ["dellos9_s0", "switch", "iperf-server"],
        ]
        for item in hostdata:
            data = {
                "type": item[2],
                "sitename": "",
                "hostname": item[0],
                "onetime": "True",
                "interface": "dummyinterface",
                "ip": "1.2.3.4",
                "port": "1234",
                "time": "60",
            }
            outsuc = {
                "out": ["iperf server success", "from unittest"],
                "err": "",
                "exitCode": 0,
            }
            dataupd = {"state": "success", "output": json.dumps(outsuc)}
            debugActions(self, data, dataupd)

    def test_fake_cert(self):
        """Test Fake Cert Failure"""
        # Save good keys.
        x509_key = os.environ["X509_USER_KEY"]
        x509_cert = os.environ["X509_USER_CERT"]
        # Script working dir
        work_dir = pathlib.Path(__file__).parent.resolve()
        os.environ["X509_USER_KEY"] = f"{work_dir}/certs/host.key"
        os.environ["X509_USER_CERT"] = f"{work_dir}/certs/host.cert"
        url = "/api/frontend/configuration"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        os.environ["X509_USER_KEY"] = x509_key
        os.environ["X509_USER_CERT"] = x509_cert
        self.assertEqual(out[1], 401, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "Unauthorized", msg=f"Failed to GET on {url}. Output: {out}")

    def test_getdata(self):
        """Test to get agentdata"""
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")

    def test_addhost(self):
        """Test to addhost"""
        dic = {
            "hostname": "unittest",
            "ip": "1.2.3.4",
            "insertTime": getUTCnow(),
            "updateTime": getUTCnow(),
            "NetInfo": {"unittest": "randomvalue"},
        }
        # Add Host
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "PUT", "data": dic})
        self.assertEqual(out[1], 200, msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        # Delete Host
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "POST", "data": dic})
        self.assertEqual(out[1], 200, msg=f"Failed to POST on {url}. DataIn: {dic}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to POST on {url}. DataIn: {dic}. Output: {out}")

    def test_updatehost(self):
        """Test updatehost"""
        dic = {
            "hostname": "unittest",
            "ip": "1.2.3.4",
            "insertTime": getUTCnow(),
            "updateTime": getUTCnow(),
            "NetInfo": {"unittest": "randomvalue"},
        }
        # Add Host
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "PUT", "data": dic})
        self.assertEqual(out[1], 200, msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        # Update Host
        dic["NetInfo"] = {"updateunittest": "updaterandomvalue"}
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "PUT", "data": dic})
        self.assertEqual(out[1], 200, msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to PUT on {url}. DataIn: {dic}. Output: {out}")
        # Get Host
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        # Delete Host
        url = f"/api/{self.PARAMS['sitename']}/hosts"
        out = makeRequest(self, url, {"verb": "POST", "data": dic})
        self.assertEqual(out[1], 200, msg=f"Failed to POST on {url}. DataIn: {dic}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to POST on {url}. DataIn: {dic}. Output: {out}")

    def test_getactivedeltas(self):
        """Test getactivedeltas"""
        url = f"/api/{self.PARAMS['sitename']}/frontend/activedeltas"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")

    def test_getswitchdata(self):
        """Test getswitchdata"""
        url = f"/api/{self.PARAMS['sitename']}/frontend/getswitchdata"
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")

    def test_getmodels(self):
        """Test models"""
        options = [
            ["summary", True, 200, "OK"],
            ["current", True, 200, "OK"],
            ["oldview", True, 200, "OK"],
            ["encode", True, 200, "OK"],
            ["model", "turtle", 200, "OK"],
            ["model", "json-ld", 200, "OK"],
            ["model", "ntriples", 200, "OK"],
            ["summary", False, 200, "OK"],
            ["current", False, 200, "OK"],
            ["oldview", False, 200, "OK"],
            ["encode", False, 200, "OK"],
            ["model", "dummyRandom", 400, "Bad Request"],
        ]
        url = f"/api/{self.PARAMS['sitename']}/models"
        for option in options:
            tmpurl = url + f"?{option[0]}={option[1]}"
            out = makeRequest(self, tmpurl, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], option[2], msg=f"Failed to GET on {tmpurl}. Output: {out}")
            self.assertEqual(out[2], option[3], msg=f"Failed to GET on {tmpurl}. Output: {out}")
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        if len(out) >= 1:
            modeloptions = [
                ["encode", True, 200, "OK"],
                ["summary", True, 200, "OK"],
                ["encode", False, 200, "OK"],
                ["summary", False, 200, "OK"],
            ]
            model = out[0][0]
            hurl = model["href"][len(self.PARAMS["hostname"]) :]
            out = makeRequest(self, hurl, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], 200, msg=f"Failed to GET on {hurl}. Output: {out}")
            self.assertEqual(out[2], "OK", msg=f"Failed to GET on {hurl}. Output: {out}")
            for option in modeloptions:
                tmpurl = hurl + f"?{option[0]}={option[1]}"
                out = makeRequest(self, tmpurl, {"verb": "GET", "data": {}})
                self.assertEqual(out[1], option[2], msg=f"Failed to GET on {tmpurl}. Output: {out}")
                self.assertEqual(out[2], option[3], msg=f"Failed to GET on {tmpurl}. Output: {out}")

    def test_deltas(self):
        """Test deltas"""
        options = [
            ["summary", True, 200, "OK"],
            ["oldview", True, 200, "OK"],
            ["encode", True, 200, "OK"],
            ["model", "turtle", 200, "OK"],
            ["model", "json-ld", 200, "OK"],
            ["model", "ntriples", 200, "OK"],
            ["summary", False, 200, "OK"],
            ["oldview", False, 200, "OK"],
            ["encode", False, 200, "OK"],
            ["model", "dummyRandom", 400, "Bad Request"],
        ]
        url = f"/api/{self.PARAMS['sitename']}/deltas"
        for option in options:
            tmpurl = url + f"?{option[0]}={option[1]}"
            out = makeRequest(self, tmpurl, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], option[2], msg=f"Failed to GET on {tmpurl}. Output: {out}")
            self.assertEqual(out[2], option[3], msg=f"Failed to GET on {tmpurl}. Output: {out}")
        out = makeRequest(self, url, {"verb": "GET", "data": {}})
        self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
        self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
        if len(out) >= 1 and len(out[0]) >= 1:
            delta = out[0][0]
            # Delta states
            url = f"/api/{self.PARAMS['sitename']}/deltas/{delta['id']}/"
            out = makeRequest(self, url, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], 200, msg=f"Failed to GET on {url}. Output: {out}")
            self.assertEqual(out[2], "OK", msg=f"Failed to GET on {url}. Output: {out}")
            # Delta via href
            hurl = delta["href"][len(self.PARAMS["hostname"]) :]
            out = makeRequest(self, hurl, {"verb": "GET", "data": {}})
            self.assertEqual(out[1], 200, msg=f"Failed to GET on {hurl}. Output: {out}")
            self.assertEqual(out[2], "OK", msg=f"Failed to GET on {hurl}. Output: {out}")
            for option in options:
                tmpurl = hurl + f"?{option[0]}={option[1]}"
                out = makeRequest(self, tmpurl, {"verb": "GET", "data": {}})
                self.assertEqual(out[1], option[2], msg=f"Failed to GET on {tmpurl}. Output: {out}")
                self.assertEqual(out[2], option[3], msg=f"Failed to GET on {tmpurl}. Output: {out}")


if __name__ == "__main__":
    conf = {}
    if not os.path.isfile("test-config.yaml"):
        raise Exception("Configuration file not available for unit test")
    with open("test-config.yaml", "r", encoding="utf-8") as fd:
        conf = yaml.safe_load(fd)
    TestUtils.PARAMS = conf
    unittest.main()
