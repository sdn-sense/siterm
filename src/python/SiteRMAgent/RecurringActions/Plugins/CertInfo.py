#!/usr/bin/env python3
"""Plugin which gathers information about certificate

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/12/23
"""
import os.path
import time
import pprint
from datetime import datetime
from OpenSSL import crypto
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject


class CertInfo:
    """CertInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service='Agent')


    def get(self, **_kwargs):
        """Get certificate info."""
        out = {}
        certcontent = ""
        if not os.path.isfile('/etc/grid-security/hostcert.pem'):
            self.logger.warning("No certificate found at /etc/grid-security/hostcert.pem")
            return out
        with open('/etc/grid-security/hostcert.pem', 'r', encoding='utf-8') as fd:
            certcontent = fd.read()
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
    obj = CertInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
