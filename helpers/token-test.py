#!/usr/bin/env python3
import sys
import json
import base64
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa, ec, padding
from cryptography.hazmat.primitives.serialization import load_pem_private_key


# ============================
# configuration / inputs
# ============================
SERVER = sys.argv[1]                 # https://
CERT_PATH = Path(sys.argv[2])        # public cert (pem)
PRIVATE_KEY_PATH = Path(sys.argv[3]) # private key (pem)

MODELS_ENDPOINT = "/api/T2_US_SDSC_DEV/models?current=true&summary=false&encode=false"

WHOAMI_ENDPOINT = "/auth/whoami"
TOKEN_ENDPOINT = "/m2m/token"
REFRESH_ENDPOINT = "/m2m/token/refresh"

TIMEOUT = 30


# ============================
# helpers
# ============================
def whoami(client: httpx.Client) -> dict:
    """
    Returns identity of user from validated token.
    """
    try:
        url = SERVER + WHOAMI_ENDPOINT
        r = client.get(url)
        r.raise_for_status()
        data = r.json()
        print("== whoami ==")
        print(json.dumps(data, indent=2))
        return data
    except httpx.HTTPError as ex:
        print(f"Error during whoami: {ex}")
        return {}

def preflight(client: httpx.Client) -> dict:
    """
    Mandatory call before every auth transition.
    Uses Bearer token if present.
    """
    whoami(client)
    try:
        url = SERVER + MODELS_ENDPOINT
        r = client.get(url)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as ex:
        print(f"Error during preflight: {ex}")
        return {}

def sign_challenge(challenge_b64: str, private_key_pem: bytes) -> str:
    """
    Sign base64-encoded challenge using RSA or EC private key.
    """
    challenge = base64.b64decode(challenge_b64)
    key = load_pem_private_key(private_key_pem, password=None)

    if isinstance(key, rsa.RSAPrivateKey):
        signature = key.sign(
            challenge,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH,
            ),
            hashes.SHA256(),
        )
    elif isinstance(key, ec.EllipticCurvePrivateKey):
        signature = key.sign(
            challenge,
            ec.ECDSA(hashes.SHA256()),
        )
    else:
        raise RuntimeError("Unsupported private key type")

    return base64.b64encode(signature).decode("utf-8")


# ============================
# main flow
# ============================
def main():
    cert_text = CERT_PATH.read_text(encoding="utf-8")
    private_key_bytes = PRIVATE_KEY_PATH.read_bytes()

    with httpx.Client(timeout=TIMEOUT) as client:

        # --------------------------------------------------
        # 1. preflight (unauthenticated)
        # --------------------------------------------------
        print("== preflight (unauthenticated) ==")
        models = preflight(client)
        print(json.dumps(models, indent=2))

        # --------------------------------------------------
        # 2. request challenge
        # --------------------------------------------------
        print("\n== request challenge ==")
        r = client.post(
            SERVER + TOKEN_ENDPOINT,
            json={"certificate": cert_text},
        )
        r.raise_for_status()
        challenge_resp = r.json()
        print(json.dumps(challenge_resp, indent=2))

        # --------------------------------------------------
        # 3. sign challenge
        # --------------------------------------------------
        signature = sign_challenge(
            challenge_resp["challenge"],
            private_key_bytes,
        )

        # --------------------------------------------------
        # 4. preflight before token exchange
        # --------------------------------------------------
        print("\n== preflight (before token exchange) ==")
        preflight(client)

        # --------------------------------------------------
        # 5. exchange signature for tokens
        # --------------------------------------------------
        print("\n== exchange signature for token ==")
        r = client.post(
            challenge_resp["ref_url"],
            json={"signature": signature},
        )
        r.raise_for_status()
        token_resp = r.json()

        # IMPORTANT: attach Bearer token
        client.headers["Authorization"] = f"Bearer {token_resp['access_token']}"

        print(json.dumps(token_resp, indent=2))

        # --------------------------------------------------
        # 6. preflight with Bearer token
        # --------------------------------------------------
        print("\n== preflight (authenticated) ==")
        preflight(client)

        # --------------------------------------------------
        # 7. refresh token
        # --------------------------------------------------
        print("\n== use refresh token to get new access token ==")
        r = client.post(
            SERVER + REFRESH_ENDPOINT,
            json={
                "session_id": token_resp["session_id"],
                "refresh_token": token_resp["refresh_token"],
            },
        )
        r.raise_for_status()
        refreshed = r.json()

        client.headers["Authorization"] = f"Bearer {refreshed['access_token']}"

        # --------------------------------------------------
        # 8. preflight with refreshed Bearer token
        # --------------------------------------------------
        print("\n== preflight (authenticated with refreshed token) ==")
        preflight(client)

if __name__ == "__main__":
    main()