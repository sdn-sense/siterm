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
import os.path
import re
from datetime import datetime, timezone
from OpenSSL import crypto
from SiteRMLibs.GitConfig import getGitConfig

class CertHandler():
    """Cert handler."""
    def __init__(self):
        self.allowedCerts = {}
        self.allowedWCerts = {}
        self.loadTime = None
        self.loadAuthorized()
        self.gitConf = getGitConfig()

    def loadAuthorized(self):
        """Load all authorized users for FE from git."""
        dateNow = datetime.now(timezone.utc).strftime('%Y-%m-%d-%H')
        if dateNow != self.loadTime:
            self.loadTime = dateNow
            self.gitConf = getGitConfig()
            self.allowedCerts = {}
            if self.gitConf.config.get('AUTH', {}):
                for user, userinfo in list(self.gitConf.config.get('AUTH', {}).items()):
                    self.allowedCerts.setdefault(userinfo['full_dn'], {})
                    self.allowedCerts[userinfo['full_dn']]['username'] = user
                    self.allowedCerts[userinfo['full_dn']]['permissions'] = userinfo['permissions']
            if self.gitConf.config.get('AUTH_RE', {}):
                for user, userinfo in list(self.gitConf.config.get('AUTH_RE', {}).items()):
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
        out['notAfter'] = int(datetime.strptime(environ['SSL_CLIENT_V_END'], "%b %d %H:%M:%S %Y %Z").timestamp())
        out['notBefore'] = int(datetime.strptime(environ['SSL_CLIENT_V_START'], "%b %d %H:%M:%S %Y %Z").timestamp())
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
        timestamp = int(datetime.now(timezone.utc).timestamp())
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

    def loadCACerts(self, capath):
        """Load CA certificates."""
        # Load CA certificates from /etc/grid-security/certificates
        store = crypto.X509Store()
        for filename in os.listdir(capath):
            if filename.endswith(".pem"):
                try:
                    with open(os.path.join(capath, filename), "rb") as cafile:
                        cacert = crypto.load_certificate(crypto.FILETYPE_PEM, cafile.read())
                        store.add_cert(cacert)
                except Exception as ex:
                    print(f"Failed to load CA cert {filename}: {ex}")
        return store

    def validateHostCertKey(self, certpath, keypath):
        """Validate Host Cert and key and check if they match"""
        out = {'failure': None}
        if not os.path.isfile(certpath):
            return out
        if not os.path.isfile(keypath):
            return out

        try:
            with open(certpath, 'r', encoding='utf-8') as fd:
                certcontent = fd.read()
            with open(keypath, 'r', encoding='utf-8') as fd:
                keycontent = fd.read()

            cert = crypto.load_certificate(crypto.FILETYPE_PEM, certcontent)
            key = crypto.load_privatekey(crypto.FILETYPE_PEM, keycontent)
            castore = self.loadCACerts('/etc/grid-security/certificates')

            subject = cert.get_subject()
            out['subject'] = "".join(f"/{name.decode()}={value.decode()}" for name, value in subject.get_components())
            out['notAfter'] = int(datetime.strptime(cert.get_notAfter().decode('UTF-8'), '%Y%m%d%H%M%SZ').timestamp())
            out['notBefore'] = int(datetime.strptime(cert.get_notBefore().decode('UTF-8'), '%Y%m%d%H%M%SZ').timestamp())
            out['issuer'] = "".join(f"/{name.decode()}={value.decode()}" for name, value in cert.get_issuer().get_components())
            out['fullDN'] = f"{out['issuer']}{out['subject']}"

            try:
                context = crypto.X509StoreContext(castore, cert)
                context.verify_certificate()
                if cert.get_pubkey().to_cryptography_key().public_numbers() != key.to_cryptography_key().public_key().public_numbers():
                    out['failure'] = "Certificate and private key do not match!"
            except Exception as ex:
                out['failure'] = f"Certificate and key verification failed: {ex}"
        except Exception as ex:
            out['failure'] = f"Certificate and key verification failed at general: {ex}"
        return out


    def externalCertChecker(self):
        """Call for External service like Readiness/Liveness"""
        exitCode = 0
        for cert, key in [('/etc/siterm/certs/hostcert.pem', '/etc/siterm/certs/hostkey.pem'),
                          ('/etc/httpd/certs/cert.pem', '/etc/httpd/certs/privkey.pem')]:
            certCheck = self.validateHostCertKey(cert, key)
            timestampnow = int(datetime.now().timestamp())
            if certCheck.get('failure', None):
                print(f"Certificate check failed. Error: {certCheck['failure']}")
                exitCode = 2
            if certCheck['notAfter'] < timestampnow:
                print(f"Certificate expired. Expired at: {certCheck['notAfter']}")
                exitCode = 3
            if certCheck['notBefore'] > timestampnow:
                print(f"Certificate not valid yet. Not valid before: {certCheck['notBefore']}")
                exitCode = 4
            if certCheck['notAfter'] - timestampnow < 604800:
                print(f"Certificate will expire in less than 7 days. Expires at: {certCheck['notAfter']}")
        return exitCode
