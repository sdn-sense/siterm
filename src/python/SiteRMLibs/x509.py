#!/usr/bin/env python3
"""User/Application authentication using Cert or OIDC.

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
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""
import os
import re
import json
from datetime import datetime, timezone
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import loadEnvFile
from SiteRMLibs.CustomExceptions import RequestWithoutCert, IssuesWithAuth


class OIDCHandler:
    """OIDC handler to validate claims from Apache environment."""

    def __init__(self):
        """Init OIDC Handler"""
        loadEnvFile()
        self.required_issuer = os.environ.get(
            "OIDC_REQUIRED_ISSUER", "https://login.sdn-sense.net/"
        )
        self.permission_claim_prefix = "HTTP_" + os.environ.get(
            "OIDC_PERMISSIONS_CLAIM", "OIDC_CLAIM_HTTPS___SDN_SENSE.NET_PERMISSIONS"
        )

    @staticmethod
    def _getEnv(environ, key):
        value = environ.get(key)
        if not value:
            print(f"Missing required OIDC claim: {key}")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        return value

    def parsePermissions(self, environ):
        """Extract and parse the custom permissions claim."""
        for key, value in environ.items():
            if key.startswith(self.permission_claim_prefix):
                try:
                    return json.loads(value)
                except json.JSONDecodeError as ex:
                    print(f"Invalid JSON in permissions claim: {value}")
                    raise IssuesWithAuth(
                        "Issues with permissions. Check backend logs."
                    ) from ex
        print(
            f"Permissions claim with prefix '{self.permission_claim_prefix}' not found"
        )
        raise IssuesWithAuth("Issues with permissions. Check backend logs.")

    def validateOIDCInfo(self, environ):
        """Validate OIDC claims and extract user identity & permissions."""
        email = self._getEnv(environ, "HTTP_OIDC_CLAIM_EMAIL")
        issuer = self._getEnv(environ, "HTTP_OIDC_CLAIM_ISS")
        emailVerified = self._getEnv(environ, "HTTP_OIDC_CLAIM_EMAIL_VERIFIED")

        if issuer != self.required_issuer:
            print(f"Unexpected issuer: {issuer} (expected {self.required_issuer})")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")

        if emailVerified not in ("1", "true", "True", True):
            print(f"Email not verified. Debug info {email} {issuer} {emailVerified}")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")

        permissions = self.parsePermissions(environ)

        return {
            "email": email,
            "issuer": issuer,
            "permissions": permissions,
            "claims": {k: v for k, v in environ.items() if k.startswith("HTTP_OIDC_CLAIM_")},
        }


class CertHandler:
    """Cert handler."""

    def __init__(self):
        self.allowedCerts = {}
        self.allowedWCerts = {}
        self.loadTime = None
        self.loadAuthorized()
        self.gitConf = getGitConfig()

    def loadAuthorized(self):
        """Load all authorized users for FE from git."""
        dateNow = datetime.now(timezone.utc).strftime("%Y-%m-%d-%H")
        if dateNow != self.loadTime:
            self.loadTime = dateNow
            self.gitConf = getGitConfig()
            self.allowedCerts = {}
            if self.gitConf.config.get("AUTH", {}):
                for user, userinfo in list(self.gitConf.config.get("AUTH", {}).items()):
                    self.allowedCerts.setdefault(userinfo["full_dn"], {})
                    self.allowedCerts[userinfo["full_dn"]]["username"] = user
                    self.allowedCerts[userinfo["full_dn"]]["permissions"] = userinfo[
                        "permissions"
                    ]
            if self.gitConf.config.get("AUTH_RE", {}):
                for user, userinfo in list(
                    self.gitConf.config.get("AUTH_RE", {}).items()
                ):
                    self.allowedWCerts.setdefault(userinfo["full_dn"], {})
                    self.allowedWCerts[userinfo["full_dn"]]["username"] = user
                    self.allowedWCerts[userinfo["full_dn"]]["permissions"] = userinfo[
                        "permissions"
                    ]

    @staticmethod
    def getCertInfo(environ):
        """Get certificate info."""
        out = {}
        for key in [
            "HTTP_SSL_CLIENT_V_REMAIN",
            "HTTP_SSL_CLIENT_S_DN",
            "HTTP_SSL_CLIENT_I_DN",
            "HTTP_SSL_CLIENT_V_START",
            "HTTP_SSL_CLIENT_V_END",
        ]:
            if key not in environ or environ.get(key, None) in (None, "", "(null)"):
                raise RequestWithoutCert("Unauthorized access. Request without certificate.")

        out["subject"] = environ["HTTP_SSL_CLIENT_S_DN"]
        out["notAfter"] = int(
            datetime.strptime(
                environ["HTTP_SSL_CLIENT_V_END"], "%b %d %H:%M:%S %Y %Z"
            ).timestamp()
        )
        out["notBefore"] = int(
            datetime.strptime(
                environ["HTTP_SSL_CLIENT_V_START"], "%b %d %H:%M:%S %Y %Z"
            ).timestamp()
        )
        out["issuer"] = environ["HTTP_SSL_CLIENT_I_DN"]
        out["fullDN"] = f"{out['issuer']}{out['subject']}"
        return out

    def checkAuthorized(self, environ):
        """Check if user is authorized."""
        if environ["CERTINFO"]["fullDN"] in self.allowedCerts:
            return self.allowedCerts[environ["CERTINFO"]["fullDN"]]
        for wildcarddn, userinfo in self.allowedWCerts.items():
            if re.match(wildcarddn, environ["CERTINFO"]["fullDN"]):
                return userinfo
        print(
            f"User DN {environ['CERTINFO']['fullDN']} is not in authorized list. Full info: {environ['CERTINFO']}"
        )
        raise IssuesWithAuth("Issues with permissions. Check backend logs.")

    def validateCertificate(self, environ):
        """Validate certification validity."""
        timestamp = int(datetime.now(timezone.utc).timestamp())
        if "CERTINFO" not in environ:
            raise RequestWithoutCert(
                "Unauthorized access. Request without certificate."
            )
        for key in ["subject", "notAfter", "notBefore", "issuer", "fullDN"]:
            if key not in list(environ["CERTINFO"].keys()):
                print(f"{key} not available in certificate retrieval")
                raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check time before
        if environ["CERTINFO"]["notBefore"] > timestamp:
            print(
                f"Certificate Invalid. Current Time: {timestamp} NotBefore: {environ['CERTINFO']['notBefore']}"
            )
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check time after
        if environ["CERTINFO"]["notAfter"] < timestamp:
            print(
                f"Certificate Invalid. Current Time: {timestamp} NotAfter: {environ['CERTINFO']['notAfter']}"
            )
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check if reload of auth list is needed.
        self.loadAuthorized()
        # Check DN in authorized list
        return self.checkAuthorized(environ)
