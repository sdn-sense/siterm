#!/usr/bin/env python3
"""
SENSE Ansible test runner

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/04/14

TODO:
    1. Log to file
    2. Log all ansible events
    3. Allow to test vlan and IP assignment

"""
import pprint
import ansible_runner

def runAnsible(playbookFile):
    """Run Ansible Playbook"""
    ansRunner = ansible_runner.run(private_data_dir='/etc/ansible/sense/',
                                   inventory='/etc/ansible/sense/inventory/inventory.yaml',
                                   playbook=playbookFile)
    return ansRunner


playbooks = ['getfacts.yaml', 'maclldproute.yaml', 'applyconfig.yaml']
for playbook in playbooks:
    print("RUNNING PLAYBOOK: %s" % playbook)
    r = runAnsible(playbook)
    for host, _ in r.stats['failures'].items():
        for host_events in r.host_events(host):
            if host_events['event'] != 'runner_on_failed':
                continue
            pprint.pprint(host_events)
    for host, _ in r.stats['ok'].items():
        print("HOSTNAME: %s" % host)
        print('-'*100)
        for host_events in r.host_events(host):
            if host_events['event'] != 'runner_on_ok':
                continue
            if 'stdout_lines' in host_events['event_data']['res']:
                for line in host_events['event_data']['res']['stdout_lines']:
                    print(line)
            elif 'ansible_facts' in host_events['event_data']['res'] and  \
                 'ansible_net_interfaces' in host_events['event_data']['res']['ansible_facts']:
                action = host_events['event_data']['task_action']
                pprint.pprint(host_events['event_data']['res']['ansible_facts'])
            else:
                pprint.pprint(host_events)
        print('-'*100)
