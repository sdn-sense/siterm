#!/usr/bin/env python3
# pylint: disable=line-too-long, too-many-arguments
"""
Delta API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""
import os
from time import sleep
from typing import Literal, Optional

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
from pydantic import BaseModel
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    allAPIDeps,
    checkReadyState,
    depGetModel,
)
from SiteRMLibs.CustomExceptions import ModelNotFound
from SiteRMLibs.MainUtilities import (
    convertTSToDatetime,
    decodebase64,
    getFileContentAsJson,
    getModTime,
    getUTCnow,
    httpdate,
    jsondumps,
    removeFile,
    saveContent,
)

router = APIRouter()


def _getdeltas(dbI, **kwargs):
    """Get delta from database."""
    search = []
    if kwargs.get("deltaID"):
        search.append(["uid", kwargs.get("deltaID")])
    if kwargs.get("updatedate"):
        search.append(["updatedate", ">", kwargs.get("updatedate")])
    out = dbI.get("deltas", search=search, limit=kwargs.get("limit", 10), orderby=["insertdate", "DESC"])
    if out and kwargs.get("deltaID"):
        return out[0]
    return out


class DeltaItem(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    modelId: str
    id: str
    # Optional fields
    reduction: Optional[str] = None
    addition: Optional[str] = None


class DeltaTimeState(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    uuid: str
    uuidtype: str
    hostname: str
    hostport: str
    uuidstate: str


# =========================================================
# /api/{sitename}/deltas
# =========================================================
@router.get(
    "/{sitename}/deltas",
    summary="Get Service Delta information",
    description=("Retrieves service deltas from the specified site."),
    tags=["Deltas"],
    responses={
        **{
            200: {"description": "Service deltas retrieved successfully", "content": {"application/json": {"example": {"delta": "example_delta"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltas(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the service deltas for."),
    summary: bool = Query(False, description="Whether to return a summary of the deltas. Defaults to False."),
    encode: bool = Query(True, description="Whether to encode the deltas. Defaults to True."),
    limit: int = Query(10, description="The maximum number of results to return. Defaults to 10."),
    _rdfformat: Literal["turtle", "json-ld", "ntriples"] = Query("turtle", description="Model format: turtle, json-ld, ntriples."),
    deps=Depends(allAPIDeps),
):
    """
    Get service deltas from the specified site.
    """
    retvals = {"deltas": []}
    modTime = getModTime(request.headers)
    deltas = _getdeltas(deps["dbI"], limit=limit, updatedate=modTime)
    if not deltas:
        # return 404 Not Found if no deltas are found
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No deltas found in the system.")
    # We get it here, but would be more valuable to do this in sql query.
    for delta in deltas:
        current = {
            "id": delta["uid"],
            "lastModified": delta["updatedate"],
            "state": delta["state"],
            "href": f"{deps['config'].get(sitename, 'app_callback')}/{delta['uid']}",
            "modelId": delta["modelid"],
        }
        if not summary:
            current["addition"] = decodebase64(delta["addition"], not encode)
            current["reduction"] = decodebase64(delta["reduction"], not encode)
        retvals["deltas"].append(current)
    return APIResponse.genResponse(request, [retvals])


@router.post(
    "/{sitename}/deltas",
    summary="Submit Delta",
    description=("Submits a new delta for the specified site."),
    tags=["Deltas"],
    responses={
        **{
            201: {"description": "Delta created successfully", "content": {"application/json": {"example": {"delta": "example_delta"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def submitDelta(
    request: Request,
    item: DeltaItem,
    sitename: str = Path(..., description="The site name to create the service delta for."),
    checkignore: bool = Query(False, description="Whether to bypass ignore checks (Frontend not ready yet state)"),
    deps=Depends(allAPIDeps),
):
    """
    Create a new service delta for the specified site.
    """
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(checkignore):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="You cannot request model information yet, because LookUpService or ProvisioningService is not finished with first run (Server restart?). Retry later.",
        )
    # If both addition and reduction are empty, raise a Error
    if not item.reduction and not item.addition:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You did POST method, but nor reduction, nor addition is present")
    if delta := _getdeltas(deps["dbI"], deltaID=item.id):
        # If delta is not in a final state, we delete it from db, and will add new one.
        if delta["state"] not in ["activated", "failed", "removed", "accepted", "accepting"]:
            deps["dbI"].delete("deltas", [["uid", delta["uid"]]])
    try:
        depGetModel(deps["dbI"], modelID=item.modelId)
    except ModelNotFound as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Model not found in the database. First time run?") from ex
    outContent = {"ID": item.id, "InsertTime": getUTCnow(), "UpdateTime": getUTCnow(), "Content": item.dict(), "State": "accepting", "modelId": item.modelId}
    # Save item to disk
    fname = os.path.join(deps["config"].get(sitename, "privatedir"), "PolicyService", "httpnew", f"{item.id}.json")
    finishedName = os.path.join(deps["config"].get(sitename, "privatedir"), "PolicyService", "httpfinished", f"{item.id}.json")
    saveContent(fname, outContent)

    # Loop for max 50seconds and check if we have file in finished directory.
    out = {}
    timer = 50
    while timer > 0:
        if os.path.isfile(finishedName):
            out = getFileContentAsJson(finishedName)
            removeFile(finishedName)
            break
        timer -= 1
        sleep(1)
    # If timer reached 0, we will not have file in finished directory
    if timer == 0 and not out:
        # Return failed http code
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Failed to accept delta. Timeout reached and output to accept delta is empty.")
    if not out:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to accept delta. Output is empty.")
    outContent["State"] = out["State"]
    outContent["id"] = item.id
    outContent["lastModified"] = convertTSToDatetime(outContent["UpdateTime"])
    outContent["href"] = f"{request.base_url}api/{sitename}/deltas/{item.id}"
    if outContent["State"] not in ["accepted"]:
        if "Error" not in out:
            outContent["Error"] = f"Unknown Error. Error Message: None. Full dump: {jsondumps(out)}"
        else:
            outContent["Error"] = out["Error"]
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Failed to accept delta. Error Message: {outContent['Error']}. Full dump: {jsondumps(out)}")
    return APIResponse.genResponse(request, outContent, status_code=status.HTTP_201_CREATED)


# =========================================================
# /api/{sitename}/deltas/{delta_id}
# =========================================================
@router.get(
    "/{sitename}/deltas/{delta_id}",
    summary="Get Delta by ID",
    description=("Retrieves delta information by its ID for the given site name."),
    tags=["Deltas"],
    responses={
        **{
            200: {"description": "Delta information retrieved successfully", "content": {"application/json": {"example": {"delta": "example_delta"}}}},
            404: {"description": "Delta not found", "content": {"application/json": {"example": {"detail": "Delta not found in the database."}}}},
            304: {"description": "Delta not modified", "content": {"application/json": {"example": {"detail": "Delta not modified."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltaByID(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the delta information for."),
    delta_id: str = Path(..., description="The ID of the delta to retrieve."),
    summary: bool = Query(False, description="Whether to return a summary of the deltas. Defaults to False."),
    encode: bool = Query(True, description="Whether to encode the deltas. Defaults to True."),
    deps=Depends(allAPIDeps),
):
    """
    Get delta information by its ID for the given site name.
    """
    modTime = getModTime(request.headers)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delta not found in the database. First time run?")
    # Check if the delta is modified since last request
    if delta["updatedate"] < modTime:
        return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers={"Last-Modified": httpdate(delta["updatedate"])})
    # Return 200 OK with delta content
    headers = {"Last-Modified": httpdate(delta["updatedate"])}
    response = {
        "id": delta["uid"],
        "lastModified": convertTSToDatetime(delta["updatedate"]),
        "state": delta["state"],
        "href": f"{request.base_url}api/{sitename}/deltas/{delta['uid']}",
        "modelId": delta["modelid"],
    }
    if not summary:
        response["addition"] = decodebase64(delta["addition"], not encode)
        response["reduction"] = decodebase64(delta["reduction"], not encode)
    return APIResponse.genResponse(request, response, headers=headers)


# =========================================================
# /api/{sitename}/deltas/{delta_id}/actions/{action}
# =========================================================


@router.put(
    "/{sitename}/deltas/{delta_id}/actions/{action}",
    summary="Perform Action on Delta",
    description=("Performs a specified action on a delta by its ID for the given site name."),
    tags=["Deltas"],
    responses={
        **{
            200: {"description": "Action performed successfully", "content": {"application/json": {"example": {"result": "Action completed successfully"}}}},
            404: {"description": "Delta not found", "content": {"application/json": {"example": {"detail": "Delta not found in the database."}}}},
            400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "Invalid action or parameters."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def performActionOnDelta(
    request: Request,
    _sitename: str = Path(..., description="The site name to perform the action on the delta for."),
    delta_id: str = Path(..., description="The ID of the delta to perform the action on."),
    action: Literal["commit", "forcecommit", "forceapply"] = Path(..., description="The action to perform on the delta."),
    checkignore: bool = Query(False, description="Whether to bypass ignore checks (Frontend not ready yet state)"),
    deps=Depends(allAPIDeps),
):
    """
    Perform a specified action on a delta by its ID for the given site name.
    """
    # actions are commit, forceapply
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(checkignore):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="You cannot request delta commit yet, because LookUpService or ProvisioningService is not finished with first run (Server restart?). Retry later.",
        )
    # Check if delta state is valid for commit action;
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delta not found in the database.")
    if delta["state"] != "accepted" and action == "commit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Delta state '{delta['state']}' is not valid for commit action. Only 'accepted' state is allowed. Current state: {delta['state']}"
        )
    if delta["state"] not in ["activated", "failed"] and action == "forcecommit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Delta state '{delta['state']}' is not valid for forcecommit action. Only 'activated' or 'failed' states are allowed. Current state: {delta['state']}",
        )
    if action in ["commit", "forcecommit"]:
        # Commit or force commit the delta
        deps["stateMachine"].stateChangerDelta(deps["dbI"], "committed", **delta)
        deps["stateMachine"].modelstatechanger(deps["dbI"], "add", **delta)
        return APIResponse.genResponse(request, {"result": "Action completed successfully"})
    if action == "forceapply":
        # Force apply the delta
        deps["dpI"].insert("forceapplyuuid", [{"uuid": delta_id}])
        return APIResponse.genResponse(request, {"result": "Force apply action completed successfully"})
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid action '{action}' specified. Valid actions are 'commit', 'forcecommit', 'forceapply'.")


# =========================================================
# /api/{sitename}/deltas/{delta_id}/timestates
# =========================================================
@router.get(
    "/{sitename}/deltas/{delta_id}/timestates",
    summary="Get Time States for Delta",
    description=("Retrieves time states for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            200: {"description": "Time states retrieved successfully", "content": {"application/json": {"example": {"time_states": "example_time_states"}}}},
            404: {"description": "Delta not found", "content": {"application/json": {"example": {"detail": "Delta not found in the database."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getTimeStatesForDelta(
    request: Request,
    _sitename: str = Path(..., description="The site name to retrieve the time states for the delta."),
    delta_id: str = Path(..., description="The ID of the delta to retrieve the time states for."),
    limit: int = Query(10, description="The maximum number of results to return. Defaults to 10."),
    deps=Depends(allAPIDeps),
):
    """
    Get time states for the specified delta ID.
    """
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delta not found in the database.")

    # Retrieve time states from the database
    timestates = deps["dbI"].get("deltatimestates", search=[["uuid", delta_id]], orderby=["insertdate", "DESC"], limit=limit)
    if not timestates:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No time states found for the specified delta ID.")
    return APIResponse.genResponse(request, {"time_states": timestates})


@router.post(
    "/{sitename}/deltas/{delta_id}/timestates",
    summary="Create Time State for Delta",
    description=("Creates a new time state for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            201: {"description": "Time state created successfully", "content": {"application/json": {"example": {"time_state": "example_time_state"}}}},
            404: {"description": "Delta not found", "content": {"application/json": {"example": {"detail": "Delta not found in the database."}}}},
            400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "Invalid time state parameters."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def createTimeStateForDelta(
    request: Request,
    item: DeltaTimeState,
    _sitename: str = Path(..., description="The site name to create the time state for the delta."),
    delta_id: str = Path(..., description="The ID of the delta to create the time state for."),
    deps=Depends(allAPIDeps),
):
    """
    Create a new time state for the specified delta ID.
    """
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delta not found in the database.")
    # Check if the delta is in a state that allows creating a time state
    deps["dbI"].insert(
        "deltatimestates", [{"insertdate": getUTCnow(), "uuid": item.uuid, "uuidtype": item.uuidtype, "hostname": item.hostname, "hostport": item.hostport, "uuidstate": item.uuidstate}]
    )
    return APIResponse.genResponse(request, {"status": "Time state created successfully", "delta_id": delta_id, "time_state": item.dict()}, status_code=status.HTTP_201_CREATED)
