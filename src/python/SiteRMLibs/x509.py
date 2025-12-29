#!/usr/bin/env python3
# pylint: disable=line-too-long
"""User/Application authentication using Cert or OIDC.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""
import json
import os
import re
import base64
import hashlib
import secrets
from datetime import datetime, timezone, timedelta

import jwt
from jwt.algorithms import RSAAlgorithm
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.hashes import Hash
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from SiteRMLibs.CustomExceptions import IssuesWithAuth, RequestWithoutCert
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import loadEnvFile, getUTCnow, generateRandomUUID


def getauthmethod():
    """Get the authentication method from environment."""
    loadEnvFile()
    mode = os.environ.get("AUTH_SUPPORT", "OIDC").upper()
    if mode not in ["OIDC", "X509"]:
        raise IssuesWithAuth(f"Unsupported authentication method: {mode}")
    return mode


def hash_token(token: str) -> str:
    """Hash refresh token for DB storage (SHA-256 hex)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_refresh_token() -> str:
    """
    Generate a cryptographically strong opaque refresh token.
    256 bits of entropy.
    """
    return secrets.token_urlsafe(32)


def base64url_encode_nopad(b: bytes) -> str:
    """ Base64url encode without padding. """
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def jwk_thumbprint(jwk: dict) -> str:
    """
    RFC 7638: JWK Thumbprint (SHA-256 over canonical JSON of members).
    For RSA: use { "e", "kty", "n" }.
    """
    ordered = {"e": jwk["e"], "kty": jwk["kty"], "n": jwk["n"]}
    canonical = json.dumps(ordered, separators=(",", ":"), sort_keys=True)
    digest = Hash(hashes.SHA256())
    digest.update(canonical.encode("utf-8"))
    thumb = digest.finalize()
    return base64url_encode_nopad(thumb)


