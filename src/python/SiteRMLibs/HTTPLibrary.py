#!/usr/bin/env python3
# pylint: disable=line-too-long
"""Modern HTTP(s) request handler using httpx.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2017/09/26
"""
import copy
import functools
import os
import socket
import time
import traceback
import urllib.parse
from typing import Any, Callable
import base64

import httpx
import jwt

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from SiteRMLibs.CustomExceptions import (
    HTTPException,
    HTTPServerNotReady,
    ValidityFailure,
)
from SiteRMLibs.MainUtilities import getTempDir, getUTCnow

def signChallenge(challenge_response: dict, private_key_pem: str) -> str:
    """
    Sign a server-provided challenge using the given private key.
    """
    challenge_b64 = challenge_response["challenge"]
    challenge = base64.b64decode(challenge_b64)

    private_key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)

    if isinstance(private_key, ec.EllipticCurvePrivateKey):
        signature = private_key.sign(challenge, ec.ECDSA(hashes.SHA256()))

    elif isinstance(private_key, rsa.RSAPrivateKey):
        signature = private_key.sign(
            challenge,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH), hashes.SHA256())
    else:
        raise RuntimeError("Unsupported private key type")
    return base64.b64encode(signature).decode("utf-8")

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
    proxy = f"{getTempDir()}/x509up_u{uid}"
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


def httpserviceready(endpoint="/api/ready"):
    """Decorator that checks if the HTTP service is ready before executing the decorated function."""

    def decorator(func: Callable) -> Callable:
        """Decorator that checks if the HTTP service is ready before executing the decorated function."""

        @functools.wraps(func)
        def wrapper(self, *args, **kwargs) -> Any:
            """Wrapper function that checks if the HTTP service is ready before executing the decorated function."""
            # Check if service is ready by calling the specified endpoint
            kwargscopy = copy.deepcopy(kwargs)
            kwargscopy.setdefault("retries", 3)
            kwargscopy.setdefault("raiseEx", True)
            kwargscopy.setdefault("sleep", 5)
            if not kwargs.get("SiteRMHTTPCall", True):
                return func(self, *args, **kwargs)
            while kwargscopy["retries"] > 0:
                kwargscopy["retries"] -= 1
                try:
                    response, status_code, reason_phrase, _ = self.http_makeRequest("GET", endpoint)
                    if status_code == 503:
                        raise HTTPServerNotReady(f"HTTP Frontend is not ready and returns 503 from {endpoint}. Please check SiteRM Frontend")
                    if status_code != 200:
                        raise HTTPServerNotReady(f"HTTP Frontend is not ready to serve connections. Please check SiteRM Frontend. Error: {status_code} {reason_phrase} from {endpoint}")
                    if endpoint == "/api/ready":
                        if not isinstance(response, dict) or response.get("status") != "ready":
                            raise HTTPServerNotReady("HTTP Frontend is not ready to serve connections. Please check SiteRM Frontend.")
                    elif endpoint == "/api/alive":
                        if not isinstance(response, dict) or response.get("status") != "alive":
                            raise HTTPServerNotReady("HTTP Frontend is not alive. Please check SiteRM Frontend.")
                    # Here it means service is ready. break the loop
                    break
                except HTTPServerNotReady as ex:
                    print(str(ex))
                    if kwargscopy["retries"] == 0 and kwargscopy["raiseEx"]:
                        raise ex
                except Exception as e:
                    print(f"Exception while checking service readiness from {endpoint}: {str(e)}")
                    print(f"Full traceback: {traceback.format_exc()}")
                    if kwargscopy["retries"] == 0 and kwargscopy["raiseEx"]:
                        raise HTTPServerNotReady(f"Failed to check service readiness from {endpoint}: {str(e)}") from e
                if kwargscopy["retries"] > 0:
                    time.sleep(kwargscopy["sleep"])
            return func(self, *args, **kwargs)

        return wrapper

    return decorator


