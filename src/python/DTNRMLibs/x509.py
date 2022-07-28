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
Title                   : dtnrm
Author                  : Justas Balcas
Email                   : justas.balcas (at) cern.ch
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""
import time
from datetime import datetime
from OpenSSL import crypto
from DTNRMLibs.MainUtilities import getGitConfig


class CertHandler():
    """Cert handler."""
    def __init__(self):
        self.allowedCerts = {}
        self.loadTime = None
        self.loadAuthorized()

    def loadAuthorized(self):
        """Load all authorized users for FE from git."""
        dateNow = datetime.now().strftime('%Y-%m-%d-%H')
        if dateNow != self.loadTime:
            self.loadTime = dateNow
            config = getGitConfig()
            self.allowedCerts = {}
            for user, userinfo in list(config['AUTH'].items()):
                self.allowedCerts.setdefault(userinfo['full_dn'], {})
                self.allowedCerts[userinfo['full_dn']]['username'] = user
                self.allowedCerts[userinfo['full_dn']]['permissions'] = userinfo['permissions']

    @staticmethod
    def getCertInfo(environ):
        """Get certificate info."""
        out = {}
        if 'SSL_CLIENT_CERT' not in environ:
            print('Request without certificate. Unauthorized')
            raise Exception('Unauthorized access. Request without certificate.')
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, environ['SSL_CLIENT_CERT'])
        subject = cert.get_subject()
        out['subject'] = "".join(f"/{name.decode():s}={value.decode():s}"
                                 for name, value in subject.get_components())
        out['notAfter'] = int(time.mktime(datetime.strptime(cert.get_notAfter().decode('UTF-8'),
                                                            '%Y%m%d%H%M%SZ').timetuple()))
        out['notBefore'] = int(time.mktime(datetime.strptime(cert.get_notBefore().decode('UTF-8'),
                                                             '%Y%m%d%H%M%SZ').timetuple()))
        out['issuer'] = "".join(f"/{name.decode():s}={value.decode():s}"
                                for name, value in cert.get_issuer().get_components())
        out['fullDN'] = f"{out['issuer']}{out['subject']}"
        return out

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
            print('Certificate Invalid. Current Time: %s NotBefore: %s' % (timestamp,
                                                                           environ['CERTINFO']['notBefore']))
            raise Exception(f"Certificate Invalid. Full Info: {environ['CERTINFO']}")
        # Check time after
        if environ['CERTINFO']['notAfter'] < timestamp:
            print('Certificate Invalid. Current Time: %s NotAfter: %s' % (timestamp,
                                                                          environ['CERTINFO']['notAfter']))
            raise Exception(f"Certificate Invalid. Full Info: {environ['CERTINFO']}")
        # Check if reload of auth list is needed.
        self.loadAuthorized()
        # Check DN in authorized list
        if environ['CERTINFO']['fullDN'] not in self.allowedCerts:
            print('User DN %s is not in authorized list. Full info: %s' % (environ['CERTINFO']['fullDN'],
                                                                           environ['CERTINFO']))
            raise Exception('Unauthorized access')
        return self.allowedCerts[environ['CERTINFO']['fullDN']]
