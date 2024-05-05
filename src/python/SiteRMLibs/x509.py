#!/usr/bin/env python3
"""Certificate loading and validation tool.

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
Title                   : siterm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""
import re
import time
from datetime import datetime
from SiteRMLibs.GitConfig import getGitConfig


class CertHandler():
    """Cert handler."""
    def __init__(self):
        self.allowedCerts = {}
        self.allowedWCerts = {}
        self.loadTime = None
        self.loadAuthorized()
        self.config = getGitConfig()

    def loadAuthorized(self):
        """Load all authorized users for FE from git."""
        dateNow = datetime.now().strftime('%Y-%m-%d-%H')
        if dateNow != self.loadTime:
            self.loadTime = dateNow
            self.config = getGitConfig()
            self.allowedCerts = {}
            for user, userinfo in list(self.config.get('AUTH', {}).items()):
                self.allowedCerts.setdefault(userinfo['full_dn'], {})
                self.allowedCerts[userinfo['full_dn']]['username'] = user
                self.allowedCerts[userinfo['full_dn']]['permissions'] = userinfo['permissions']
            for user, userinfo in list(self.config.get('AUTH_RE', {}).items()):
                self.allowedWCerts.setdefault(userinfo['full_dn'], {})
                self.allowedWCerts[userinfo['full_dn']]['username'] = user
                self.allowedWCerts[userinfo['full_dn']]['permissions'] = userinfo['permissions']

    @staticmethod
    def getCertInfo(environ):
        """Get certificate info."""
        out = {}
        for key in ['SSL_CLIENT_V_REMAIN', 'SSL_CLIENT_S_DN', 'SSL_CLIENT_I_DN', 'SSL_CLIENT_V_START', 'SSL_CLIENT_V_END']:
            if key not in environ:
                print('Request without certificate. Unauthorized')
                raise Exception('Unauthorized access. Request without certificate.')
        out['subject'] = environ['SSL_CLIENT_S_DN']
        out['notAfter'] = int(time.mktime(datetime.strptime(environ['SSL_CLIENT_V_END'], "%b %d %H:%M:%S %Y %Z").timetuple()))
        out['notBefore'] = int(time.mktime(datetime.strptime(environ['SSL_CLIENT_V_START'], "%b %d %H:%M:%S %Y %Z").timetuple()))
        out['issuer'] = environ['SSL_CLIENT_I_DN']
        out['fullDN'] = f"{out['issuer']}{out['subject']}"
        return out

    def checkAuthorized(self, environ):
        """Check if user is authorized."""
        if environ['CERTINFO']['fullDN'] in self.allowedCerts:
            return self.allowedCerts[environ['CERTINFO']['fullDN']]
        for wildcarddn, userinfo in self.allowedWCerts.items():
            if re.match(wildcarddn, environ['CERTINFO']['fullDN']):
                return userinfo
        print(f"User DN {environ['CERTINFO']['fullDN']} is not in authorized list. Full info: {environ['CERTINFO']}")
        raise Exception(f"User DN {environ['CERTINFO']['fullDN']} is not in authorized list. Full info: {environ['CERTINFO']}")

    def validateCertificate(self, environ):
        """Validate certification validity."""
        now = datetime.utcnow()
        timestamp = int(time.mktime(now.timetuple()))
        if 'CERTINFO' not in environ:
            raise Exception('Certificate not found. Unauthorized')
        for key in ['subject', 'notAfter', 'notBefore', 'issuer', 'fullDN']:
            if key not in list(environ['CERTINFO'].keys()):
                print(f'{key} not available in certificate retrieval')
                raise Exception('Unauthorized access')
        # Check time before
        if environ['CERTINFO']['notBefore'] > timestamp:
            print(f"Certificate Invalid. Current Time: {timestamp} NotBefore: {environ['CERTINFO']['notBefore']}")
            raise Exception(f"Certificate Invalid. Full Info: {environ['CERTINFO']}")
        # Check time after
        if environ['CERTINFO']['notAfter'] < timestamp:
            print(f"Certificate Invalid. Current Time: {timestamp} NotAfter: {environ['CERTINFO']['notAfter']}")
            raise Exception(f"Certificate Invalid. Full Info: {environ['CERTINFO']}")
        # Check if reload of auth list is needed.
        self.loadAuthorized()
        # Check DN in authorized list
        return self.checkAuthorized(environ)
