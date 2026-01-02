#!/usr/bin/env python3
# pylint: disable=line-too-long
"""User/Application authentication using User/Pass or token.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2016 California Institute of Technology
Date                    : 2019/10/01
"""

import base64
import hashlib
import json
import os
import re
import secrets
import traceback
import pprint
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
from cryptography.hazmat.primitives.hashes import Hash
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from cryptography.x509.oid import NameOID
from cryptography.x509.store import X509Store, X509StoreContext
from jwt.algorithms import RSAAlgorithm
from SiteRMLibs.CustomExceptions import (
    BadRequestError,
    IssuesWithAuth,
    RequestWithoutCert,
)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    dumpFileContentAsJson,
    getFileContentAsJson,
    getTempDir,
    getUTCnow,
    loadEnvFile,
    removeFile,
)

OID_SHORT_NAMES = {
    NameOID.COUNTRY_NAME: "C",
    NameOID.STATE_OR_PROVINCE_NAME: "ST",
    NameOID.LOCALITY_NAME: "L",
    NameOID.ORGANIZATION_NAME: "O",
    NameOID.ORGANIZATIONAL_UNIT_NAME: "OU",
    NameOID.COMMON_NAME: "CN",
}


def load_cert(cert_pem: str):
    """Load a certificate from a PEM-encoded certificate."""
    return x509.load_pem_x509_certificate(cert_pem.encode())


def name_to_openssl(name: x509.Name) -> str:
    """Convert an x509.Name object to an OpenSSL-style string."""
    parts = []
    for attr in name:
        # pylint: disable=protected-access
        short = OID_SHORT_NAMES.get(attr.oid, attr.oid._name)
        parts.append(f"{short}={attr.value}")
    return "/" + "/".join(parts)


def load_ca_store(ca_dir):
    store = X509Store()
    for fname in os.listdir(ca_dir):
        if not fname.endswith(".pem"):
            continue
        path = os.path.join(ca_dir, fname)
        try:
            with open(path, "rb") as f:
                ca_cert = x509.load_pem_x509_certificate(f.read())
                store.add_cert(ca_cert)
        except Exception:
            # Ignore broken / policy / non-cert files
            continue
    return store

def verify_cert_chain(cert, ca_store):
    """
    cert  : leaf x509.Certificate
    ca_store : X509Store containing trusted CA certificates
    """
    ctx = X509StoreContext(ca_store, cert)
    ctx.verify_certificate()  # raises on failure

def load_cert_info(cert):
    """Load certificate information into a dictionary."""
    out = {}
    out["issuer"] = name_to_openssl(cert.issuer)
    out["subject"] = name_to_openssl(cert.subject)
    out["notBefore"] = int(cert.not_valid_before_utc.timestamp())
    out["notAfter"] = int(cert.not_valid_after_utc.timestamp())
    out["fullDN"] = f"{out['issuer']}{out['subject']}"
    return out


def get_challenge_record(challenge_id: str):
    """Retrieve a challenge record by its ID."""
    tempfile = f"{getTempDir()}/m2m/{challenge_id}.json"
    if not os.path.exists(tempfile):
        return None
    return getFileContentAsJson(tempfile)


def base64url_encode_nopad(b: bytes) -> str:
    """Base64url encode without padding."""
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


