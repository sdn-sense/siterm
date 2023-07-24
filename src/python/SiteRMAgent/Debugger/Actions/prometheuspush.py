#!/usr/bin/env python3
"""
    Push local prometheus stats to a remote gateway.

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2023/03/17
"""
from SiteRMLibs.PromPush import PromPushService


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
    print(prometheuspush(data))
