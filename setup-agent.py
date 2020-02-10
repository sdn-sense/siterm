#!/usr/bin/python
"""
Setup tools script for DTN-RM Site Agent.
To Install:
    python setup-agent.py build install --force
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
import sys
from setuptools import setup
from setupUtilities import list_packages, get_py_modules
from setupUtilities import getConfig, createDirs
from setupUtilities import createAllDirsFromConfig

BASEPATH = '/etc/'
if "--user" in sys.argv:
    BASEPATH = 'etc/'

CONFIG = None
CONFIG_LOCATION = []
if os.path.isfile('/etc/dtnrm/main.conf'):
    CONFIG_LOCATION.append('/etc/dtnrm/main.conf')
else:
    CONFIG_LOCATION.append('packaging/dtnrm-site-agent/main.conf')

CONFIG = getConfig(CONFIG_LOCATION)
MAINDIR = CONFIG.get('general', 'private_dir')
createAllDirsFromConfig(CONFIG, MAINDIR)
RAWCONFIGS = "%s/%s/" % (MAINDIR, "rawConfigs")
createDirs(RAWCONFIGS)

setup(
    name='DTNRMAgent',
    version="0.1",
    long_description="DTN-RM Agent installation",
    author="Justas Balcas",
    author_email="justas.balcas@cern.ch",
    url="http://hep.caltech.edu",
    download_url="https://github.com/sdn-sense/siterm",
    keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
    package_dir={'': 'src/python/'},
    packages=['DTNRMAgent'] + list_packages(['src/python/DTNRMAgent/']),
    install_requires=['importlib==1.0.4', 'psutil==5.2.2', 'potsdb', 'ipaddress', 'pyroute2'],
    data_files=[("%s/dtnrm/" % BASEPATH, CONFIG_LOCATION)],
    py_modules=get_py_modules(['src/python/DTNRMAgent']),
    scripts=["packaging/dtnrm-site-agent/dtnrmagent-update", "packaging/dtnrm-site-agent/dtnrm-ruler"]
)
