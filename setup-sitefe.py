#!/usr/bin/env python3
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
import sys
from setuptools import setup
from setupUtilities import list_packages, get_py_modules, get_web_files, VERSION

# Cronjobs which are running also have to be prepared with correct timing.
# Also another cronjob, which monitors config file and modifies cronjobs if needed.
# Currently it is allowed to specify only minutes and up to 30 minutes.
# This is how CRONJOBS are handled and division is done only for the current hour.
SCRIPTS = []
for sectionName in ['LookUpService', 'PolicyService', 'ProvisioningService']:
    SCRIPTS.append('packaging/dtnrm-site-fe/scripts/%s-update' % sectionName)

setup(
    name='DTNRMSiteFE',
    version="%s" % VERSION,
    long_description="End Site-RM Site installation",
    author="Justas Balcas",
    author_email="juztas@gmail.com",
    download_url="https://github.com/sdn-sense/siterm/tarball/0.1",
    keywords=['End Site-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
    package_dir={'': 'src/python/'},
    packages=['SiteFE', 'DTNRMLibs'] + list_packages(['src/python/SiteFE/', 'src/python/DTNRMLibs/']),
    install_requires=['pyparsing', "rdflib;python_version<'3.7'", 'importlib', 'setuptools', 'future', 'simplejson', 'mod-wsgi',
                      'prometheus-client', 'python-dateutil', 'pyaml', 'requests', 'pycurl', 'pyOpenSSL',
                      'mariadb==1.0.8', 'cryptography==3.2.1', 'wheel', 'paramiko', 'ansible_runner', 'psutil', 'typing-extensions==4.1.1'],
    data_files=[("/var/www/wsgi-scripts/", ["packaging/dtnrm-site-fe/sitefe.wsgi"]),
                ("/etc/httpd/conf.d/", ["packaging/dtnrm-site-fe/sitefe-httpd.conf",
                                        "packaging/dtnrm-site-fe/welcome.conf"]),
                ("/etc/cron.d/", ["packaging/dtnrm-site-fe/siterm-crons"]),
                ("/etc/cron-scripts/", ["packaging/general/siterm-ca-cron.sh"])] + get_web_files(),
    py_modules=get_py_modules(['src/python/SiteFE/', 'src/python/DTNRMLibs']),
    scripts=SCRIPTS
)
