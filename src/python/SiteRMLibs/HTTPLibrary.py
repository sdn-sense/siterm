#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Modern HTTP(s) request handler using httpx.

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
Date                    : 2017/09/26
"""

import os
import socket
import time
import urllib.parse

import httpx
from SiteRMLibs.CustomExceptions import ValidityFailure


def argValidity(arg, aType):
    "Argument validation."
    if not arg:
        return {} if aType == dict else []
    if aType == dict:
        if isinstance(arg, dict):
            return arg
    elif aType == list:
        if isinstance(arg, list):
            return arg
    else:
        raise ValidityFailure(f"Input {type(arg)} != {aType}.")
    return {} if aType == dict else []


def checkServerUrl(url):
    """Check if given url starts with http tag."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"You must include http(s):// in the server address: {url}")


def sanitizeURL(url):
    """Take the url return sanitized clean URL."""
    endpoint = urllib.parse.urlparse(url)
    netloc = f"{endpoint.hostname}:{endpoint.port}" if endpoint.port else endpoint.hostname
    cleanUrl = urllib.parse.urlunparse([endpoint.scheme, netloc, endpoint.path, endpoint.params, endpoint.query, endpoint.fragment])
    return cleanUrl


def getKeyCertFromEnv():
    """Get the certificate and key from environment variables or default locations."""
    pairs = [
        ("X509_HOST_KEY", "X509_HOST_CERT"),
        ("X509_USER_PROXY", "X509_USER_PROXY"),
        ("X509_USER_KEY", "X509_USER_CERT"),
    ]
    for key_env, cert_env in pairs:
        key = os.environ.get(key_env)
        cert = os.environ.get(cert_env)
        if key and cert and os.path.exists(key) and os.path.exists(cert):
            return cert, key  # httpx expects cert, key
    uid = str(os.getuid())
    proxy = f"/tmp/x509up_u{uid}"
    if os.path.exists(proxy):
        return proxy, proxy
    home = os.environ.get("HOME")
    if home and os.path.exists(f"{home}/.globus/usercert.pem") and os.path.exists(f"{home}/.globus/userkey.pem"):
        return f"{home}/.globus/usercert.pem", f"{home}/.globus/userkey.pem"
    if os.path.exists("/etc/grid-security/hostcert.pem") and os.path.exists("/etc/grid-security/hostkey.pem"):
        return "/etc/grid-security/hostcert.pem", "/etc/grid-security/hostkey.pem"
    return None, None


def getCAPathFromEnv():
    """Get the CA path from environment variables or default locations."""
    return os.environ.get("X509_CERT_DIR")


class Requests:
    """Main Requests class to handle HTTP requests."""

    def __init__(self, url="http://localhost", logger=None):
        """Initialize the Requests class with a URL and optional logger."""
        self.logger = logger
        self.useragent = f"SiteRM-{socket.gethostname()}"
        self.default_headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": self.useragent}
        self.host = sanitizeURL(url)
        checkServerUrl(self.host)

        self.session = httpx.Client(cert=self.__http_getCertKeyTuple(), verify=self.__http_getCAPath(), timeout=60.0, follow_redirects=True)
        self.notFEsession = httpx.Client(timeout=60.0, follow_redirects=True)

    def close(self):
        """Close the HTTP sessions."""
        self.session.close()
        self.notFEsession.close()

    def setHost(self, url):
        """Set the host URL for the Requests class."""
        self.host = sanitizeURL(url)
        checkServerUrl(self.host)

    def http_extendUserAgent(self, useragent):
        """Extend the User-Agent header with additional information."""
        self.default_headers["User-Agent"] += f" {useragent}"

    def __http_resetUserAgent(self):
        """Reset the User-Agent header to the default value."""
        self.default_headers["User-Agent"] = self.useragent

    def __http_getCertKeyTuple(self):
        """Get Certificate and Key Tuple."""
        cert, key = getKeyCertFromEnv()
        if cert and key:
            return (cert, key)
        return None

    def __http_getCAPath(self):
        """Get CA Path."""
        return getCAPathFromEnv() or True

    def _stripHostFromUrl(self, uri):
        """Get the full URL for the given URI."""
        parsed = urllib.parse.urlparse(uri)
        uri = urllib.parse.urlunparse(("", "", parsed.path, parsed.params, parsed.query, parsed.fragment))
        if parsed.scheme in ["http", "https"]:
            url = uri
        else:
            url = urllib.parse.urljoin(self.host, uri)
        return url

    def __http_makeRequest(self, verb, uri, **kwargs):
        """Make an HTTP request with the given parameters."""
        kwargs.setdefault("data", None)
        kwargs.setdefault("headers", None)
        kwargs.setdefault("json", True)
        kwargs.setdefault("SiteRMHTTPCall", True)
        if kwargs.get("useragent"):
            self.http_extendUserAgent(kwargs["useragent"])
        headers = {**self.default_headers, **argValidity(kwargs["headers"], dict)}
        url = urllib.parse.urljoin(self.host, self._stripHostFromUrl(uri))
        try:
            if kwargs["SiteRMHTTPCall"]:
                response = self.session.request(method=verb, url=url, headers=headers, json=kwargs["data"] if kwargs["json"] else None, data=None if kwargs["json"] else kwargs["data"])
                return response.json(), response.status_code, response.reason_phrase, False
            # The only implementation of nonFESession is to fetch github config files
            # We are not passing headers or json data here
            response = self.notFEsession.request(method=verb, url=url)
            return response.text, response.status_code, response.reason_phrase, False
        except httpx.HTTPStatusError as e:
            return e.response.text, e.response.status_code, e.response.reason_phrase, False
        except Exception as e:
            return {"error": str(e)}, 500, "Internal Error", False
        finally:
            self.__http_resetUserAgent()

    def makeHttpCall(self, verb, url, **kwargs):
        """Put JSON to the Site FE."""
        kwargs.setdefault("retries", 3)
        kwargs.setdefault("raiseEx", True)
        kwargs.setdefault("sleep", 1)
        exc = []
        if verb not in ["GET", "POST", "PUT", "DELETE"]:
            raise ValueError(f"Invalid HTTP verb: {verb}. Must be one of GET, POST, PUT, DELETE.")
        while kwargs["retries"] > 0:
            kwargs["retries"] -= 1
            try:
                return self.__http_makeRequest(verb, url, **kwargs)
            except Exception as ex:
                self.logger.debug(f"Got Exception: {ex}. Will retry {kwargs['retries']} more times.")
                exc.append(str(ex))
                if kwargs["retries"] == 0 and kwargs["raiseEx"]:
                    self.logger.debug("No more retries left. Raising exception.")
                    raise Exception(f"Failed to make HTTP call after retries: {exc}") from ex
                if kwargs["retries"] != 0:
                    time.sleep(kwargs["sleep"])
        return "Failed after all retries", -1, "Failed after all retries", False
