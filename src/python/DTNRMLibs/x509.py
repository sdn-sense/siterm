#!/usr/bin/env python
"""
Certificate loading and validation tool

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
import os
import time
from OpenSSL import crypto
from datetime import datetime

class CertHandler(object):
    def __init__(self):
        self.allowedCerts = {}
        self.loadAuthorized()

    def loadAuthorized(self):
        if os.path.isfile('/etc/dtnrm-auth.conf'):
            lines = []
            with open('/etc/dtnrm-auth.conf', 'r') as fd:
                lines = fd.readlines()
            for line in lines:
                if line.startswith('#'):
                    continue
                auth = line.split("|")
                if len(auth) == 3:
                    self.allowedCerts[auth[0]] = {'username': auth[1], 'permissions': auth[2].strip()}

    def getCertInfo(self, environ):
        out = {}
        if 'SSL_CLIENT_CERT' not in environ:
            print 'Request without certificate. Unauthorized'
            raise Exception('Unauthorized access')
        cert = crypto.load_certificate(crypto.FILETYPE_PEM, environ['SSL_CLIENT_CERT'])
        subject = cert.get_subject()
        out['subject'] = "".join("/{0:s}={1:s}".format(name.decode(), value.decode()) for name, value in subject.get_components())
        out['notAfter'] = int(time.mktime(datetime.strptime(str(cert.get_notAfter()), '%Y%m%d%H%M%SZ').timetuple()))
        out['notBefore'] = int(time.mktime(datetime.strptime(str(cert.get_notBefore()), '%Y%m%d%H%M%SZ').timetuple()))
        out['issuer'] = "".join("/{0:s}={1:s}".format(name.decode(), value.decode()) for name, value in cert.get_issuer().get_components())
        out['fullDN'] = "%s%s" % (out['issuer'], out['subject'])
        print 'Cert Info: %s' % out
        return out

    def validateCertificate(self, environ):
        now = datetime.utcnow()
        timestamp = int(time.mktime(now.timetuple()))
        if 'CERTINFO' not in environ:
            raise Exception('Certificate not found. Unauthorized')
        for key in ['subject', 'notAfter', 'notBefore', 'issuer', 'fullDN']:
            if key not in environ['CERTINFO'].keys():
                print '%s not available in certificate retrieval' % key
                raise Exception('Unauthorized access')
        # Check time before
        if environ['CERTINFO']['notBefore'] > timestamp:
            print 'Certificate Invalid. Current Timestamp: %s NotBefore: %s' % (timestamp, environ['CERTINFO']['notBefore'])
            raise Exception('Certificate Invalid')
        # Check time after
        if environ['CERTINFO']['notAfter'] < timestamp:
            print 'Certificate Invalid. Current Timestamp: %s NotAfter: %s' % (timestamp, environ['CERTINFO']['notAfter'])
            raise Exception('Certificate Invalid')
        # Check DN in authorized list
        if environ['CERTINFO']['fullDN'] not in self.allowedCerts.keys():
            print 'User DN %s is not in authorized list' % environ['CERTINFO']['fullDN']
            raise Exception('Unauthorized access')
        return self.allowedCerts[environ['CERTINFO']['fullDN']]
