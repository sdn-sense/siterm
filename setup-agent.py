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
    name='SiteRMAgent',
    version="%s" % VERSION,
    long_description="SiteRM Agent installation",
    author="Justas Balcas",
    author_email="juztas@gmail.com",
    url="https://sdn-sense.github.io",
    download_url=f"https://github.com/sdn-sense/siterm/archive/refs/tags/{VERSION}.tar.gz",
    keywords=['SiteRM', 'system', 'monitor', 'SDN', 'end-to-end'],
    package_dir={'': 'src/python/'},
    packages=['SiteRMAgent', 'SiteRMLibs'] + list_packages(['src/python/SiteRMAgent/', 'src/python/SiteRMLibs/']),
    install_requires=[],
    data_files=[("/etc/cron.d/", ["packaging/general/siterm-crons"]),
                ("/etc/cron-scripts/", ["packaging/general/siterm-ca-cron.sh"])],
    py_modules=get_py_modules(['src/python/SiteRMAgent', 'src/python/SiteRMLibs']),
    scripts=["packaging/siterm-site-agent/scripts/sitermagent-update",
             "packaging/siterm-site-agent/scripts/siterm-ruler",
             "packaging/siterm-site-agent/scripts/siterm-debugger",
             "packaging/siterm-site-agent/scripts/siterm-prompush",
             "packaging/general/Config-Fetcher"]
)
