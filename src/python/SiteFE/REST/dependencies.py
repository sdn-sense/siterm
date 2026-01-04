#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Dependencies for SiteFE REST API FastAPI application.
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""

import asyncio
import time
import traceback
from collections import defaultdict, deque
from functools import wraps
from typing import Any, Dict, List, Union

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic_core import core_schema
from SiteFE.PolicyService import stateMachine as ST
from SiteRMLibs.CustomExceptions import (
    IssuesWithAuth,
    ModelNotFound,
    RequestWithoutCert,
)
from SiteRMLibs.GitConfig import getGitConfig
from SiteRMLibs.MainUtilities import (
    encodebase64,
    firstRunFinished,
    getAllFileContent,
    getDBConnObj,
    getUTCnow,
)
from SiteRMLibs.x509 import AuthHandler

DEP_CONFIG = getGitConfig()
DEP_DBOBJ = getDBConnObj()
DEP_STATE_MACHINE = ST.StateMachine(DEP_CONFIG)
AUTH_HANDLER = AuthHandler()

BEARER_SCHEME = HTTPBearer(scheme_name="BearerAuth", description="JWT Bearer token obtained from /auth/login")

DEFAULT_RESPONSES = {
    401: {
        "description": "Unauthorized",
        "content": {"application/json": {"example": {"detail": "Not authorized to access this resource"}}},
    },
    403: {
        "description": "Forbidden",
        "content": {"application/json": {"example": {"detail": "Access to this resource is forbidden"}}},
    },
    422: {
        "description": "Unprocessable Entity",
        "content": {"application/json": {"example": {"detail": "Request parameters are invalid"}}},
    },
    500: {
        "description": "Internal Server Error",
        "content": {"application/json": {"example": {"detail": "Internal server error"}}},
    },
    503: {
        "description": "Service Unavailable",
        "content": {"application/json": {"example": {"detail": "Service temporarily unavailable"}}},
    },
}


def depGetDBObj():
    """Get the database connection object."""
    return DEP_DBOBJ


def depGetConfig():
    """Dependency to get the configuration object."""
    return DEP_CONFIG


def depGetStateMachine():
    """Dependency to get the state machine object."""
    return DEP_STATE_MACHINE


def depGetAuthHandler():
    """Dependency to get the authentication handler object."""
    return AUTH_HANDLER


def loguseraction(request, userinfo):
    """Print user action to log."""
    client_host = request.client.host if request.client else "unknown"
    method = request.method
    url = str(request.url)
    timestamp = getUTCnow()
    log_entry = {
        "timestamp": timestamp,
        "client_host": client_host,
        "method": method,
        "url": url,
        "userinfo": userinfo,
    }
    print(f"User Action Log: {log_entry}")


async def depAuthenticate(request: Request):
    """Dependency to authenticate the user via certificate or OIDC."""
    auth_handler = AUTH_HANDLER
    try:
        token = auth_handler.extractToken(request)
        userInfo = auth_handler.validateToken(token)
        loguseraction(request, {"user_info": userInfo})
        return {"user_info": userInfo}
    except (IssuesWithAuth, RequestWithoutCert) as ex:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized",
            headers={"WWW-Authenticate": "Bearer"},
        ) from ex
    except Exception as ex:
        loguseraction(request, {"exception": str(ex)})
        print(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        ) from ex


def depGetModelContent(dbentry, **kwargs):
    """Get model content based on db entry."""
    rettype = kwargs.get("rdfformat", "turtle")
    if rettype not in ["json-ld", "ntriples", "turtle"]:
        raise ModelNotFound(f"Model type {rettype} is not supported. Supported: json-ld, ntriples, turtle")
    if kwargs.get("encode", False):
        return encodebase64(getAllFileContent(f"{dbentry['fileloc']}.{rettype}"))
    return getAllFileContent(f"{dbentry['fileloc']}.{rettype}")


def depGetModel(dbI, **kwargs):
    """Get all models."""
    orderby = kwargs.get("orderby", ["insertdate", "DESC"])
    if not kwargs.get("modelID"):
        models = dbI.get("models", limit=kwargs.get("limit", 10), orderby=orderby)
        if not models:
            raise ModelNotFound("No models in database. First time run?")
        return models
    model = dbI.get("models", limit=1, search=[["uid", kwargs["modelID"]]])
    if not model:
        raise ModelNotFound(f"Model with {kwargs['modelID']} id was not found in the system")
    return model


def checkReadyState(deps):
    """Check if the system is ready for delta and model operations."""
    if not (firstRunFinished("LookUpService") or firstRunFinished("ProvisioningService")):
        return False
    # Check database connection.
    return deps["dbI"].isDBReady()


def checkSite(deps, sitename: str):
    """Check if the site is configured in the system."""
    if sitename not in deps["config"]["MAIN"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Site '{sitename}' is not configured in the system. Please check the request and configuration.",
        )


def checkPermissions(userinfo, required_perms: List[str]):
    """Check if the user has the required permissions."""
    print("Checking permissions for user:", userinfo)
    print("Required permissions:", required_perms)
    # user_perms = userinfo.get("user_info", {}).get("permissions", [])
    # if not any(perm in user_perms for perm in required_perms):
    #    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access to this resource is forbidden due to insufficient permissions.")
    # TODO: Implement permission checking logic and also add permissions inside the token


