This is the expected ansible output from any NOS. All starts from an empty dict. like `self.facts = {}`

 Interfaces required output:
```
        self.facts['interfaces'] = {}
```
And Inside Interfaces, parameters are:
```
                            'Vlan 67': {'bandwidth': 500000,
                                        'description': 'P2P LRT building SDN '
                                                       'testbed',
                                        'duplex': None,
                                        'ipv4': [{'address': '192.84.86.239',
                                                 'masklen': 31}],
                                        'ipv6': [{'address': '2605:d9c0:0:ff02::1',
                                                  'subnet': '2605:d9c0:0:ff02::/127'}],
                                        'lineprotocol': 'up',
                                        'macaddress': '4c:76:25:e8:44:c2',
                                        'mediatype': None,
                                        'mtu': 9416,
                                        'operstatus': 'up',
                                        'tagged': ['Port-channel_103'],
                                        'type': None},
                            'Port-channel 102': {'bandwidth': 200000,
                                                 'channel-member': ['hundredGigE_1-1',
                                                                    'hundredGigE_1-2'],
                                                 'description': None,
                                                 'duplex': None,
                                                 'ipv4': None,
                                                 'lineprotocol': 'up',
                                                 'macaddress': '4c:76:25:e8:44:c2,',
                                                 'mediatype': None,
                                                 'mtu': 9416,
                                                 'operstatus': 'up',
                                                 'type': None},
                            'fortyGigE 1/26/1': {'bandwidth': 40000,
                                                 'description': 'Dell S4810',
                                                 'duplex': None,
                                                 'ipv4': None,
                                                 'lineprotocol': 'up',
                                                 'macaddress': '4c:76:25:e8:44:c2',
                                                 'mediatype': '40GBASE-CR4',
                                                 'mtu': 9416,
                                                 'operstatus': 'up',
                                                 'type': 'DellEMCEth'},
```

Additional needed parameters:
```
+++++ {'ansible_command_info': {'mac': '4c:76:25:e8:44:c0'},
+++++  'ansible_command_ipv4': [{'from': '198.32.43.1', 'to': '0.0.0.0/0'},
                                {'from': '140.221.201.1',
                           'to': '140.221.250.106/32'}],
+++++  'ansible_command_ipv6': [{'from': '2605:d9c0:2:10::1', 'to': '::/0'}],
+++++ 'ansible_command_lldp': {'ManagementEthernet 1/1': {'local_port_id': 'ManagementEthernet 1/1',
                                                          'remote_chassis_id': '00:01:e8:96:1c:19',
                                                          'remote_port_id': 'GigabitEthernet 0/33',
                                                          'remote_system_name': 'LRT-R02-DELL-S60'},
```

Some other notes on requirements:
```
'ipv4', 'ipv6', 'mac', 'macaddress', 'lineprotocol', 'operstatus', 'mtu', 'bandwidth'
channel-member': ['hundredGigE_1-9', 'hundredGigE_1-13']

for lldp dict:
remote_port_id, remote_chassis_id

for routes:
from, to
intf, to
```
