"""Test Debug Prometheus Push"""
import os
import unittest
import http.client
import simplejson as json
import yaml
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

class TestUtils(unittest.TestCase):
    """UnitTest"""
    PARAMS = {}

    @classmethod
    def setUpClass(cls):
        """Set Up Class. Set CERT/KEY env params"""
        os.environ["X509_USER_KEY"] = cls.PARAMS['key']
        os.environ["X509_USER_CERT"] = cls.PARAMS['cert']

    def test_debug_prometheus_push(self):
        """Test Prometheus Push Debug API"""
        for data in [{'hostname': 'sdn-dtn-1-7.ultralight.org', 'hosttype': 'host',
                      'type': 'prometheus-push', 'metadata': {'instance': 'sdn-dtn-1-7.ultralight.org',
                                                              'sense_mon_id': 'rtmon-1'},
                      'gateway': 'dev2.virnao.com:9091', 'runtime': str(int(getUTCnow())+610),
                      'resolution': '5'},
                     {'hostname': 'sdn-dtn-1-7.ultralight.org', 'hosttype': 'host',
                      'type': 'arp-push', 'metadata': {'instance': 'sdn-dtn-1-7.ultralight.org',
                                                       'sense_mon_id': 'rtmon-1'},
                      'gateway': 'dev2.virnao.com:9091', 'runtime': str(int(getUTCnow())+610),
                      'resolution': '5'},
                     {'hostname': 'dellos9_s0', 'hosttype': 'host',
                      'type': 'prometheus-push', 'metadata': {'instance': 'dellos9_s0', 'sense_mon_id': 'rtmon-1'},
                      'gateway': 'dev2.virnao.com:9091', 'runtime': str(int(getUTCnow())+610),
                      'resolution': '5'}]:
            outsuc = {"out": ["running"], "err": "", "exitCode": 0}
            dataupd = {'state': 'active', 'output': json.dumps(outsuc)}
            debugActions(self, data, dataupd)

            url = f"/{self.PARAMS['sitename']}/sitefe/json/frontend/getalldebughostnameactive/dummyhostname"
            out = makeRequest(self, url, {'verb': 'GET', 'data': {}})
            self.assertEqual(out[1], 200)
            self.assertEqual(out[2], 'OK')


if __name__ == '__main__':
    conf = {}
    if not os.path.isfile('test-config.yaml'):
        raise Exception('Configuration file not available for unit test')
    with open('test-config.yaml', 'r', encoding='utf-8') as fd:
        conf = yaml.safe_load(fd)
    TestUtils.PARAMS = conf
    unittest.main()
