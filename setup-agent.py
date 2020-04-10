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
import sys
from setuptools import setup
from setupUtilities import list_packages, get_py_modules

if "--docker" not in sys.argv:
    setup(
        name='DTNRMAgent',
        version="0.1",
        long_description="DTN-RM Agent installation",
        author="Justas Balcas",
        author_email="justas.balcas@cern.ch",
        url="https://hep.caltech.edu",
        download_url="https://github.com/sdn-sense/siterm",
        keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
        package_dir={'': 'src/python/'},
        packages=['DTNRMAgent', 'DTNRMLibs'] + list_packages(['src/python/DTNRMAgent/', 'src/python/DTNRMLibs/']),
        install_requires=['importlib==1.0.4', 'psutil==5.2.2', 'potsdb', 'ipaddress', 'pyroute2', 'pyaml', 'requests'],
        py_modules=get_py_modules(['src/python/DTNRMAgent', 'src/python/DTNRMLibs']),
        scripts=["packaging/dtnrm-site-agent/dtnrmagent-update", "packaging/dtnrm-site-agent/dtnrm-ruler"]
    )
else:
    sys.argv.remove("--docker")
    setup(
        name='DTNRMAgent',
        version="0.1",
        long_description="DTN-RM Agent installation",
        author="Justas Balcas",
        author_email="justas.balcas@cern.ch",
        url="https://hep.caltech.edu",
        download_url="https://github.com/sdn-sense/siterm",
        keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
        package_dir={'': 'src/python/'},
        packages=['DTNRMAgent', 'DTNRMLibs'] + list_packages(['src/python/DTNRMAgent/', 'src/python/DTNRMLibs/']),
        install_requires=['importlib==1.0.4', 'psutil==5.2.2', 'potsdb', 'ipaddress', 'pyroute2', 'pyyaml', 'requests'],
        py_modules=get_py_modules(['src/python/DTNRMAgent', 'src/python/DTNRMLibs']),
        scripts=["packaging/dtnrm-site-agent/dtnrmagent-update", "packaging/dtnrm-site-agent/dtnrm-ruler"]
    )
