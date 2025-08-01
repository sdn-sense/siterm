#!/usr/bin/env python3
# pylint: disable=line-too-long
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
import json
import os
import re
from datetime import datetime, timezone

from SiteRMLibs.CustomExceptions import IssuesWithAuth, RequestWithoutCert
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import loadEnvFile


class OIDCHandler:
    """OIDC handler to validate claims from Apache environment."""

    def __init__(self):
        """Init OIDC Handler"""
        loadEnvFile()
        self.required_issuer = os.environ.get("OIDC_REQUIRED_ISSUER", "https://login.sdn-sense.net/")
        self.permission_claim_prefix = "HTTP_" + os.environ.get("OIDC_PERMISSIONS_CLAIM", "OIDC_CLAIM_HTTPS___SDN_SENSE.NET_PERMISSIONS")

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
                    raise IssuesWithAuth("Issues with permissions. Check backend logs.") from ex
        print(f"Permissions claim with prefix '{self.permission_claim_prefix}' not found")
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
                    self.allowedCerts[userinfo["full_dn"]]["permissions"] = userinfo["permissions"]
            if self.gitConf.config.get("AUTH_RE", {}):
                for user, userinfo in list(self.gitConf.config.get("AUTH_RE", {}).items()):
                    self.allowedWCerts.setdefault(userinfo["full_dn"], {})
                    self.allowedWCerts[userinfo["full_dn"]]["username"] = user
                    self.allowedWCerts[userinfo["full_dn"]]["permissions"] = userinfo["permissions"]

    @staticmethod
    def getCertInfo(request):
        """Get certificate info."""
        out = {}
        for key in [
            "ssl_client_v_remain",
            "ssl_client_s_dn",
            "ssl_client_i_dn",
            "ssl_client_v_start",
            "ssl_client_v_end",
        ]:
            if key not in request.headers or request.headers.get(key, None) in (None, "", "(null)"):
                print(f"Missing required certificate info: {key}")
                raise RequestWithoutCert("Unauthorized access. Request without certificate.")

        out["subject"] = request.headers["ssl_client_s_dn"]
        # pylint: disable=line-too-long
        out["notAfter"] = int(datetime.strptime(request.headers["ssl_client_v_end"], "%b %d %H:%M:%S %Y %Z").timestamp())
        out["notBefore"] = int(datetime.strptime(request.headers["ssl_client_v_start"], "%b %d %H:%M:%S %Y %Z").timestamp())
        out["issuer"] = request.headers["ssl_client_i_dn"]
        out["fullDN"] = f"{out['issuer']}{out['subject']}"
        return out

    def checkAuthorized(self, certinfo):
        """Check if user is authorized."""
        if certinfo["fullDN"] in self.allowedCerts:
            return self.allowedCerts[certinfo["fullDN"]]
        for wildcarddn, userinfo in self.allowedWCerts.items():
            if re.match(wildcarddn, certinfo["fullDN"]):
                return userinfo
        print(f"User DN {certinfo['fullDN']} is not in authorized list. Full info: {certinfo}")
        raise IssuesWithAuth("Issues with permissions. Check backend logs.")

    def validateCertificate(self, request):
        """Validate certificate validity."""
        certinfo = self.getCertInfo(request)
        timestamp = int(datetime.now(timezone.utc).timestamp())
        for key in ["subject", "notAfter", "notBefore", "issuer", "fullDN"]:
            if key not in certinfo:
                print(f"{key} not available in certificate retrieval")
                raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check time before
        if certinfo["notBefore"] > timestamp:
            print(f"Certificate Invalid. Current Time: {timestamp} NotBefore: {certinfo['notBefore']}")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check time after
        if certinfo["notAfter"] < timestamp:
            print(f"Certificate Invalid. Current Time: {timestamp} NotAfter: {certinfo['notAfter']}")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        # Check if reload of auth list is needed.
        self.loadAuthorized()
        # Check DN in authorized list
        certinfo["permissions"] = self.checkAuthorized(certinfo)
        return certinfo
