#!/usr/bin/env python3
"""
Setup tools script for SiteRM Site Agent.
Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/05/20
"""
from setuptools import setup
from setupUtilities import list_packages, get_py_modules, VERSION

setup(
    name='DTNRMAgent',
    version="%s" % VERSION,
    long_description="DTN-RM Agent installation",
    author="Justas Balcas",
    author_email="justas.balcas@cern.ch",
    url="https://hep.caltech.edu",
    download_url="https://github.com/sdn-sense/siterm",
    keywords=['DTN-RM', 'system', 'monitor', 'SDN', 'end-to-end'],
    package_dir={'': 'src/python/'},
    packages=['DTNRMAgent', 'DTNRMLibs'] + list_packages(['src/python/DTNRMAgent/', 'src/python/DTNRMLibs/']),
    install_requires=[],
    data_files=[("/etc/cron.d/", ["packaging/general/siterm-crons"]),
                ("/etc/cron-scripts/", ["packaging/general/siterm-ca-cron.sh"])],
    py_modules=get_py_modules(['src/python/DTNRMAgent', 'src/python/DTNRMLibs']),
    scripts=["packaging/dtnrm-site-agent/scripts/dtnrmagent-update",
             "packaging/dtnrm-site-agent/scripts/dtnrm-ruler",
             "packaging/dtnrm-site-agent/scripts/dtnrm-debugger",
             "packaging/general/Config-Fetcher"]
)
