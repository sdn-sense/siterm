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
from typing import Any, Dict, List, Union

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
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
)
from SiteRMLibs.x509 import CertHandler, OIDCHandler

DEP_CONFIG = getGitConfig()
DEP_DBOBJ = getDBConnObj()
DEP_STATE_MACHINE = ST.StateMachine(DEP_CONFIG)

DEFAULT_RESPONSES = {
    401: {"description": "Unauthorized", "content": {"application/json": {"example": {"detail": "Not authorized to access this resource"}}}},
    403: {"description": "Forbidden", "content": {"application/json": {"example": {"detail": "Access to this resource is forbidden"}}}},
    500: {"description": "Internal Server Error", "content": {"application/json": {"example": {"detail": "Internal server error"}}}},
    503: {"description": "Service Unavailable", "content": {"application/json": {"example": {"detail": "Service temporarily unavailable"}}}},
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


async def depAuthenticate(request: Request):
    """Dependency to authenticate the user via certificate or OIDC."""
    cert_handler = CertHandler()
    oidc_handler = OIDCHandler()
    try:
        print("Authenticating user via certificate")
        certInfo = cert_handler.getCertInfo(request)
        userInfo = cert_handler.validateCertificate(request)
        return {"cert_info": certInfo, "user_info": userInfo}
    except (RequestWithoutCert, IssuesWithAuth):
        try:
            userInfo = oidc_handler.validateOIDCInfo(request)
            return {"user_info": userInfo}
        except (RequestWithoutCert, IssuesWithAuth) as ex:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized access. Please provide valid credentials or check with your administrator.") from ex


def depGetModelContent(dbentry, **kwargs):
    """Get model content based on db entry."""
    rettype = kwargs.get("rdfformat", "turtle")
    if rettype not in ["json-ld", "ntriples", "turtle"]:
        raise ModelNotFound(f"Model type {rettype} is not supported. Supported: json-ld, ntriples, turtle")
    if kwargs.get("encode", False):
        return encodebase64(getAllFileContent(f'{dbentry["fileloc"]}.{rettype}'))
    return getAllFileContent(f'{dbentry["fileloc"]}.{rettype}')


def depGetModel(dbI, **kwargs):
    """Get all models."""
    if not kwargs.get("modelID", None):
        models = dbI.get("models", limit=kwargs.get("limit", 10), orderby=["insertdate", "DESC"])
        if not models:
            raise ModelNotFound("No models in database. First time run?")
        if kwargs.get("limit", 10) == 1:
            return models[0]
        return models
    model = dbI.get("models", limit=1, search=[["uid", kwargs["modelID"]]])
    if not model:
        raise ModelNotFound(f"Model with {kwargs['modelID']} id was not found in the system")
    return model[0]


def checkReadyState(checkignore: bool = False):
    """Check if the system is ready for delta and model operations."""
    if not checkignore:
        if not (firstRunFinished("LookUpService") or firstRunFinished("ProvisioningService")):
            return False
    return True


def checkSite(deps, sitename: str):
    """Check if the site is configured in the system."""
    if sitename not in deps["config"]["MAIN"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Site '{sitename}' is not configured in the system. Please check the request and configuration.")


def allAPIDeps(config=Depends(depGetConfig), dbI=Depends(depGetDBObj), user=Depends(depAuthenticate), stateMachine=Depends(depGetStateMachine)):
    """Dependency to get all necessary objects for the REST API."""
    return {"config": config, "dbI": dbI, "user": user, "stateMachine": stateMachine}


# pylint: disable=too-few-public-methods
class APIResponse:
    """API Response class to handle API responses."""

    @staticmethod
    def genResponse(request: Request, data: Union[Dict[str, Any], List[Any]], headers: Dict[str, str] = None):
        """Generate a response based on the request and data."""
        if not isinstance(data, (dict, list)):
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Data must be a dictionary or a list. Received: {type(data)}")
        accept_header = request.headers.get("accept", "application/json").lower()
        headers = headers or {}
        if "application/json" in accept_header or "*/*" in accept_header:
            return JSONResponse(content=data, headers=headers)
        if "text/plain" in accept_header:
            # Handle plain text response if needed
            return Response(content=str(data), media_type="text/plain", headers=headers)
        raise HTTPException(
            status_code=status.HTTP_406_NOT_ACCEPTABLE,
            detail=f"Unsupported Accept header: {accept_header}. Supported: application/json, text/plain, */*",
        )
