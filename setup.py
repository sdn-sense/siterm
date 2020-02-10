#!/usr/bin/python
"""
Setup tools script for Site-RM Utilities. This is mandatory for Frontend
and the agents to have this installed.
To Install:
    python setup-agent.py build install

Copyright 2019 California Institute of Technology
   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at
       http://www.apache.org/licenses/LICENSE-2.0
   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.
Title 			: dtnrm
Author			: Justas Balcas
Email 			: justas.balcas (at) cern.ch
@Copyright		: Copyright (C) 2019 California Institute of Technology
Date			: 2019/05/26
"""
from setuptools import setup
from setupUtilities import list_packages, get_py_modules

setup(
    name='DTNRM-Utilities',
    version="0.1",
    long_description="DTN-RM Utilities Installation",
    author="Justas Balcas",
    author_email="justas.balcas@cern.ch",
    url="http://hep.caltech.edu",
    download_url="https://github.com/sdn-sense/dtnrm-utilities",
    keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
    install_requires=['pyOpenSSL==17.5.0'],
    package_dir={'': 'src/python/'},
    packages=['DTNRMLibs'] + list_packages(['src/python/DTNRMLibs/']),
    py_modules=get_py_modules(['src/python/DTNRMLibs']),
)
