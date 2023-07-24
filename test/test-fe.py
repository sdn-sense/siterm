"""Test Frontend"""
import os
import unittest
import pathlib
import http.client
import simplejson as json
import yaml
from SiteRMLibs.HTTPLibrary import Requests
from SiteRMLibs.MainUtilities import getUTCnow


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

    @classmethod
    def setUpClass(cls):
        """Set Up Class. Set CERT/KEY env params"""
        os.environ["X509_USER_KEY"] = cls.PARAMS['key']
        os.environ["X509_USER_CERT"] = cls.PARAMS['cert']

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
        data = {"type": "rapidping", "sitename": "", "hostname": "dummyhostname", "ip": "1.2.3.4",
                "packetsize": "32", "interval": "1", "interface": "dummyinterface", "time": "60"}
        outsuc = {"out": ["ping success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_arptable(self):
        """Test Debug arptable API"""
        data = {"type": "arptable", "sitename": "", "hostname": "dummyhostname", "interface": "dummyinterface"}
        outsuc = {"out": ["arp success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_tcpdump(self):
        """Test Debug TCPDump API"""
        data = {"type": "tcpdump", "sitename": "", "hostname": "dummyhostname", "interface": "dummyinterface"}
        outsuc = {"out": ["tcpdump success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_iperf(self):
        """Test Debug Iperf API"""
        data = {"type": "iperf", "sitename": "", "hostname": "dummyhostname",
                "interface": "dummyinterface", "ip": "1.2.3.4", "port": "1234", "time": "60"}
        outsuc = {"out": ["iperf success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_iperfserver(self):
        """Test Debug IperfServer API"""
        data = {"type": "iperfserver", "sitename": "", "hostname": "dummyhostname", "onetime": "True",
                "interface": "dummyinterface", "ip": "1.2.3.4", "port": "1234", "time": "60"}
        outsuc = {"out": ["iperf server success", "from unittest"], "err": "", "exitCode": 0}
        dataupd = {'state': 'success', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

    def test_debug_prometheus_push(self):
        """Test Prometheus Push Debug API"""
        data = {'hostname': 'dummyhostname',  # hostname
                'hosttype': 'host',  # switch or host
                'type': 'arp-push',  # type of action (prometheus-push - for switch/host, arp-push - for host)
                'metadata': {'key': 'value'},  # Only supported for switch hosttype, Optional
                'gateway': 'gateway-url',  # gateway url
                'runtime': str(int(getUTCnow())+1200),  # runtime until time in seconds since the epoch
                'resolution': '5'}  # resolution time
                #'mibs': "list of mibs separated by comma"} # Optional parameter
        outsuc = {"out": ["running"], "err": "", "exitCode": 0}
        dataupd = {'state': 'active', 'output': json.dumps(outsuc)}
        debugActions(self, data, dataupd)

        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getalldebughostnameactive/dummyhostname"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

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

    def test_getactivedeltas(self):
        """Test getactivedeltas"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getactivedeltas"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

    def test_getswitchdata(self):
        """Test getswitchdata"""
        url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getswitchdata"
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')

    def test_getmodels(self):
        """Test models"""
        options = [['summary', True, 200, "OK"], ['current', True, 200, "OK"],
                   ['oldview', True, 200, "OK"], ['encode', True, 200, "OK"],
                   ['model', 'turtle', 200, "OK"], ['summary', False, 200, "OK"],
                   ['current', False, 200, "OK"], ['oldview', False, 200, "OK"],
                   ['encode', False, 200, "OK"], ['model', 'dummyRandom', 400, "Bad Request"]]
        url = f"/{self.PARAMS['sitename']}/sitefe/v1/models"
        for option in options:
            tmpurl = url + f"?{option[0]}={option[1]}"
            out = makeRequest(self, tmpurl, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], option[2])
            self.assertEqual(out[2], option[3])
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        if len(out) >= 1:
            modeloptions = [['encode', True, 200, "OK"], ['summary', True, 200, "OK"],
                            ['encode', False, 200, "OK"], ['summary', False, 200, "OK"]]
            model = out[0][0]
            hurl = model['href'][len(self.PARAMS['hostname']):]
            out = makeRequest(self, hurl, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], 200)
            self.assertEqual(out[2], 'OK')
            for option in modeloptions:
                tmpurl = hurl + f"?{option[0]}={option[1]}"
                out = makeRequest(self, tmpurl, {'verb': 'GET', 'data': {}})
                self.assertEqual(out[1], option[2])
                self.assertEqual(out[2], option[3])

    def test_deltas(self):
        """Test deltas"""
        options = [['summary', True, 200, "OK"], ['oldview', True, 200, "OK"],
                   ['encode', True, 200, "OK"], ['model', 'turtle', 200, "OK"],
                   ['summary', False, 200, "OK"], ['oldview', False, 200, "OK"],
                   ['encode', False, 200, "OK"], ['model', 'dummyRandom', 400, "Bad Request"]]
        url = f"/{self.PARAMS['sitename']}/sitefe/v1/deltas"
        for option in options:
            tmpurl = url + f"?{option[0]}={option[1]}"
            out = makeRequest(self, tmpurl, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], option[2])
            self.assertEqual(out[2], option[3])
        out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
        self.assertEqual(out[1], 200)
        self.assertEqual(out[2], 'OK')
        if len(out) >= 1 and len(out[0]) >= 1:
            delta = out[0][0]
            # Delta states
            url = f"/{self.PARAMS['sitename']}/sitefe/v1/deltastates/{delta['id']}/"
            out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], 200)
            self.assertEqual(out[2], 'OK')
            # Delta via href
            hurl = delta['href'][len(self.PARAMS['hostname']):]
            out = makeRequest(self, hurl, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], 200)
            self.assertEqual(out[2], 'OK')
            for option in options:
                tmpurl = hurl + f"?{option[0]}={option[1]}"
                out = makeRequest(self, tmpurl, {'verb': 'GET', 'data': {}})
                self.assertEqual(out[1], option[2])
                self.assertEqual(out[2], option[3])

# TODO: Test Full cycle: Submit good delta, Check that delta becomes active
#                        Check that it get's added to model
#                        Cancel delta and check that delta becomes active
#                        And it get's removed from the model

if __name__ == '__main__':
    conf = {}
    if not os.path.isfile('test-config.yaml'):
        raise Exception('Configuration file not available for unit test')
    with open('test-config.yaml', 'r', encoding='utf-8') as fd:
        conf = yaml.safe_load(fd)
    TestUtils.PARAMS = conf
    unittest.main()
