#!/usr/bin/env python3
"""
Setup tools script for SiteRM Site Frontend.
Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/05/20
"""
from setuptools import setup
from setupUtilities import list_packages, get_py_modules, get_web_files, VERSION

# Cronjobs which are running also have to be prepared with correct timing.
# Also another cronjob, which monitors config file and modifies cronjobs if needed.
# Currently it is allowed to specify only minutes and up to 30 minutes.
# This is how CRONJOBS are handled and division is done only for the current hour.
SCRIPTS = ["packaging/general/Config-Fetcher"]
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
    install_requires=['pyparsing', "rdflib", 'importlib', 'setuptools', 'future', 'simplejson',
                      'mod-wsgi', 'prometheus-client', 'python-dateutil', 'pyaml', 'requests',
                      'pycurl', 'pyOpenSSL', 'mariadb==1.0.8', 'cryptography>=35.0',
                      'wheel', 'paramiko', 'ansible-runner', 'psutil', 'typing-extensions',
                      'ansible', 'setuptools-rust', 'PyYAML'],
    data_files=[("/var/www/wsgi-scripts/", ["packaging/dtnrm-site-fe/sitefe.wsgi"]),
                ("/etc/httpd/conf.d/", ["packaging/dtnrm-site-fe/sitefe-httpd.conf",
                                        "packaging/dtnrm-site-fe/welcome.conf"]),
                ("/etc/cron.d/", ["packaging/general/siterm-crons"]),
                ("/etc/cron-scripts/", ["packaging/general/siterm-ca-cron.sh"])] + get_web_files(),
    py_modules=get_py_modules(['src/python/SiteFE/', 'src/python/DTNRMLibs']),
    scripts=SCRIPTS
)
