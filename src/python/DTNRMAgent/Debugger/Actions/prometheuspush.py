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
            {'hostname': 'dummyhostname', # hostname
             'hosttype': 'switch', # switch or hostname
             'type': 'prometheus-push', # type of action
             'metadata': {'key': 'value'}, # Only supported for switch hosttype, Optional
             'gateway': 'gateway-url', # gateway url
             'runtime': '60', # runtime since epoch
             'resolution': '5'}} # resolution time
    print(prometheuspush(data))
