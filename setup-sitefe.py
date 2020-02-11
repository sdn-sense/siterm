#!/usr/bin/python
"""
Setup tools script for DTN-RM Site Frontend.
To Install:
    python setup-site-fe.py build install --force
Copyright 2017 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title             : dtnrm
Author            : Justas Balcas
Email             : justas.balcas (at) cern.ch
@Copyright        : Copyright (C) 2016 California Institute of Technology
Date            : 2017/09/26
"""
import os
import os.path
import sys
from shutil import move
from setuptools import setup
from setupUtilities import list_packages, get_py_modules, getConfig, createDirs, readFile
from setupUtilities import createAllDirsFromConfig

CONFIG = None
CONFIG_LOCATION = []
for configName in ['dtnrm-site-fe.conf', 'dtnrm-auth.conf']:
    if os.path.isfile('/etc/%s' % configName):
        CONFIG_LOCATION.append('/etc/%s' % configName)
    else:
       CONFIG_LOCATION.append('packaging/dtnrm-site-fe/%s' % configName)
CONFIG = getConfig(CONFIG_LOCATION)
MAINDIR = CONFIG.get('general', 'privatedir')
createAllDirsFromConfig(CONFIG, MAINDIR)
RAWCONFIGS = "%s/%s/" % (MAINDIR, "rawConfigs")
createDirs(RAWCONFIGS)
# Cronjobs which are running also have to be prepared with correct timing.
# Also another cronjob, which monitors config file and modifies cronjobs if needed.
# Currently it is allowed to specify only minutes and up to 30 minutes.
# This is how CRONJOBS are handled and division is done only for the current hour.
SCRIPTS = ['packaging/dtnrm-site-fe/centos7/ContinuousLoop-update']
for sectionName in CONFIG.sections():
    print sectionName
    if sectionName in ['LookUpService', 'PolicyService', 'ProvisioningService']:
        SCRIPTS.append('packaging/dtnrm-site-fe/centos7/%s-update' % sectionName)

#  This is bare metal instalation which means config files should be added,
#  while it is not done for docker as they are on HOST os.
if "--docker" not in sys.argv:
    setup(
        name='DTNRMSiteFE',
        version="0.1",
        long_description="DTN-RM Site installation",
        author="Justas Balcas",
        author_email="justas.balcas@cern.ch",
        url="http://hep.caltech.edu",
        download_url="https://github.com/juztas/dtnrm/tarball/0.1",
        keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
        package_dir={'': 'src/python/'},
        packages=['SiteFE'] + list_packages(['src/python/SiteFE/']),
        install_requires=['rdflib==4.2.2', 'importlib==1.0.4', 'setuptools==39.1.0', 'python-dateutil==2.7.5'],
        data_files=[("/etc/", CONFIG_LOCATION),
                    (RAWCONFIGS, ["packaging/dtnrm-site-fe/sitefe-httpd.conf"]),
                    ("/var/www/wsgi-scripts/", ["packaging/dtnrm-site-fe/sitefe.wsgi"]),
                    ("/etc/httpd/conf.d/", ["packaging/dtnrm-site-fe/sitefe-httpd.conf",
                                            "packaging/dtnrm-site-fe/welcome.conf"])],
        py_modules=get_py_modules(['src/python/SiteFE/', 'src/python/DTNRMLibs']),
        scripts=SCRIPTS
    )
else:
    sys.argv.remove("--docker")
    setup(
        name='DTNRMSiteFE',
        version="0.1",
        long_description="DTN-RM Site installation",
        author="Justas Balcas",
        author_email="justas.balcas@cern.ch",
        url="http://hep.caltech.edu",
        download_url="https://github.com/juztas/dtnrm/tarball/0.1",
        keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
        package_dir={'': 'src/python/'},
        packages=['SiteFE'] + list_packages(['src/python/SiteFE/']),
        install_requires=['rdflib==4.2.2', 'importlib==1.0.4', 'setuptools==39.1.0', 'python-dateutil==2.7.5'],
        data_files=[("/var/www/wsgi-scripts/", ["packaging/dtnrm-site-fe/sitefe.wsgi"])],
        py_modules=get_py_modules(['src/python/SiteFE/', 'src/python/DTNRMLibs']),
        scripts=SCRIPTS
    )
