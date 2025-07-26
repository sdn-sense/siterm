#!/usr/bin/env python3
# pylint: disable=line-too-long, too-many-arguments
"""
Model API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/17
"""
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    allAPIDeps,
    checkSite,
    depGetModel,
    depGetModelContent,
)
from SiteRMLibs.CustomExceptions import ModelNotFound
from SiteRMLibs.MainUtilities import convertTSToDatetime, getModTime, httpdate

router = APIRouter()


# =========================================================
# /api/{sitename}/models
# =========================================================
@router.get(
    "/{sitename}/models",
    summary="Get Model Information",
    description=("Retrieves model information for the given site name."),
    tags=["Models"],
    responses={
        **{
            200: {"description": "Model information retrieved successfully", "content": {"application/json": {"example": {"model": "example_model"}}}},
            404: {"description": "Model not found", "content": {"application/json": {"example": {"detail": "Model not found in the database. First time run?"}}}},
            304: {"description": "Not Modified", "content": {"application/json": {"example": {"detail": "Model not modified since last request"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getModelInfo(
    # pylint: disable=too-many-locals
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the model information for."),
    current: bool = Query(False, description="Whether to return the current model. Defaults to False."),
    summary: bool = Query(True, description="Whether to return a summary of the model. Defaults to True."),
    encode: bool = Query(True, description="Whether to encode the model. Defaults to True."),
    limit: int = Query(100, description="The maximum number of results to return. Defaults to 10. Only applies if current is False."),
    rdfformat: Literal["turtle", "json-ld", "ntriples"] = Query("turtle", description="Model format: turtle, json-ld, ntriples."),
    deps=Depends(allAPIDeps),
):
    """
    Get model information for the given site name.
    """
    # Check if current is set, if so, it only asks for current model
    checkSite(deps, sitename)
    try:
        if current:
            outmodels = depGetModel(deps["dbI"], limit=1, orderby=["insertdate", "DESC"])
            # Check IF_MODIFIED_SINCE from request headers
            if outmodels["insertdate"] < getModTime(request.headers):
                return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"Last-Modified": httpdate(outmodels["insertdate"])})
            # Return 200 OK with model content
            headers = {"Last-Modified": httpdate(outmodels["insertdate"])}
            if not summary:
                modContent = depGetModelContent(outmodels, rdfformat=rdfformat, encode=encode)
                return APIResponse.genResponse(request,
                                               [{"id": outmodels["uid"],
                                                 "creationTime": convertTSToDatetime(outmodels["insertdate"]),
                                                 "href": f"{request.base_url}api/{sitename}/models/{outmodels['uid']}",
                                                 "model": modContent}],
                    headers=headers,
                )
            return APIResponse.genResponse(request, [{"id": outmodels["uid"],
                                                      "creationTime": convertTSToDatetime(outmodels["insertdate"]),
                                                      "href": f"{request.base_url}api/{sitename}/models/{outmodels['uid']}"}],
                                           headers=headers)
        # If current is not set, return all models (based on limit)
        outmodels = depGetModel(deps["dbI"], limit=limit, orderby=["insertdate", "DESC"])
        models = []
        for model in outmodels:
            tmpDict = {"id": model["uid"], "creationTime": convertTSToDatetime(model["insertdate"]), "href": f"{request.base_url}api/{sitename}/models/{model['uid']}"}
            if not summary:
                tmpDict["model"] = depGetModelContent(model, rdfformat=rdfformat, encode=encode)
            models.append(tmpDict)
        return APIResponse.genResponse(request, models)
    except ModelNotFound as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found in the database. First time run?") from ex


# =========================================================
# /api/{sitename}/models/{modelID}
# =========================================================
@router.get(
    "/{sitename}/models/{modelID}",
    summary="Get Model by ID",
    description=("Retrieves model information by its ID for the given site name."),
    tags=["Models"],
    responses={
        **{
            200: {"description": "Model information retrieved successfully", "content": {"application/json": {"example": {"model": "example_model"}}}},
            404: {"description": "Model not found", "content": {"application/json": {"example": {"detail": "Model not found in the database. First time run?"}}}},
            304: {"description": "Not Modified", "content": {"application/json": {"example": {"detail": "Model not modified since last request"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
# pylint: disable=too-many-arguments,too-many-locals
async def getModelByID(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the model information for."),
    modelID: str = Path(..., description="The ID of the model to retrieve."),
    summary: bool = Query(False, description="Whether to return a summary of the model. Defaults to False."),
    encode: bool = Query(False, description="Whether to encode the model. Defaults to False."),
    rdfformat: Literal["turtle", "json-ld", "ntriples"] = Query("turtle", description="Model format: turtle, json-ld, ntriples."),
    deps=Depends(allAPIDeps),
):
    """
    Get model information by its ID for the given site name.
    """
    # Get model by ID
    try:
        model = depGetModel(deps["dbI"], modelID=modelID, limit=1)
        # Check IF_MODIFIED_SINCE from request headers
        if model["insertdate"] < getModTime(request.headers):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"Last-Modified": httpdate(model["insertdate"])})
        # Return 200 OK with model content
        headers = {"Last-Modified": httpdate(model["insertdate"])}
        if not summary:
            modContent = depGetModelContent(model, rdfformat=rdfformat, encode=encode)
            return APIResponse.genResponse(
                request,
                {"id": model["uid"], "creationTime": convertTSToDatetime(model["insertdate"]), "href": f"{request.base_url}api/{sitename}/models/{model['uid']}", "model": modContent},
                headers=headers,
            )
        return APIResponse.genResponse(
            request,
            {"id": model["uid"], "creationTime": convertTSToDatetime(model["insertdate"]), "href": f"{request.base_url}api/{sitename}/models/{model['uid']}"},
            headers=headers,
        )
    except ModelNotFound as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requested model not found in the database.") from ex