class AuthHandler:
    """Authentication handler to manage user/pass and token-based authentication."""

    def __init__(self):
        loadEnvFile()
        # Password handling parameters
        self.hasher = PasswordHasher(
            time_cost=int(os.environ.get("ARGON2_TIME_COST", 3)),
            memory_cost=int(os.environ.get("ARGON2_MEMORY_COST", 65536)),
            parallelism=int(os.environ.get("ARGON2_PARALLELISM", 4)),
            hash_len=int(os.environ.get("ARGON2_HASH_LEN", 32)),
        )
        # OIDC and JWKS handling
        self.gitConf = getGitConfig()
        self.oidc_app_name = os.environ.get("OIDC_APP_NAME", "SITERM Token Issuer.")
        self.oidc_issuer = os.environ.get("OIDC_ISSUER", self.gitConf.get("general", "webdomain"))
        self.oidc_audience = os.environ.get("OIDC_AUDIENCE", self.gitConf.get("general", "webdomain"))
        self.oidc_algorithm = os.environ.get("OIDC_ALGORITHM", "RS256")
        self.oidc_token_lifetime_minutes = int(os.environ.get("OIDC_TOKEN_LIFETIME_MINUTES", "60"))
        self.refresh_token_ttl = timedelta(days=int(os.environ.get("REFRESH_TOKEN_TTL_DAYS", "7"))).total_seconds()
        self.oidc_leeway = int(os.environ.get("OIDC_LEEWAY", "60"))
        self.oidc_public_key = os.environ.get("OIDC_PUBLIC_KEY", None)
        self.oidc_private_key = os.environ.get("OIDC_PRIVATE_KEY", None)
        self.oidc_prev_public_key = os.environ.get("OIDC_PREV_PUBLIC_KEY", None)
        self.oidc_prev_private_key = os.environ.get("OIDC_PREV_PRIVATE_KEY", None)
        self.oidc_ca_store = load_ca_store(os.environ.get("OIDC_CA_DIR", "/etc/grid-security/truststore/"))
        self.oidc_kid = None
        self.__startup__()
        self.__getjwks__()

        # Certificate handling
        self.allowedCerts = {}
        self.allowedWCerts = {}
        self.loadTime = None
        self.loadAuthorized()
        self.gitConf = getGitConfig()

    def generate_challenge(self, input_cert: str):
        """Generate a challenge for the given certificate."""
        # Challenge storage is filesystem-based (tmp), that breaks if multiple instances are running
        # or if container is restarted
        try:
            cert = load_cert(input_cert)
            verify_cert_chain(cert, self.oidc_ca_store)
            certinfo = load_cert_info(cert)
            self.validateCertificate(certinfo)

            challenge_b64 = base64.b64encode(secrets.token_bytes(32)).decode("utf-8")

            challenge_id = secrets.token_hex(16)

            tempfile = f"{getTempDir()}/m2m/{challenge_id}.json"
            expires_at = getUTCnow() + 60

            dumpFileContentAsJson(
                tempfile,
                {
                    "challenge_id": challenge_id,
                    "challenge": challenge_b64,
                    "input_cert": input_cert,
                    "expires_at": expires_at,
                },
            )
            return {
                "challenge_id": challenge_id,
                "challenge": challenge_b64,
                "expires_at": expires_at,
            }
        except Exception as e:
            print(f"Error generating challenge: {e}")
            print(f"Full traceback: {traceback.format_exc()}")
            raise BadRequestError("Failed to generate challenge") from e

    def verify_challenge(self, challenge_id: str, signature_b64: str):
        """Verify a challenge using the provided signature."""
        record = get_challenge_record(challenge_id)
        if not record:
            print(f"Challenge {challenge_id} not found")
            return False, None
        if record["expires_at"] < getUTCnow():
            print(f"Challenge {challenge_id} has expired")
            return False, None
        try:
            cert = load_cert(record["input_cert"])
            verify_cert_chain(cert, self.oidc_ca_store)
            certinfo = load_cert_info(cert)
            user = self.validateCertificate(certinfo)
            public_key = cert.public_key()
            challenge = base64.b64decode(record["challenge"])
            signature = base64.b64decode(signature_b64)

            if isinstance(public_key, ec.EllipticCurvePublicKey):
                public_key.verify(
                    signature,
                    challenge,
                    ec.ECDSA(hashes.SHA256()),
                )
            else:
                public_key.verify(
                    signature,
                    challenge,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
        except InvalidSignature as ex:
            print(f"Invalid signature: {ex}")
            return False, None
        except Exception as ex:
            print(f"Error verifying challenge: {ex}")
            print(f"Full traceback: {traceback.format_exc()}")
            return False, None
        finally:
            tempfile = f"{getTempDir()}/m2m/{challenge_id}.json"
            removeFile(tempfile)
        return True, user

    # =========================================================
    # Password handling
    # =========================================================

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

    # =========================================================
    # OIDC and JWKS handling
    # =========================================================

    def __startup__(self):
        # Check all environment variables and that everything is set correctly. preset default values if not set
        # Check for current pub and priv keys
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
        for key in self.jwks.get("keys", []):
            if key.get("kid") == kid:
                return RSAAlgorithm.from_jwk(json.dumps(key))
        raise IssuesWithAuth(f"No matching JWK found for kid={kid}")

    def getOpenIDConfiguration(self):
        """Get OpenID Connect configuration."""
        return {
            "issuer": self.oidc_issuer,
            "jwks_uri": f"{self.oidc_issuer}/.well-known/jwks.json",
            "token_endpoint": f"{self.oidc_issuer}/m2m/token",
            "refresh_token_endpoint": f"{self.oidc_issuer}/m2m/token/refresh",
            "response_types_supported": ["token", "id_token"],
            "subject_types_supported": ["public"],
            "id_token_signing_alg_values_supported": [self.oidc_algorithm],
        }

    def getJWKS(self):
        """Get JWKS."""
        return self.jwks

    def getRefreshToken(self, **_kwargs) -> str:
        """Get a refresh token for the specified user."""
        # This returns unique uuid for the refresh token
        return secrets.token_urlsafe(32)

    def getAccessToken(self, usersub: str, **kwargs) -> str:
        """Get an access token for the specified user."""
        now = getUTCnow()
        exp = now + timedelta(minutes=self.oidc_token_lifetime_minutes).total_seconds()

        payload = {
            "iss": self.oidc_issuer,
            "aud": self.oidc_audience,
            "sub": usersub,
            "iat": int(now),
            "exp": int(exp),
        }

        if "extra_claims" in kwargs:
            payload.update(kwargs["extra_claims"])

        headers = {"kid": self.oidc_kid, "typ": "JWT"}

        with open(self.oidc_private_key, "r", encoding="utf-8") as f:
            private_key = f.read()

        token = jwt.encode(payload, private_key, algorithm=self.oidc_algorithm, headers=headers)
        return token

    @staticmethod
    def hash_token(token: str):
        """Hash refresh token for DB storage (SHA-256 hex)."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def extractToken(self, request):
        """Extract the Bearer token from the request."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or not auth_header.startswith("Bearer "):
            raise RequestWithoutCert("Unauthorized: Missing or invalid Bearer token")
        token = auth_header.replace("Bearer ", "")
        if not token:
            raise RequestWithoutCert("Unauthorized: Missing or invalid Bearer token")
        return token

    def validateToken(self, token):
        """Validate OIDC claims and extract user identity & permissions."""
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
            if not kid:
                raise IssuesWithAuth("Missing kid in token header")
        except Exception as ex:
            print(f"Full traceback: {traceback.format_exc()}")
            raise IssuesWithAuth(f"Invalid token header: {ex}") from ex

        public_key = self.__get_key_from_jwks__(kid)
        try:
            decoded = jwt.decode(
                token,
                public_key,
                algorithms=[self.oidc_algorithm],
                audience=self.oidc_audience,
                issuer=self.oidc_issuer,
                leeway=self.oidc_leeway,
            )
        except jwt.ExpiredSignatureError as ex:
            raise IssuesWithAuth("Token expired") from ex
        except jwt.InvalidTokenError as ex:
            raise IssuesWithAuth(f"Invalid token: {ex}") from ex
        return decoded

    # ==========================================
    # Certificate handling
    # ==========================================

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
            print(f"Allowed Certs: {pprint.pformat(self.allowedCerts)}")
            print(f"Allowed Wildcard Certs: {pprint.pformat(self.allowedWCerts)}")

    def checkAuthorized(self, certinfo):
        """Check if user is authorized."""
        self.loadAuthorized()
        if certinfo["fullDN"] in self.allowedCerts:
            return self.allowedCerts[certinfo["fullDN"]]
        for wildcarddn, userinfo in self.allowedWCerts.items():
            if re.match(wildcarddn, certinfo["fullDN"]):
                return userinfo
        print(f"User DN {certinfo['fullDN']} is not in authorized list. Full info: {certinfo}")
        raise IssuesWithAuth("Issues with permissions. Check backend logs.")

    def validateCertificate(self, certinfo):
        """Validate certificate validity."""
        timestamp = getUTCnow()
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
