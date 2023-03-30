#!/usr/bin/env python3
"""
    Push local prometheus stats to a remote gateway.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
from DTNRMLibs.PromPush import PromPushService


def prometheuspush(inputDict):
    """Run a prometheus push thread"""
    return PromPushService(inputDict)

if __name__ == "__main__":
    data = {'id': 1, 'requestdict':
            {'hostname': 'dummyhostname',
             'hosttype': 'switch',
             'type': 'prometheus-push',
             'metadata': {'key': 'value'},
             'gateway': 'gateway-url',
             'runtime': '60',
             'resolution': '5'}}
    data = {'id': 217, 'hostname': 'sdn-dtn-1-7.ultralight.org', 'state': 'active', 'requestdict': {'hostname': 'sdn-dtn-1-7.ultralight.org', 'hosttype': 'host', 'type': 'prometheus-push', 'metadata': {'instance': 'sdn-dtn-1-7.ultralight.org'}, 'gateway': 'dev2.virnao.com:9091', 'runtime': '1680204684', 'resolution': '5'}, 'output': '{"out": ["running"], "err": "", "exitCode": 0}', 'insertdate': 1680204074, 'updatedate': 1680204074}
    print(prometheuspush(data))
