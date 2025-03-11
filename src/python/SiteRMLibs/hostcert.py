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
from datetime import datetime
from OpenSSL import crypto
from SiteRMLibs.GitConfig import getGitConfig


class HostCertHandler():
    """Cert handler."""
    def __init__(self):
        self.loadTime = None
        self.gitConf = getGitConfig()


    @staticmethod
    def loadCACerts(capath):
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

    def runChecks(self, certinfo):
        exitCode = 0
        msg = ""
        timestampnow = int(datetime.now().timestamp())
        if certinfo.get('failure', False):
            msg = f"Certificate check failed. Error: {certinfo['failure']}"
            print(msg)
            exitCode = 2
        if 'notAfter' in certinfo and certinfo['notAfter'] < timestampnow:
            msg = f"Certificate expired. Expired at: {certinfo['notAfter']}"
            print(msg)
            exitCode = 3
        if 'notBefore' in certinfo and certinfo['notBefore'] > timestampnow:
            msg = f"Certificate not valid yet. Not valid before: {certinfo['notBefore']}"
            print(msg)
            exitCode = 4
        if 'notAfter' in certinfo and certinfo['notAfter'] - timestampnow < 1209600:
            msg = f"Certificate will expire in less than 14 days. Expires at: {certinfo['notAfter']}"
            print(msg)
        return exitCode, msg

    def externalCertChecker(self):
        """Call for External service like Readiness/Liveness"""
        exitCode = 0
        for cert, key in [('/etc/siterm/certs/hostcert.pem', '/etc/siterm/certs/hostkey.pem'),
                          ('/etc/httpd/certs/cert.pem', '/etc/httpd/certs/privkey.pem')]:
            certCheck = self.validateHostCertKey(cert, key)
            tmpExitCode, _msg = self.runChecks(certCheck)
            if tmpExitCode > exitCode:
                exitCode = tmpExitCode
        return exitCode
