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
import time
from datetime import datetime, timezone

import jwt
import requests
from jwt.algorithms import RSAAlgorithm
from SiteRMLibs.CustomExceptions import IssuesWithAuth, RequestWithoutCert
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import loadEnvFile


def getjwks(jwks_url):
    """Get JWKS from URL."""
    while True:
        try:
            print(f"Fetching JWKS from {jwks_url}")
            response = requests.get(jwks_url, timeout=60)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as ex:
            print(f"Error fetching JWKS from {jwks_url}: {ex}")
            time.sleep(5)


class OIDCHandler:
    """OIDC handler to validate claims from Apache environment."""

    def __init__(self):
        """Init OIDC Handler"""
        loadEnvFile()
        self.jwks = self.__getjwks__()
        self.audience = os.environ.get("OIDC_AUDIENCE", "")
        self.issuer = os.environ.get("OIDC_ISSUER", "")

    def __getjwks__(self):
        """Get JWKS."""
        jwks = os.environ.get("OIDC_JWKS", "")
        if not jwks:
            print("Missing OIDC_JWKS environment variable")
            raise IssuesWithAuth("Issues with permissions. Check backend logs.")
        return getjwks(jwks)

    def __get_key_from_jwks__(self, kid):
        """Find the key in JWKS that matches the kid"""
        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(json.dumps(key))
        raise IssuesWithAuth(f"No matching JWK found for kid={kid}")

    def validateOIDCInfo(self, request):
        """Validate OIDC claims and extract user identity & permissions."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise RequestWithoutCert("Unauthorized: Missing or invalid Bearer token")

        token = auth_header.replace("Bearer ", "")
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
        except Exception as ex:
            raise IssuesWithAuth(f"Invalid token header: {ex}") from ex

        public_key = self.__get_key_from_jwks__(kid)
        try:
            decoded = jwt.decode(token, public_key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer)
            return decoded
        except jwt.ExpiredSignatureError as ex:
            raise IssuesWithAuth("Token expired") from ex
        except jwt.InvalidTokenError as ex:
            raise IssuesWithAuth(f"Invalid token: {ex}") from ex


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
