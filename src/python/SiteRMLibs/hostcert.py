#!/usr/bin/env python3
"""Certificate loading and validation tool.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""

import os.path
import traceback
from datetime import datetime

from OpenSSL import crypto
from SiteRMLibs.GitConfig import getGitConfig


class HostCertHandler:
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
                    print(f"Full traceback: {traceback.format_exc()}")
        return store

    def validateHostCertKey(self, certpath, keypath):
        """Validate Host Cert and key and check if they match"""
        out = {"failure": None}
        if not os.path.isfile(certpath):
            return out
        if not os.path.isfile(keypath):
            return out

        try:
            with open(certpath, "r", encoding="utf-8") as fd:
                certcontent = fd.read()
            with open(keypath, "r", encoding="utf-8") as fd:
                keycontent = fd.read()

            cert = crypto.load_certificate(crypto.FILETYPE_PEM, certcontent)
            key = crypto.load_privatekey(crypto.FILETYPE_PEM, keycontent)
            castore = self.loadCACerts("/etc/grid-security/certificates")

            subject = cert.get_subject()
            out["subject"] = "".join(f"/{name.decode()}={value.decode()}" for name, value in subject.get_components())
            out["notAfter"] = int(datetime.strptime(cert.get_notAfter().decode("UTF-8"), "%Y%m%d%H%M%SZ").timestamp())
            out["notBefore"] = int(datetime.strptime(cert.get_notBefore().decode("UTF-8"), "%Y%m%d%H%M%SZ").timestamp())
            out["issuer"] = "".join(f"/{name.decode()}={value.decode()}" for name, value in cert.get_issuer().get_components())
            out["fullDN"] = f"{out['issuer']}{out['subject']}"

            try:
                context = crypto.X509StoreContext(castore, cert)
                context.verify_certificate()
                if cert.get_pubkey().to_cryptography_key().public_numbers() != key.to_cryptography_key().public_key().public_numbers():
                    out["failure"] = "Certificate and private key do not match!"
            except Exception as ex:
                out["failure"] = f"Certificate and key verification failed: {ex}"
                print(f"Full traceback: {traceback.format_exc()}")
        except Exception as ex:
            out["failure"] = f"Certificate and key verification failed at general: {ex}"
            print(f"Full traceback: {traceback.format_exc()}")
        return out

    @staticmethod
    def runChecks(certinfo):
        """Run certificate checks"""
        exitCode = 0
        msg = ""
        timestampnow = int(datetime.now().timestamp())
        if certinfo.get("failure", False):
            msg = f"Certificate check failed. Error: {certinfo['failure']}"
            print(msg)
            exitCode = 2
        if "notAfter" in certinfo and certinfo["notAfter"] < timestampnow:
            msg = f"Certificate expired. Expired at: {certinfo['notAfter']}"
            print(msg)
            exitCode = 3
        if "notBefore" in certinfo and certinfo["notBefore"] > timestampnow:
            msg = f"Certificate not valid yet. Not valid before: {certinfo['notBefore']}"
            print(msg)
            exitCode = 4
        if "notAfter" in certinfo and certinfo["notAfter"] - timestampnow < 1209600:
            msg = f"Certificate will expire in less than 14 days. Expires at: {certinfo['notAfter']}"
            print(msg)
        return exitCode, msg

    def externalCertChecker(self):
        """Call for External service like Readiness/Liveness"""
        exitCode = 0
        for cert, key in [
            ("/etc/grid-security/hostcert.pem", "/etc/grid-security/hostkey.pem"),
            ("/etc/httpd/certs/cert.pem", "/etc/httpd/certs/privkey.pem"),
        ]:
            certCheck = self.validateHostCertKey(cert, key)
            tmpExitCode, _msg = self.runChecks(certCheck)
            if max(exitCode, tmpExitCode):
                exitCode = tmpExitCode
        return exitCode