class Requests:
    """Main Requests class to handle HTTP requests."""

    def __init__(self, url="http://localhost", logger=None):
        """Initialize the Requests class with a URL and optional logger."""
        self.logger = logger
        self.useragent = f"SiteRM-{socket.gethostname()}"
        self.default_headers = {"Content-Type": "application/json", "Accept": "application/json", "User-Agent": self.useragent}
        self.host = sanitizeURL(url)
        checkServerUrl(self.host)

        self.session = httpx.Client(verify=self.__http_getCAPath(), timeout=60.0, follow_redirects=True)
        self.authsession = httpx.Client(verify=self.__http_getCAPath(), timeout=60.0, follow_redirects=True)
        self.notFEsession = httpx.Client(timeout=60.0, follow_redirects=True)
        self.bearertoken = None
        self.refreshtoken = None
        self.sessionid = None

    def close(self):
        """Close the HTTP sessions."""
        self.session.close()
        self.notFEsession.close()

    def _logMessage(self, message):
        """Log a message if logger is set."""
        if self.logger:
            self.logger.debug(message)
        else:
            print(message)

    @httpserviceready("/api/alive")
    def apiAlive(self):
        """Just a place holder for decorator check."""
        return True

    @httpserviceready("/api/ready")
    def apiReady(self):
        """Just a place holder for decorator check."""
        return True

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

    @staticmethod
    def __http_getCertKeyValue():
        """Get Certificate and Key Tuple."""
        cert, key = getKeyCertFromEnv()
        if not cert or not key:
            raise ValueError("Certificate or key not found in environment variables.")
        # Read file contents and return
        with open(cert, "r", encoding="utf-8") as fd:
            certval = fd.read()
        with open(key, "r", encoding="utf-8") as fd:
            keyval = fd.read()
        return certval, keyval

    @staticmethod
    def __http_getCAPath():
        """Get CA Path."""
        return getCAPathFromEnv() or True

    def _getNewBearerToken(self, auth_info):
        """Get a new Bearer token using the token endpoint."""
        if "token_endpoint" in auth_info and auth_info["token_endpoint"]:
            try:
                certval, keyval = self.__http_getCertKeyValue()
                response = self.authsession.request(method="POST",
                                                    url=auth_info["token_endpoint"],
                                                    headers={"Content-Type": "application/json"},
                                                    json={"certificate": certval})
                if response.status_code == 200:
                    # We get the challenge response, that needs to be completed to obtain the token
                    # Challenge can be solved only with the private key corresponding to the certificate
                    challengeResponse = response.json()
                    if challengeResponse:
                        # Sign the challenge with the private key
                        signature = signChallenge(challengeResponse, keyval)
                        # Send the signed challenge to the token endpoint to get the token
                        token_response = self.authsession.request(method="POST",
                                                                  url=challengeResponse["ref_url"],
                                                                  headers={"Content-Type": "application/json"},
                                                                  json={"signature": signature})
                        if token_response.status_code == 200:
                            resp_json = token_response.json()
                            self.bearertoken = resp_json.get("access_token", None)
                            self.refreshtoken = resp_json.get("refresh_token", None)
                            self.sessionid = resp_json.get("session_id", None)
                            if self.bearertoken:
                                self._logMessage("Successfully obtained new Bearer token.")
                else:
                    self._logMessage(f"Failed to obtain new Bearer token from {auth_info['auth_endpoint']}: {response.status_code} {response.reason_phrase}")
            except Exception as ex:
                self._logMessage(f"Failed to obtain new Bearer token from {auth_info['auth_endpoint']}: {ex}")
                self._logMessage(f"Full traceback: {traceback.format_exc()}")

    def _renewBearerToken(self, auth_info):
        """Renew the Bearer token by reading it from the environment variable"""
        # If refresh token is available, use it to get a new access token
        # If no refresh token is available, use the token endpoint to get a new access token via challenge
        # In case no refreshtoken or access_token, then use client cert as post
        # and get back the challenged url. Once challenge url received, make response challenge and return
        # the challenge response (that gives the token back)
        # Case 1. Token refresh if we have no access_token, but we have a refresh_token
        if self.refreshtoken and auth_info.get("refresh_token_endpoint"):
            # need to post sessionid and refresh_token
            # Call refresh token endpoint
            response = self.authsession.request(method="POST",
                                                url=auth_info["refresh_token_endpoint"],
                                                headers={"Content-Type": "application/json"},
                                                json={"sessionid": self.sessionid, "refresh_token": self.refreshtoken})
            if response.status_code == 200:
                resp_json = response.json()
                self.bearertoken = resp_json.get("access_token", None)
                self.refreshtoken = resp_json.get("refresh_token", None)
                if self.bearertoken:
                    self._logMessage("Successfully renewed Bearer token using refresh token.")
                else:
                    self._logMessage("Failed to find access_token in the response while renewing Bearer token using refresh token.")
        else:
            self._getNewBearerToken(auth_info)

    def _expiredBearerToken(self):
        """Check if the Bearer token is expired"""
        if not self.bearertoken:
            return True
        try:
            unverified_claims = jwt.decode(self.bearertoken, options={"verify_signature": False})
            exp = unverified_claims.get("exp", 0)
            current_time = getUTCnow()
            # Consider token expired if it's within 2 minutes of expiration
            if current_time >= exp - 120:
                return True
        except Exception:
            print("Failed to decode Bearer token. Assuming it is expired.")
            print(f"Full traceback: {traceback.format_exc()}")
            return True
        return False

    def _stripHostFromUrl(self, uri):
        """Get the full URL for the given URI."""
        parsed = urllib.parse.urlparse(uri)
        uri = urllib.parse.urlunparse(("", "", parsed.path, parsed.params, parsed.query, parsed.fragment))
        if parsed.scheme in ["http", "https"]:
            url = uri
        else:
            url = urllib.parse.urljoin(self.host, uri)
        return url

    def __makeSiteRMHTTPCall(self, url, verb, **kwargs):
        """Make an HTTP request to the SiteRM Frontend."""
        if not self.bearertoken or self._expiredBearerToken():
            response = self.session.request(method="GET", url=urllib.parse.urljoin(self.host, "/.well-known/openid-configuration"))
            if response.status_code == 200:
                auth_info = response.json()
                self._renewBearerToken(auth_info)
            else:
                self._logMessage(f"Failed to get authentication method from /.well-known/openid-configuration: {response.status_code} {response.reason_phrase}")
                raise HTTPException(f"Failed to get authentication method from /.well-known/openid-configuration: {response.status_code} {response.reason_phrase}")
        kwargs.setdefault("headers", {})
        kwargs["headers"]["Authorization"] = f"Bearer {self.bearertoken}"
        response = self.session.request(method=verb, url=url, headers=kwargs["headers"], json=kwargs["data"] if kwargs["json"] else None, data=None if kwargs["json"] else kwargs["data"])
        return response

    def http_makeRequest(self, verb, uri, **kwargs):
        """Make an HTTP request with the given parameters."""

        def getResponseContent(response, json):
            """Get response content based on json flag."""
            if json:
                return response.json()
            return response.text

        kwargs.setdefault("data", None)
        kwargs.setdefault("headers", None)
        kwargs.setdefault("json", True)
        kwargs.setdefault("SiteRMHTTPCall", True)
        if kwargs.get("useragent"):
            self.http_extendUserAgent(kwargs["useragent"])
        kwargs["headers"] = {**self.default_headers, **argValidity(kwargs["headers"], dict)}
        url = urllib.parse.urljoin(self.host, self._stripHostFromUrl(uri))
        try:
            if kwargs["SiteRMHTTPCall"]:
                response = self.__makeSiteRMHTTPCall(url, verb, **kwargs)
            # The only implementation of nonFESession is to fetch github config files
            # We are not passing headers or json data here
            else:
                response = self.notFEsession.request(method=verb, url=url)
            if response.status_code not in [200, 201, 202, 204, 304]:
                self._logMessage(f"HTTP request failed: {response.status_code} {response.reason_phrase} for URL: {url}")
                if kwargs["raiseEx"]:
                    raise HTTPException(f"HTTP request failed: {response.status_code} {response.reason_phrase} for URL: {url}")
                return getResponseContent(response, kwargs["json"]), response.status_code, response.reason_phrase, False
            return getResponseContent(response, kwargs["json"]), response.status_code, response.reason_phrase, False
        except HTTPException as e:
            return {"error": str(e)}, 500, "HTTP Exception", False
        except Exception as e:
            self._logMessage(f"Full traceback: {traceback.format_exc()}")
            return {"error": str(e)}, 500, "Internal Error", False
        finally:
            self.__http_resetUserAgent()

    @httpserviceready()
    def makeHttpCall(self, verb, url, SiteRMHTTPCall=True, **kwargs):
        """Put JSON to the Site FE."""
        kwargs.setdefault("retries", 3)
        kwargs.setdefault("raiseEx", True)
        kwargs.setdefault("sleep", 5)
        kwargs.setdefault("SiteRMHTTPCall", SiteRMHTTPCall)
        exc = []
        if verb not in ["GET", "POST", "PUT", "DELETE"]:
            raise ValueError(f"Invalid HTTP verb: {verb}. Must be one of GET, POST, PUT, DELETE.")
        while kwargs["retries"] > 0:
            kwargs["retries"] -= 1
            try:
                return self.http_makeRequest(verb, url, **kwargs)
            except Exception as ex:
                self._logMessage(f"Got Exception: {ex}. Will retry {kwargs['retries']} more times.")
                self._logMessage(f"Full traceback: {traceback.format_exc()}")
                exc.append(str(ex))
                if kwargs["retries"] == 0 and kwargs["raiseEx"]:
                    self._logMessage("No more retries left. Raising exception.")
                    raise Exception(f"Failed to make HTTP call after retries: {exc}") from ex
                if kwargs["retries"] != 0:
                    time.sleep(kwargs["sleep"])
        return "Failed after all retries", -1, "Failed after all retries", False
