#!/usr/bin/env python3
"""Plugin which gathers information about certificate

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/12/23
"""
import time
import pprint
from datetime import datetime
from OpenSSL import crypto
from DTNRMLibs.MainUtilities import getLoggingObject

NAME = 'CertInfo'

def get(**_):
    """Get certificate info."""
    out = {}
    certcontent = open('/etc/grid-security/hostcert.pem').read()
    cert = crypto.load_certificate(crypto.FILETYPE_PEM, certcontent)
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

if __name__ == "__main__":
    getLoggingObject(logType='StreamLogger', service='Agent')
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(get())
