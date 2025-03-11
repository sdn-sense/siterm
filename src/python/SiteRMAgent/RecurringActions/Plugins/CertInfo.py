#!/usr/bin/env python3
"""Plugin which gathers information about certificate

Authors:
  Justas Balcas jbalcas (at) caltech.edu

Date: 2022/12/23
"""
import pprint
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import getLoggingObject
from SiteRMLibs.hostcert import HostCertHandler

class CertInfo:
    """CertInfo Plugin"""

    def __init__(self, config=None, logger=None):
        self.config = config if config else getGitConfig()
        self.logger = logger if logger else getLoggingObject(config=self.config, service='Agent')
        self.certHandler = HostCertHandler()


    def get(self, **_kwargs):
        """Get certificate info."""
        certInfo = self.certHandler.validateHostCertKey('/etc/grid-security/hostcert.pem',
                                                        '/etc/grid-security/hostkey.pem')
        exitCode, msg = self.certHandler.runChecks(certInfo)
        if exitCode:
            self.logger.error(f"Failed to validate host certificate: {msg}")

        return certInfo



if __name__ == "__main__":
    obj = CertInfo()
    PRETTY = pprint.PrettyPrinter(indent=4)
    PRETTY.pprint(obj.get())
