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
import os
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    apiReadDeps,
    apiWriteDeps,
    apiPublicDeps,
    checkSite,
    forbidExtraQueryParams,
    StrictBool
)
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.CustomExceptions import BadRequestError
from SiteRMLibs.DefaultParams import LIMIT_DEFAULT, LIMIT_MAX, LIMIT_MIN
from SiteRMLibs.MainUtilities import (
    dumpFileContentAsJson,
    generateRandomUUID,
    getFileContentAsJson,
    getstartupconfig,
    getUTCnow,
)
from SiteRMLibs.Validator import validator

router = APIRouter()

startupConfig = getstartupconfig()

class LoginItem(BaseModel):
    """Login Item Model."""
    # pylint: disable=too-few-public-methods
    username: constr(strip_whitespace=True, min_length=1, max_length=255)
    password: constr(strip_whitespace=True, min_length=1, max_length=255)

class M2MLoginItem(BaseModel):
    """M2M Login Item Model."""

    # pylint: disable=too-few-public-methods
    client_id: constr(strip_whitespace=True, min_length=1, max_length=255)
    client_secret: constr(strip_whitespace=True, min_length=1, max_length=4096)

# ==========================================================
# /api/authentication-method
# ==========================================================
@router.get(
    "/auth/method",
    summary="Get Authentication Method",
    description=("Returns the authentication method used by the frontend (X509 or OIDC)."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "Authentication method successfully returned.", "content": {"application/json": {"example": {"auth_method": "X509"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getAuthMethod(request: Request, deps=Depends(apiPublicDeps), _forbid=Depends(forbidExtraQueryParams())):
    """
    Get the authentication method used by the frontend.
    - Returns the authentication method in use (X509 or OIDC).
    """
    if not deps["oidcHandler"].enabled:
        auth_method = "X509"
        return APIResponse.genResponse(request, {"auth_method": auth_method, "auth_endpoint": ""})
    else:
        auth_method = "OIDC"
        openidConfig = deps["oidcHandler"].getOpenIDConfiguration()
        return APIResponse.genResponse(request, {"auth_method": auth_method, "auth_endpoint": openidConfig})    

# ==========================================================
#POST /auth/login  Authenticate human user;
# ==========================================================
@router.post("/auth/login", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def login(request: Request, item: LoginItem, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Authenticate human user
    """
    try:
        # Need to use username and hash lib;
        # Returns Set-Cookie header with refresh token
        #Set-Cookie: refresh_token=RT1; HttpOnly; Secure; SameSite=Strict; Path=/auth/refresh; Max-Age=2592000
        user = deps["dbI"].get("users", limit=1, search=[["username", item.username], ["password", item.password]])
        if user:
            return APIResponse(success=True, data={"message": "Login successful"})
        else:
            raise BadRequestError("Invalid username or password")
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================================
#POST /auth/logout Logout human user;
# ==========================================================
@router.post("/auth/logout", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def logout(request: Request, payload: Dict[str, Any] = Depends(apiReadDeps)):
    """
    Logout human user
    """
    try:
        # Your logout logic here
        return APIResponse(success=True, data={"message": "Logout successful"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
# ==========================================================
#GET /auth/whoami Returns identity of whoami;
# ==========================================================
@router.get("/auth/whoami", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def whoami(request: Request, payload: Dict[str, Any] = Depends(apiReadDeps)):
    """
    Returns identity of whoami
    """
    try:
        # Your whoami logic here
        return APIResponse(success=True, data={"message": "Whoami successful"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================================
#GET /auth/refresh Returns refresh token;
# ==========================================================
@router.get("/auth/refresh", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def refresh(request: Request, payload: Dict[str, Any] = Depends(apiReadDeps)):
    """
    Returns refresh token
    """
    try:
        # Your refresh token logic here
        return APIResponse(success=True, data={"message": "Refresh token retrieved"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# ==========================================================
#POST /token Get Token based on Cert challenge
# ==========================================================
@router.post("/m2m/token", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def token(request: Request, payload: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Request new token challenge
    """
    try:
        # Your token logic here
        return APIResponse(success=True, data={"message": "Token retrieved"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================================
#POST /m2m/token/refresh -> access token (rotated refresh)
# ==========================================================
@router.post("/m2m/token/refresh", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def token_refresh(request: Request, item: M2MLoginItem, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Refresh access token (rotated refresh)
    """
    try:
        # Your token refresh logic here
        return APIResponse(success=True, data={"message": "Token refreshed"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/m2m/token/{challenge_id}", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def token_challenge(request: Request, deps: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Challenge reply
    """
    try:
        # Your token challenge logic here
        return APIResponse(success=True, data={"message": "Token challenge retrieved"})
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

# ==========================================================
#GET /.well-known/jwks.json
# ==========================================================
@router.get("/.well-known/jwks.json", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def jwks(request: Request, payload: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Get JSON Web Key Set
    """
    try:
        jwkso = payload["oidcHandler"].getJWKS()
        return APIResponse(success=True, data=jwkso)
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e

# ==========================================================
#GET /.well-known/openid-configuration
# ==========================================================
@router.get("/.well-known/openid-configuration", response_model=APIResponse, responses=DEFAULT_RESPONSES)
async def openid_configuration(request: Request, payload: Dict[str, Any] = Depends(apiPublicDeps)):
    """
    Get OpenID Configuration
    """
    try:
        openid_config = payload["oidcHandler"].getOpenIDConfiguration()
        return APIResponse(success=True, data=openid_config)
    except BadRequestError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e