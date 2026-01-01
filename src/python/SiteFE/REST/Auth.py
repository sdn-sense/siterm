#!/usr/bin/env python3
# pylint: disable=line-too-long, too-many-arguments
"""
Debug API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""

import traceback
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    apiPublicDeps,
    apiReadDeps,
    rateLimitIp,
)
from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.MainUtilities import generateRandomUUID, getUTCnow

router = APIRouter()


class LoginItem(BaseModel):
    """Login Item Model."""

    # pylint: disable=too-few-public-methods
    username: constr(strip_whitespace=True, min_length=1, max_length=255)
    password: constr(strip_whitespace=True, min_length=1, max_length=255)


class M2MLoginItem(BaseModel):
    """M2M Login Item Model."""

    # pylint: disable=too-few-public-methods
    session_id: constr(strip_whitespace=True, min_length=1, max_length=255)
    refresh_token: constr(strip_whitespace=True, min_length=1, max_length=4096)


class X509LoginItem(BaseModel):
    """X509 Login Item Model."""

    # pylint: disable=too-few-public-methods
    certificate: constr(strip_whitespace=True, min_length=1, max_length=4096)


class M2MChallengeItem(BaseModel):
    """M2M Challenge Item Model."""

    # pylint: disable=too-few-public-methods
    signature: constr(strip_whitespace=True, min_length=1, max_length=4096)


# ==========================================================
# POST /auth/login  Authenticate human user;
# ==========================================================
@router.post("/auth/login", responses=DEFAULT_RESPONSES)
@rateLimitIp(maxRequests=5, windowSeconds=60)
async def login(request: Request, item: LoginItem, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """Authenticate human user"""
    try:
        pass_handler = deps["passHandler"]
        user = deps["dbI"].get("users", limit=1, search=[["username", item.username]])
        if not user:
            raise BadRequestError("Invalid username or password")
        if user[0].get("disabled"):
            raise BadRequestError("Invalid username or password")
        if not pass_handler.verify_password(user[0]["password_hash"], item.password):
            raise BadRequestError("Invalid username or password")

        if pass_handler.needs_rehash(user[0]["password_hash"]):
            deps["dbI"].update(
                "users",
                search=[["id", user[0]["id"]]],
                update={"password_hash": pass_handler.hash_password(item.password)},
            )

        refresh_token = deps["authHandler"].getRefreshToken()
        refresh_token_hash = deps["authHandler"].hash_token(refresh_token)

        deps["dbI"].insert(
            "refresh_tokens",
            {
                "session_id": generateRandomUUID(),
                "token_hash": refresh_token_hash,
                "expires_at": getUTCnow() + deps["authHandler"].refresh_token_ttl,
                "revoked": False,
                "rotated_from": None,
            },
        )

        # TODO: Review how to pass the cookies to the response
        response = APIResponse.genResponse(
            request,
            {
                "message": "Login successful",
                "user": {"id": user[0]["id"], "username": user[0]["username"]},
            },
        )

        response.set_cookie(
            key="refresh_token",
            value=refresh_token,
            httponly=True,
            secure=True,
            samesite="strict",
            max_age=int(deps["authHandler"].refresh_token_ttl),
        )
        return response
    except BadRequestError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e)) from e


# ==========================================================
# GET /auth/whoami Returns identity of whoami;
# ==========================================================
@router.get("/auth/whoami", responses=DEFAULT_RESPONSES)
@rateLimitIp(maxRequests=5, windowSeconds=60)
async def whoami(request: Request, deps: Dict[str, Any] = Depends(apiReadDeps)):
    """
    Returns identity of whoami
    """
    try:
        # TODO: Implement whoami logic
        user = deps.get("user")
        print(f"Whoami user: {user}")
        if not user:
            raise BadRequestError("User not authenticated")
        return APIResponse.genResponse(request, {"message": "Whoami successful", "user": "Not implemented"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


# ==========================================================
# POST /token Get Token based on Cert challenge
# ==========================================================
@router.post("/m2m/token", responses=DEFAULT_RESPONSES)
@rateLimitIp(maxRequests=5, windowSeconds=60)
async def token(request: Request, item: X509LoginItem, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Request new token challenge
    """
    try:
        challenge = deps["authHandler"].generate_challenge(item.certificate)
        challenge["ref_url"] = f"/m2m/token/{challenge['challenge_id']}"
        return APIResponse.genResponse(request, challenge)
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==========================================================
# POST /m2m/token/refresh -> access token (rotated refresh)
# ==========================================================
@router.post("/m2m/token/refresh", responses=DEFAULT_RESPONSES)
@rateLimitIp(maxRequests=5, windowSeconds=60)
async def token_refresh(request: Request, item: M2MLoginItem, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Refresh access token (rotated refresh)
    """
    try:
        # Check if refresh token is present in the database
        refreshRecord = deps["dbI"].get(
            "refresh_tokens",
            limit=1,
            search=[
                ["token_hash", deps["authHandler"].hash_token(item.refresh_token)],
                ["session_id", item.session_id],
            ],
        )
        if not refreshRecord:
            raise BadRequestError("Refresh token is invalid or expired")
        # Check if the refresh token has expired or been revoked
        if refreshRecord[0]["revoked"] or refreshRecord[0]["expires_at"] < getUTCnow():
            raise BadRequestError("Refresh token is invalid or expired")
        # Get new token, new refresh token, delete old refresh token
        access_token = deps["authHandler"].getAccessToken(refreshRecord[0]["user"])
        new_refresh_token = deps["authHandler"].getRefreshToken()
        deps["dbI"].delete(
            "refresh_tokens",
            [["token_hash", deps["authHandler"].hash_token(item.refresh_token)]],
        )
        out = {
            "token_hash": deps["authHandler"].hash_token(new_refresh_token),
            "session_id": item.session_id,
            "expires_at": getUTCnow() + deps["authHandler"].refresh_token_ttl,
            "revoked": False,
            "rotated_from": refreshRecord[0]["token_hash"],
        }
        deps["dbI"].insert("refresh_tokens", [out])
        return APIResponse.genResponse(
            request,
            {
                "session_id": item.session_id,
                "access_token": access_token,
                "refresh_token": new_refresh_token,
                "token_type": "Bearer",
            },
        )
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e


@router.post("/m2m/token/{challenge_id}", responses=DEFAULT_RESPONSES)
@rateLimitIp(maxRequests=5, windowSeconds=60)
async def token_challenge(
    request: Request,
    challenge_id: str,
    item: M2MChallengeItem,
    deps: Dict[str, Any] = Depends(apiPublicDeps),
):
    """
    Challenge reply
    """
    try:
        verified, user = deps["authHandler"].verify_challenge(challenge_id, item.signature)

        if not verified:
            raise BadRequestError("Invalid challenge outcome")

        access_token = deps["authHandler"].getAccessToken(user)
        refresh_token = deps["authHandler"].getRefreshToken()
        out = {
            "token_hash": deps["authHandler"].hash_token(refresh_token),
            "session_id": challenge_id,
            "expires_at": getUTCnow() + deps["authHandler"].refresh_token_ttl,
            "revoked": False,
            "rotated_from": None,
        }
        deps["dbI"].insert("refresh_tokens", [out])

        return APIResponse.genResponse(
            request,
            {
                "session_id": challenge_id,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "Bearer",
            },
        )
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=400, detail=str(e)) from e


# ==========================================================
# GET /.well-known/jwks.json
# ==========================================================
@router.get("/.well-known/jwks.json", responses=DEFAULT_RESPONSES)
async def jwks(request: Request, payload: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Get JSON Web Key Set
    """
    try:
        jwkso = payload["authHandler"].getJWKS()
        return APIResponse.genResponse(request, jwkso)
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e


# ==========================================================
# GET /.well-known/openid-configuration
# ==========================================================
@router.get("/.well-known/openid-configuration", responses=DEFAULT_RESPONSES)
async def openid_configuration(request: Request, payload: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Get OpenID Configuration
    """
    try:
        openid_config = payload["authHandler"].getOpenIDConfiguration()
        return APIResponse.genResponse(request, openid_config)
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    except Exception as e:
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)) from e
