"""Test Frontend"""
import os
import json
import unittest
import pathlib
import http.client
from DTNRMLibs.HTTPLibrary import Requests
from DTNRMLibs.MainUtilities import getUTCnow


def makeRequest(cls, url, params):
    """Make HTTP Request"""
    req = Requests(cls.PARAMS['hostname'], {})
    try:
        out = req.makeRequest(url, **params)
    except http.client.HTTPException as ex:
        return ex.result, ex.status, ex.reason, ex
    return out


def debugActions(cls, dataIn, dataUpd):
    """Test Debug Actions: submit, get update"""
    # SUBMIT
    urls = f"/{cls.PARAMS['sitename']}/sitefe/json/frontend/submitdebug/NEW"
    outs = makeRequest(cls, urls, {'verb': 'POST', 'data': dataIn})
    cls.assertEqual(outs[1], 200)
    cls.assertEqual(outs[2], 'OK')
    # GET
    urlg = f"/{cls.PARAMS['sitename']}/sitefe/json/frontend/getdebug/{outs[0]['ID']}"
    outg = makeRequest(cls, urlg, {'verb': 'GET', 'data': {}})
    cls.assertEqual(outg[1], 200)
    cls.assertEqual(outg[2], 'OK')
    # UPDATE
    urlu = f"/{cls.PARAMS['sitename']}/sitefe/json/frontend/updatedebug/{outs[0]['ID']}"
    outu = makeRequest(cls, urlu, {'verb': 'PUT', 'data': dataUpd})
    cls.assertEqual(outu[1], 200)
    cls.assertEqual(outu[2], 'OK')


