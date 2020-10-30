#!/usr/bin/python
"""
Chown database file automatically. This is needed because we do
our new site deployments automatically via git configurations.
Copyright 2020 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title             : siterm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2020 California Institute of Technology
Date            : 2020/09/29
"""
import os
import sys
import pprint
import subprocess
from DTNRMLibs.MainUtilities import getGitConfig


def callCommand(command):
    """ Call *nix command """
    cmdCall = subprocess.Popen(command, shell=True)
    cmdCall.communicate()


def getLatestVersion():
    """ Get Latest version name from Github repo """
    callCommand("cd /opt/dtnrmcode/siterm/ && git pull")
    sys.path.append('/opt/dtnrmcode/siterm/')
    import setupUtilities
    return setupUtilities.VERSION


def agentUpdater():
    """ Update Agent. Restarts all services """
    import DTNRMAgent
    installedVersion = DTNRMAgent.__version__
    latestVersion = getLatestVersion()
    if installedVersion != latestVersion:
        print 'Installed version: %s. Latest Version %s' % (installedVersion, latestVersion)
        # Stop all services
        for service in ['dtnrmagent-update', 'dtnrm-ruler']:
            print 'Stop %s' % service
            callCommand('%s stop' % service)
        # Install new code;
        callCommand('cd /opt/dtnrmcode/siterm/ && python setup-agent.py install')
        # Run update script if any
        if os.path.isfile('/opt/dtnrmcode/siterm/update/agent-%s.py' % latestVersion):
            callCommand('python /opt/dtnrmcode/siterm/update/agent-%s.py' % latestVersion)
        # Start all services
        for service in ['dtnrmagent-update', 'dtnrm-ruler']:
            print 'Stop %s' % service
            callCommand('%s start' % service)
        # Update crontab entries
        callCommand("crontab /etc/cron.d/siterm-crons")


def feUpdater():
    """ Frontend Update. Restarts all services """
    import SiteFE
    installedVersion = SiteFE.__version__
    latestVersion = getLatestVersion()
    if installedVersion != latestVersion:
        print 'Installed version: %s. Latest Version %s' % (installedVersion, latestVersion)
        # Stop all services
        for service in ['/usr/sbin/httpd -k', 'LookUpService-update',
                        'PolicyService-update', 'ProvisioningService-update']:
            print 'Stop %s' % service
            callCommand('%s stop' % service)
        # Install new code;
        callCommand('cd /opt/dtnrmcode/siterm/ && python setup-sitefe.py install')
        # Run update script if any
        if os.path.isfile('/opt/dtnrmcode/siterm/update/fe-%s.py' % latestVersion):
            callCommand('python /opt/dtnrmcode/siterm/update/fe-%s.py' % latestVersion)
        # Start all services
        for service in ['/usr/sbin/httpd -k', 'LookUpService-update',
                        'PolicyService-update', 'ProvisioningService-update']:
            print 'Stop %s' % service
            callCommand('%s start' % service)
        # Update crontab entries
        callCommand("crontab /etc/cron.d/siterm-crons")


def checkAutoUpdate(config):
    """ Check if auto update is enabled in configuration """
    autoupdate = True
    if 'autoupdate' in config['MAIN']['general'].keys():
        autoupdate = bool(config['MAIN']['general']['autoupdate'])
    if not autoupdate:
        print 'Auto Update disabled in configuration. Skipping auto update'
        return
    if config['MAPPING']['type'] == 'Agent':
        agentUpdater()
    elif config['MAPPING']['type'] == 'FE':
        feUpdater()
    else:
        print 'Unknown TYPE. Ignoring Auto Update.'


if __name__ == '__main__':
    CONFIG = getGitConfig()
    pprint.pprint(CONFIG)
    checkAutoUpdate(CONFIG)