def apiReadDeps(
    config=Depends(depGetConfig),
    dbI=Depends(depGetDBObj),
    user=Depends(depAuthenticate),
    authHandler=Depends(depGetAuthHandler),
    stateMachine=Depends(depGetStateMachine),
    _creds: HTTPAuthorizationCredentials = Depends(BEARER_SCHEME),
):
    """Dependency to get all necessary objects for the REST API."""
    return {
        "config": config,
        "dbI": dbI,
        "user": user,
        "authHandler": authHandler,
        "stateMachine": stateMachine,
    }


def apiWriteDeps(
    config=Depends(depGetConfig),
    dbI=Depends(depGetDBObj),
    user=Depends(depAuthenticate),
    authHandler=Depends(depGetAuthHandler),
    stateMachine=Depends(depGetStateMachine),
    _creds: HTTPAuthorizationCredentials = Depends(BEARER_SCHEME),
):
    """Dependency to get all necessary objects for the REST API."""
    checkPermissions(user, ["write", "admin"])
    return {
        "config": config,
        "dbI": dbI,
        "user": user,
        "authHandler": authHandler,
        "stateMachine": stateMachine,
    }


def apiAdminDeps(
    config=Depends(depGetConfig),
    dbI=Depends(depGetDBObj),
    user=Depends(depAuthenticate),
    authHandler=Depends(depGetAuthHandler),
    stateMachine=Depends(depGetStateMachine),
):
    """Dependency to get all necessary objects for the REST API."""
    checkPermissions(user, ["admin"])
    return {
        "config": config,
        "dbI": dbI,
        "user": user,
        "authHandler": authHandler,
        "stateMachine": stateMachine,
    }


def apiPublicDeps(
    config=Depends(depGetConfig),
    authHandler=Depends(depGetAuthHandler),
    dbI=Depends(depGetDBObj),
    stateMachine=Depends(depGetStateMachine),
):
    """Dependency to get all necessary objects for the public REST API."""
    return {
        "config": config,
        "dbI": dbI,
        "authHandler": authHandler,
        "stateMachine": stateMachine,
    }


# pylint: disable=too-few-public-methods
class APIResponse:
    """API Response class to handle API responses."""

    @staticmethod
    def genResponse(
        request: Request,
        data: Union[Dict[str, Any], List[Any]],
        headers: Dict[str, str] = None,
        status_code: int = 200,
    ):
        """Generate a response based on the request and data."""
        if not isinstance(data, (dict, list)):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Data must be a dictionary or a list. Received: {type(data)}",
            )
        accept_header = request.headers.get("accept", "application/json").lower()
        headers = headers or {}
        if "application/json" in accept_header or "*/*" in accept_header:
            return JSONResponse(content=data, headers=headers, status_code=status_code)
        if "text/plain" in accept_header:
            # Handle plain text response if needed
            return Response(
                content=str(data),
                media_type="text/plain",
                headers=headers,
                status_code=status_code,
            )
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unsupported Accept header: {accept_header}. Supported: application/json, text/plain, */*",
        )


def forbidExtraQueryParams(*allowedParams: str):
    """Dependency to forbid extra query parameters not in allowedParams."""

    async def checker(request: Request):
        """Check for extra query parameters not allowed."""
        if "*" in allowedParams:
            return  # Permit anything
        incoming = set(request.query_params.keys())
        allowed = set(allowedParams)
        unknown = incoming - allowed
        if unknown:
            raise HTTPException(
                status_code=422,
                detail=[
                    {
                        "type": "extra_forbidden",
                        "loc": ["query", param],
                        "msg": f"Unexpected query parameter: {param}",
                    }
                    for param in unknown
                ],
            )

    return checker


# pylint: disable=unused-argument
class StrictBool:
    """Strict boolean:
    - Accepts: real booleans, 'true', 'false'
    - Rejects everything else.
    """

    @classmethod
    def __get_pydantic_core_schema__(cls, source, handler):
        return core_schema.no_info_plain_validator_function(cls.validate)

    @staticmethod
    def validate(value):
        """Validate the input value as a strict boolean."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            v = value.strip().lower()
            if v == "true":
                return True
            if v == "false":
                return False
            raise ValueError("Invalid boolean value. Expected 'true' or 'false'.")
        raise ValueError("Invalid boolean value. Expected true/false or 'true'/'false'.")

    @classmethod
    def __get_pydantic_json_schema__(cls, schema, handler):
        return {
            "type": "boolean",
            "description": "Strict boolean. Only true/false allowed (bool or string).",
        }


_RATE_LIMIT_BUCKETS: dict[str, deque] = defaultdict(deque)
_RATE_LIMIT_LOCK = asyncio.Lock()


def rateLimitIp(
    maxRequests: int = 60,
    windowSeconds: int = 60,
):
    """
    Rate limit decorator based on client IP.
    Example: 60 requests per 60 seconds per IP
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            request: Request | None = None

            # 1. Look in kwargs
            for value in kwargs.values():
                if isinstance(value, Request):
                    request = value
                    break

            # 2. Fallback: look in args
            if request is None:
                for arg in args:
                    if isinstance(arg, Request):
                        request = arg
                        break

            if request is None:
                raise RuntimeError("rate_limit_ip requires Request parameter")
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            async with _RATE_LIMIT_LOCK:
                bucket = _RATE_LIMIT_BUCKETS[client_ip]
                while bucket and bucket[0] <= now - windowSeconds:
                    bucket.popleft()
                if len(bucket) >= maxRequests:
                    raise HTTPException(
                        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                        detail=f"Rate limit exceeded: {maxRequests}/{windowSeconds}s",
                        headers={
                            "Retry-After": str(windowSeconds),
                        },
                    )
                bucket.append(now)
            return await func(*args, **kwargs)

        return wrapper

    return decorator
