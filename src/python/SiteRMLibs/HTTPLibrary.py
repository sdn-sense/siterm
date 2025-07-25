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


def check_server_url(url):
    """Check if given url starts with http tag."""
    if not (url.startswith("http://") or url.startswith("https://")):
        raise ValueError(f"You must include http(s):// in the server address: {url}")


def sanitizeURL(url):
    """Take the url return sanitized url object
        or password."""
    endpoint = urllib.parse.urlparse(url)
    netloc = f"{endpoint.hostname}:{endpoint.port}" if endpoint.port else endpoint.hostname
    cleanUrl = urllib.parse.urlunparse([endpoint.scheme, netloc, endpoint.path,
                                        endpoint.params, endpoint.query, endpoint.fragment])
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
    def __init__(self, url="http://localhost", inputdict=None, config=None):
        inputdict = inputdict or {}
        self.config = config
        self.default_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"SiteRM + {socket.gethostname()}"
        }
        self.additional_headers = {}

        self.host = sanitizeURL(url)
        check_server_url(self.host)

        self.session = httpx.Client(cert=self.getCertKeyTuple(),
                                    verify=self.getCAPath(),
                                    timeout=30.0
        )
        self.__dict__.update(inputdict)

    def getCertKeyTuple(self):
        """Get Certificate and Key Tuple."""
        cert, key = getKeyCertFromEnv()
        if cert and key:
            return (cert, key)
        return None

    def getCAPath(self):
        """Get CA Path."""
        return getCAPathFromEnv() or True

    def makeRequest(self, uri, verb, data=None, headers=None, json=True):
        """Make an HTTP request with the given parameters."""
        headers = {**self.default_headers, **self.additional_headers, **argValidity(headers, dict)}
        url = self.host + uri
        try:
            response = self.session.request(method=verb, url=url, headers=headers, json=data if json else None, data=None if json else data)
            return response.json(), response.status_code, response.reason_phrase, False
        except httpx.HTTPStatusError as e:
            return e.response.text, e.response.status_code, e.response.reason_phrase, False
        except Exception as e:
            return {"error": str(e)}, 500, "Internal Error", False

    def get(self, uri, data=None, headers=None):
        """Make a GET request."""
        return self.makeRequest("GET", uri, data=data, headers=headers)

    def post(self, uri, data=None, headers=None):
        """Make a POST request."""
        return self.makeRequest("POST", uri, data=data, headers=headers)

    def put(self, uri, data=None, headers=None):
        """Make a PUT request."""
        return self.makeRequest("PUT", uri, data=data, headers=headers)

    def delete(self, uri, data=None, headers=None):
        """Make a DELETE request."""
        return self.makeRequest("DELETE", uri, data=data, headers=headers)
