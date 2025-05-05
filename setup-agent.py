#!/usr/bin/env python3
"""
Setup tools script for SiteRM Site Agent.
Authors:
  Justas Balcas jbalcas (at) es (dot) net

Date: 2022/05/20
"""
from setuptools import setup
from setupUtilities import list_packages, get_py_modules, VERSION

setup(
    name='SiteRMAgent',
    version=f"{VERSION}",
    long_description="SiteRM Agent installation",
    author="Justas Balcas",
    author_email="juztas@gmail.com",
    url="https://sdn-sense.github.io",
    download_url=f"https://github.com/sdn-sense/siterm/archive/refs/tags/{VERSION}.tar.gz",
    keywords=['SiteRM', 'system', 'monitor', 'SDN', 'end-to-end'],
    package_dir={'': 'src/python/'},
    packages=['SiteRMAgent', 'SiteRMLibs'] + list_packages(['src/python/SiteRMAgent/', 'src/python/SiteRMLibs/']),
    install_requires=[],
    py_modules=get_py_modules(['src/python/SiteRMAgent', 'src/python/SiteRMLibs']),
    scripts=["packaging/siterm-site-agent/scripts/sitermagent-update",
             "packaging/siterm-site-agent/scripts/siterm-ruler",
             "packaging/siterm-site-agent/scripts/siterm-agent-cleaner",
             "packaging/general/siterm-log-archiver",
             "packaging/general/Config-Fetcher",
             "packaging/general/siterm-debugger",
             "packaging/general/siterm-bgprocess",
             "packaging/general/siterm-liveness",
             "packaging/general/siterm-readiness",]
)