def generate_jwk_from_public_pem(public_pem: str, alg: str = "RS256") -> dict:
    """Generate JWK from PEM-encoded public key."""
    if not os.path.exists(public_pem):
        raise RuntimeError(f"Public key file does not exist: {public_pem}")
    with open(public_pem, "r", encoding="utf-8") as f:
        cur_pem = f.read()
    pub = load_pem_public_key(cur_pem.encode())
    if not isinstance(pub, rsa.RSAPublicKey):
        raise RuntimeError("Only RSA public keys are supported")
    numbers = pub.public_numbers()
    n = base64url_encode_nopad(numbers.n.to_bytes((numbers.n.bit_length() + 7) // 8, "big"))
    e = base64url_encode_nopad(numbers.e.to_bytes((numbers.e.bit_length() + 7) // 8, "big"))
    jwk = {"kty": "RSA", "alg": alg, "use": "sig", "n": n, "e": e}
    jwk["kid"] = jwk_thumbprint({"kty": jwk["kty"], "n": jwk["n"], "e": jwk["e"]})
    return jwk


class PassHandler:
    """Password handler using Argon2 for hashing and verification."""

    def __init__(self):
        self.hasher = PasswordHasher(time_cost=int(os.environ.get("ARGON2_TIME_COST", 3)),
                                     memory_cost=int(os.environ.get("ARGON2_MEMORY_COST", 65536)),
                                     parallelism=int(os.environ.get("ARGON2_PARALLELISM", 4)),
                                     hash_len=int(os.environ.get("ARGON2_HASH_LEN", 32)))

    def hash_password(self, password: str) -> str:
        """Hash a password."""
        return self.hasher.hash(password)

    def verify_password(self, hashed_password: str, password: str) -> bool:
        """Verify a password against a hash."""
        try:
            return self.hasher.verify(hashed_password, password)
        except VerifyMismatchError:
            return False

    def needs_rehash(self, hashed_password: str) -> bool:
        """Check if a hashed password needs to be rehashed."""
        return self.hasher.check_needs_rehash(hashed_password)


class OIDCHandler:
    """OIDC handler to validate claims from Apache environment."""

    def __init__(self):
        """Init OIDC Handler"""
        loadEnvFile()
        self.enabled = getauthmethod() == "OIDC"
        if not self.enabled:
            return
        self.gitConf = getGitConfig()
        self.oidc_app_name = os.environ.get("OIDC_APP_NAME", "SITERM Token Issuer.")
        self.oidc_issuer = os.environ.get("OIDC_ISSUER", self.gitConf.get("general", "webdomain"))
        self.oidc_audience = os.environ.get("OIDC_AUDIENCE", self.gitConf.get("general", "webdomain"))
        self.oidc_algorithm = os.environ.get("OIDC_ALGORITHM", "RS256")
        self.oidc_token_lifetime_minutes = int(os.environ.get("OIDC_TOKEN_LIFETIME_MINUTES", "60"))
        self.oidc_leeway = int(os.environ.get("OIDC_LEEWAY", "60"))
        self.oidc_public_key = os.environ.get("OIDC_PUBLIC_KEY", None)
        self.oidc_private_key = os.environ.get("OIDC_PRIVATE_KEY", None)
        self.oidc_prev_public_key = os.environ.get("OIDC_PREV_PUBLIC_KEY", None)
        self.oidc_prev_private_key = os.environ.get("OIDC_PREV_PRIVATE_KEY", None)
        self.oidc_kid = None
        self.__startup__()
        self.__getjwks__()

    def __startup__(self):
        # Check all environment variables and that everything is set correctly. preset default values if not set
        # Check for current pub and priv keys
        if not self.enabled:
            return
        save_dir = os.getenv("RSA_DIR", "/opt/siterm/jwt_secrets")
        privateKeyPath = os.path.join(save_dir, "private_key.pem")
        publicKeyPath = os.path.join(save_dir, "public_key.pem")
        # Check public key
        if not self.oidc_public_key:
            if not os.path.exists(publicKeyPath):
                raise IssuesWithAuth("Missing OIDC_PUBLIC_KEY environment variable and public key file does not exist")
            self.oidc_public_key = publicKeyPath
        elif not os.path.exists(self.oidc_public_key):
            raise IssuesWithAuth("OIDC_PUBLIC_KEY environment variable is set but the file does not exist")
        # Check private key
        if not self.oidc_private_key:
            if not os.path.exists(privateKeyPath):
                raise IssuesWithAuth("Missing OIDC_PRIVATE_KEY environment variable and private key file does not exist")
            self.oidc_private_key = privateKeyPath
        elif not os.path.exists(self.oidc_private_key):
            raise IssuesWithAuth("OIDC_PRIVATE_KEY environment variable is set but the file does not exist")
        # Check for previous pub and priv keys for key rotation
        if self.oidc_prev_public_key and self.oidc_prev_private_key:
            prevPrivateKeyPath = os.path.join(save_dir, self.oidc_prev_private_key)
            prevPublicKeyPath = os.path.join(save_dir, self.oidc_prev_public_key)
            if not os.path.exists(prevPublicKeyPath):
                raise IssuesWithAuth("OIDC_PREV_PUBLIC_KEY environment variable is set but the file does not exist")
            if not os.path.exists(prevPrivateKeyPath):
                raise IssuesWithAuth("OIDC_PREV_PRIVATE_KEY environment variable is set but the file does not exist")
            self.oidc_prev_public_key = prevPublicKeyPath
            self.oidc_prev_private_key = prevPrivateKeyPath
        elif self.oidc_prev_public_key or self.oidc_prev_private_key:
            raise IssuesWithAuth("Both OIDC_PREV_PUBLIC_KEY and OIDC_PREV_PRIVATE_KEY must be set for key rotation")

    def __getjwks__(self):
        """Get JWKS."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        curjwks = generate_jwk_from_public_pem(self.oidc_public_key, self.oidc_algorithm)
        self.oidc_kid = curjwks.get("kid")
        self.jwks = {"keys": [curjwks]}
        if self.oidc_prev_public_key:
            prev_jwks = generate_jwk_from_public_pem(self.oidc_prev_public_key, self.oidc_algorithm)
            self.jwks["keys"].append(prev_jwks)
        kids = [k["kid"] for k in self.jwks["keys"]]
        if len(kids) != len(set(kids)):
            raise IssuesWithAuth("Duplicate kid detected in JWKS. Same Current and Previous keys for JWT?")

    def __get_key_from_jwks__(self, kid):
        """Find the key in JWKS that matches the kid"""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(json.dumps(key))
        raise IssuesWithAuth(f"No matching JWK found for kid={kid}")


    def getOpenIDConfiguration(self):
        """Get OpenID Connect configuration."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        return {
            "issuer": self.oidc_issuer,
            "jwks_uri": f"{self.oidc_issuer}/.well-known/jwks.json",
            "token_endpoint": f"{self.oidc_issuer}/issue_token",
            "authorization_endpoint": f"{self.oidc_issuer}/authorize",
            "response_types_supported": ["token", "id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": [self.oidc_algorithm],
        }

    def getJWKS(self):
        """Get JWKS."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        return self.jwks

    def getRefreshToken(self, **kwargs) -> str:
        """Get a refresh token for the specified user."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        # This returns unique uuid for the refresh token
        return generateRandomUUID()

    def getAccessToken(self, usersub: str, **kwargs) -> str:
        """Get an access token for the specified user."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        now = getUTCnow()
        exp = now + timedelta(minutes=self.oidc_token_lifetime_minutes)

        payload = {
            "iss": self.oidc_issuer,
            "aud": self.oidc_audience,
            "sub": usersub,
            "iat": int(now.timestamp()),
            "exp": int(exp.timestamp())}

        if "extra_claims" in kwargs:
            payload.update(kwargs["extra_claims"])

        headers = {"kid": self.oidc_kid, "typ": "JWT"}

        with open(self.oidc_private_key, "r", encoding="utf-8") as f:
            private_key = f.read()

        token = jwt.encode(payload, private_key, algorithm=self.oidc_algorithm, headers=headers)
        return token

    def validateOIDCInfo(self, request):
        """Validate OIDC claims and extract user identity & permissions."""
        if not self.enabled:
            raise IssuesWithAuth("OIDC is not enabled")
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            raise RequestWithoutCert("Unauthorized: Missing or invalid Bearer token")

        token = auth_header.replace("Bearer ", "")
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise IssuesWithAuth("Missing kid in token header")
        except Exception as ex:
            raise IssuesWithAuth(f"Invalid token header: {ex}") from ex

        public_key = self.__get_key_from_jwks__(kid)
        try:
            decoded = jwt.decode(token, public_key, algorithms=[self.oidc_algorithm], audience=self.oidc_audience, issuer=self.oidc_issuer, leeway=self.oidc_leeway)
            return decoded
        except jwt.ExpiredSignatureError as ex:
            raise IssuesWithAuth("Token expired") from ex
        except jwt.InvalidTokenError as ex:
            raise IssuesWithAuth(f"Invalid token: {ex}") from ex


class CertHandler:
    """Cert handler."""

    def __init__(self):
        loadEnvFile()
        self.enabled = getauthmethod() == "X509"
        if not self.enabled:
            return
        self.allowedCerts = {}
        self.allowedWCerts = {}
        self.loadTime = None
        self.loadAuthorized()
        self.gitConf = getGitConfig()

    def loadAuthorized(self):
        """Load all authorized users for FE from git."""
        if not self.enabled:
            return
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


    def getCertInfo(self, request):
        """Get certificate info."""
        if not self.enabled:
            raise IssuesWithAuth("X509 is not enabled")
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
        if not self.enabled:
            raise IssuesWithAuth("X509 is not enabled")
        if certinfo["fullDN"] in self.allowedCerts:
            return self.allowedCerts[certinfo["fullDN"]]
        for wildcarddn, userinfo in self.allowedWCerts.items():
            if re.match(wildcarddn, certinfo["fullDN"]):
                return userinfo
        print(f"User DN {certinfo['fullDN']} is not in authorized list. Full info: {certinfo}")
        raise IssuesWithAuth("Issues with permissions. Check backend logs.")

    def validateCertificate(self, request):
        """Validate certificate validity."""
        if not self.enabled:
            raise IssuesWithAuth("X509 is not enabled")
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