class TestUtils(unittest.TestCase):
    """UnitTest"""
    PARAMS = {}

    def test_fake_url(self):
        """Test Fake Url"""
        url = "/NoSite/sitefe/no/url/"
        for action in ["GET", "POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {'verb': action, 'data': {}})
            self.assertIn(out[1], [404, 405])

    def test_config(self):
        """Test to get Config"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/configuration"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {'verb': action, 'data': {}})
            self.assertEqual(out[1], 405)

    def test_metrics(self):
        """Test metrics API"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/metrics"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {'verb': action, 'data': {}})
            self.assertEqual(out[1], 405)
            self.assertEqual(out[2], 'Method Not Allowed')

    def test_getdebug(self):
        """Test getdebug API"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getdebug/dummyhostname"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {'verb': action, 'data': {}})
            self.assertIn(out[1], [400, 405])
            self.assertIn(out[2], ['Bad Request', 'Method Not Allowed'])

    def test_getalldebughostname(self):
        """Test getalldebughostname API"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getalldebughostname/dummyhostname"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        for action in ["POST", "PUT", "DELETE"]:
            out = makeRequest(self, url, {'verb': action, 'data': {}})
            self.assertIn(out[1], [400, 405])
            self.assertIn(out[2], ['Bad Request', 'Method Not Allowed'])

    def test_debug_ping(self):
        """Test Debug ping API"""
        # rapidping, tcpdump, arptable, iperf, iperfserver
        data = {"type": "rapidping", "sitename": "", "dtn": "dummyhostname", "ip": "1.2.3.4",
                "packetsize": "32", "interval": "1", "interface": "dummyinterface", "time": "60"}
        outsuc = {"out": ["ping success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_arptable(self):
        """Test Debug arptable API"""
        data = {"type": "arptable", "sitename": "", "dtn": "dummyhostname", "interface": "dummyinterface"}
        outsuc = {"out": ["arp success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_tcpdump(self):
        """Test Debug TCPDump API"""
        data = {"type": "tcpdump", "sitename": "", "dtn": "dummyhostname", "interface": "dummyinterface"}
        outsuc = {"out": ["tcpdump success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_iperf(self):
        """Test Debug Iperf API"""
        data = {"type": "iperf", "sitename": "", "dtn": "dummyhostname",
                "interface": "dummyinterface", "ip": "1.2.3.4", "port": "1234", "time": "60"}
        outsuc = {"out": ["iperf success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_iperfserver(self):
        """Test Debug IperfServer API"""
        data = {"type": "iperfserver", "sitename": "", "dtn": "dummyhostname",
                "interface": "dummyinterface", "ip": "1.2.3.4", "port": "1234", "time": "60"}
        outsuc = {"out": ["iperf server success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
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
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/configuration"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        os.environ["X509_USER_KEY"] = x509_key
        os.environ["X509_USER_CERT"] = x509_cert
        self.assertEqual(out[1], 401)
        self.assertEqual(out[2], 'Unauthorized')

    def test_getdata(self):
        """Test to get agentdata"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getdata"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

    def test_addhost(self):
        """Test to addhost"""
        dic = {'hostname': 'unittest', 'ip': '1.2.3.4',
               'insertTime': getUTCnow(), 'updateTime': getUTCnow(),
               'NetInfo': {'unittest': 'randomvalue'}}
        # Add Host
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/addhost"
        out = makeRequest(self, url, {'verb': 'PUT', 'data': dic})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        # Delete Host
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/deletehost"
        out = makeRequest(self, url, {'verb': 'PUT', 'data': dic})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

    def test_updatehost(self):
        """Test updatehost"""
        dic = {'hostname': 'unittest', 'ip': '1.2.3.4',
               'insertTime': getUTCnow(), 'updateTime': getUTCnow(),
               'NetInfo': {'unittest': 'randomvalue'}}
        # Add Host
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/addhost"
        out = makeRequest(self, url, {'verb': 'PUT', 'data': dic})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        # Update Host
        dic['NetInfo'] = {'updateunittest': 'updaterandomvalue'}
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/updatehost"
        out = makeRequest(self, url, {'verb': 'PUT', 'data': dic})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        # Get Host
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getdata"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        # Delete Host
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/deletehost"
        out = makeRequest(self, url, {'verb': 'PUT', 'data': dic})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

# "%(sitename)/sitefe/json/frontend/servicestate" PUT
# TODO Write Unit tests for get deltas, submit delta, check model.
# _DELTAS_RE = re.compile(r'^/*v1/deltas/?$')
#          (_DELTAS_RE, deltas, ['GET', 'POST'], [{"key": "summary", "default": True, "type": bool},
#                                                 {"key": "oldview", "default": False, "type": bool},
#                                                 {"key": "encode", "default": True, "type": bool},
#                                                 {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}], []),
#          
# _DELTA_STATES_RE = re.compile(r'^/*v1/deltastates/([-_A-Za-z0-9]+)/?$')
#            (_DELTA_STATES_RE, delta_states, ['GET'], [], []),]
# _DELTAS_ID_RE = re.compile(r'^/*v1/deltas/([-_A-Za-z0-9]+)/?$')
#          (_DELTAS_ID_RE, deltas_id, ['GET', 'DELETE'], [{"key": "model", "default": "turtle", "type": str, "options": ['turtle']},
#                                                         {"key": "encode", "default": True, "type": bool},
#                                                         {"key": "oldview", "default": False, "type": bool},
#                                                         {"key": "summary", "default": False, "type": bool}], []),
# _DELTAS_ID_ACTION_RE = re.compile(r'^/*v1/deltas/([-_A-Za-z0-9]+)/actions/commit/?$')
#          (_DELTAS_ID_ACTION_RE, deltas_action, ['PUT', 'GET'], [], []),
# _MODELS_RE = re.compile(r'^/*v1/models/?$')
#          (_MODELS_RE, models, ['GET'], [{"key": "current", "default": False, "type": bool},
#                                         {"key": "summary", "default": True, "type": bool},
#                                         {"key": "oldview", "default": False, "type": bool},
#                                         {"key": "encode", "default": True, "type": bool},
#                                         {"key": "model", "default": "turtle", "type": str, "options": ['turtle']}], []),
# _MODELS_ID_RE = re.compile(r'^/*v1/models/([-_A-Za-z0-9]+)/?$')
# [(_MODELS_ID_RE, models_id, ['GET'], [{"key": "encode", "default": False, "type": bool},
#                                               {"key": "summary", "default": False, "type": bool}], []),
# _ACTIVE_DELTAS = re.compile(r'^/*v1/activedeltas/?$')
#          (_ACTIVE_DELTAS, active_deltas, ['GET'], [], []),

if __name__ == '__main__':
    TestUtils.PARAMS = {'hostname': "https://sdn-login-1.ultralight.org:8443", 'sitename': 'T2_US_Caltech_Test'}
    unittest.main()
