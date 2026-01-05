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
from pydantic import BaseModel, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    StrictBool,
    apiAdminDeps,
    apiReadDeps,
    apiWriteDeps,
    checkReadyState,
    checkSite,
    depGetModel,
    forbidExtraQueryParams,
)
from SiteRMLibs.CustomExceptions import ModelNotFound
from SiteRMLibs.DefaultParams import (
    DELTA_COMMIT_TIMEOUT,
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
)
from SiteRMLibs.MainUtilities import (
    convertTSToDatetime,
    evaldict,
    getFileContentAsJson,
    getModTime,
    getstartupconfig,
    getUTCnow,
    httpdate,
    jsondumps,
    removeFile,
    saveContent,
)

router = APIRouter()

startupConfig = getstartupconfig()


def _getdeltas(dbI, **kwargs):
    """Get delta from database."""
    search = []
    if kwargs.get("deltaID"):
        search.append(["uid", kwargs.get("deltaID")])
    if kwargs.get("updatedate"):
        search.append(["updatedate", ">", kwargs.get("updatedate")])
    out = dbI.get(
        "deltas",
        search=search,
        limit=kwargs.get("limit", LIMIT_DEFAULT),
        orderby=["insertdate", "DESC"],
    )
    if out and kwargs.get("deltaID"):
        return out[0]
    return out


class DeltaItem(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    modelId: Optional[constr(strip_whitespace=True, min_length=1, max_length=255)] = None
    id: constr(strip_whitespace=True, min_length=1, max_length=255)
    # Optional fields
    reduction: Optional[constr(strip_whitespace=True, min_length=1)] = None
    addition: Optional[constr(strip_whitespace=True, min_length=1)] = None


class DeltaTimeState(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    uuid: constr(strip_whitespace=True, min_length=1, max_length=255)
    uuidtype: constr(strip_whitespace=True, min_length=1, max_length=64)
    hostname: constr(strip_whitespace=True, min_length=1, max_length=255)
    hostport: constr(strip_whitespace=True, min_length=1, max_length=64)
    uuidstate: constr(strip_whitespace=True, min_length=1, max_length=64)


# =========================================================
# /api/{sitename}/deltas
# =========================================================
@router.get(
    "/{sitename}/deltas",
    summary="Get Delta information",
    description=("Retrieves deltas from the specified site."),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Deltas retrieved successfully",
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "id": "b1c68762-986d-4767-a796-fdd5f59b7ef0",
                                "lastModified": 1753744800,
                                "state": "activated",
                                "href": "http://sense-dev-sdsc.nrp-nautilus.io/api/T2_US_SDSC_DEV/deltas/b1c68762-986d-4767-a796-fdd5f59b7ef0",
                                "modelId": "f7a1b548-6c08-11f0-bfcf-00000005c83b",
                            },
                            {
                                "id": "c814a8aa-a628-4335-a03e-9264228897e9",
                                "lastModified": 1753744589,
                                "state": "activated",
                                "href": "http://sense-dev-sdsc.nrp-nautilus.io/api/T2_US_SDSC_DEV/deltas/c814a8aa-a628-4335-a03e-9264228897e9",
                                "modelId": "385a0ead-6c08-11f0-b4ef-00000004e9ab",
                            },
                        ]
                    }
                },
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - No deltas found in the system.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_deltas": {"detail": "No deltas found in the system."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltas(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the service deltas for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    summary: StrictBool = Query(
        True,
        description="Whether to return a summary of the deltas. Defaults to False.",
    ),
    limit: int = Query(
        LIMIT_DEFAULT,
        description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit", "summary")),
):
    """
    Get service deltas from the specified site.
    """
    checkSite(deps, sitename)
    retvals = []
    modTime = getModTime(request.headers)
    deltas = _getdeltas(deps["dbI"], limit=limit, updatedate=modTime)
    if not deltas:
        # return 404 Not Found if no deltas are found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No deltas found in the system.",
        )
    # We get it here, but would be more valuable to do this in sql query.
    for delta in deltas:
        current = {
            "id": delta["uid"],
            "lastModified": delta["updatedate"],
            "state": delta["state"],
            "href": f"{request.base_url}api/{sitename}/deltas/{delta['uid']}",
            "modelId": delta["modelid"],
        }
        if not summary:
            content = evaldict(delta.get("content", {}))
            current["addition"] = content.get("addition")
            current["reduction"] = content.get("reduction")
        retvals.append(current)
    return APIResponse.genResponse(request, retvals)


@router.post(
    "/{sitename}/deltas",
    summary="Submit Delta",
    description=("Submits a new delta for the specified site."),
    tags=["Deltas"],
    responses={
        **{
            201: {
                "description": "Delta submitted successfully",
                "content": {"application/json": {"example": {"delta": "example_delta"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Model not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "model_not_found": {"detail": "Model not found in the database. First time run?"},
                        }
                    }
                },
            },
            400: {
                "description": "Bad Request. Possible Reasons:\n - You did POST method, but nor reduction, nor addition is present.\n - Failed to accept delta.",
                "content": {
                    "application/json": {
                        "example": {
                            "delta_missing": {"detail": "You did POST method, but nor reduction, nor addition is present."},
                            "delta_failed": {"detail": "Failed to accept delta. Error Message: <error_message>. Full dump: <full_dump>"},
                        }
                    }
                },
            },
            504: {
                "description": "Gateway Timeout. Possible Reasons:\n - Failed to accept delta. Timeout reached and output to accept delta is empty.",
                "content": {"application/json": {"example": {"timeout": {"detail": "Failed to accept delta. Timeout reached and output to accept delta is empty. Please report to site admins."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def submitDelta(
    request: Request,
    item: DeltaItem,
    sitename: str = Path(
        ...,
        description="The site name to submit the delta for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    deps=Depends(apiAdminDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Submit a new delta for the specified site.
    """
    checkSite(deps, sitename)
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(deps):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API is not in a ready state to accept requests. Server restart? Failing service?. Retry later.",
        )
    # If both addition and reduction are empty, raise a Error
    if not item.reduction and not item.addition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You did POST method, but nor reduction, nor addition is present",
        )
    if delta := _getdeltas(deps["dbI"], deltaID=item.id):
        # If delta is not in a final state, we delete it from db, and will add new one.
        if delta["state"] not in [
            "activated",
            "failed",
            "removed",
            "accepted",
            "accepting",
        ]:
            deps["dbI"].delete("deltas", [["uid", delta["uid"]]])
    try:
        # Get latest model, and check if modelId is same as latest
        # If not, raise an Error, as model was updated, and things have changed.
        latestModel = depGetModel(deps["dbI"], limit=1, orderby=["insertdate", "DESC"])[0]
        item.modelId = latestModel["uid"] if not item.modelId else item.modelId  # Set it to the latest, if not provided.
        if latestModel["uid"] != item.modelId:
            # Model ID does not match latest model, and latest model is the one with all committed changes. We will bypass the request and use the latest model ID.
            print(f"WARNING! Bypassing requested modelID {item.modelId}. Using latest model for comparison: {latestModel['uid']}")
    except ModelNotFound as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found in the database. First time run?",
        ) from ex
    outContent = {
        "ID": item.id,
        "insertdate": getUTCnow(),
        "updatedate": getUTCnow(),
        "content": item.dict(),
        "State": "accepting",
        "modelId": item.modelId,
    }
    # Save item to disk
    fname = os.path.join(
        deps["config"].get(sitename, "privatedir"),
        "PolicyService",
        "httpnew",
        f"{item.id}.json",
    )
    finishedName = os.path.join(
        deps["config"].get(sitename, "privatedir"),
        "PolicyService",
        "httpfinished",
        f"{item.id}.json",
    )
    saveContent(fname, outContent)

    # This is a blocking call, better approach is to reply and ask to check later.
    # But for now, we will block until we get output from PolicyService.
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
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Failed to accept delta. Timeout reached and output to accept delta is empty.",
        )
    if not out:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to accept delta. Output is empty.",
        )
    outContent["State"] = out["State"]
    outContent["id"] = item.id
    outContent["lastModified"] = convertTSToDatetime(outContent["updatedate"])
    outContent["href"] = f"{request.base_url}api/{sitename}/deltas/{item.id}"
    if outContent["State"] not in ["accepted"]:
        outContent["Error"] = out.get("Error", f"Unknown Error. Error Message: None. Full dump: {jsondumps(out)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to accept delta. Error Message: {outContent['Error']}.",
        )
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
            200: {
                "description": "Delta information retrieved successfully",
                "content": {"application/json": {"example": {"delta": "example_delta"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
            304: {
                "description": "Delta not modified",
                "content": {"application/json": {"example": {"detail": "Delta not modified. See Last-Modified header for the last modification date."}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltaByID(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the delta information for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to retrieve."),
    summary: StrictBool = Query(
        False,
        description="Whether to return a summary of the deltas. Defaults to False.",
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("summary")),
):
    """
    Get delta information by its ID for the given site name.
    """
    checkSite(deps, sitename)
    modTime = getModTime(request.headers)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database. First time run?",
        )
    # Check if the delta is modified since last request
    if delta["updatedate"] < modTime:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"Last-Modified": httpdate(delta["updatedate"])},
        )
    # Return 200 OK with delta content
    headers = {"Last-Modified": httpdate(delta["updatedate"])}
    delta["insertdate"] = convertTSToDatetime(delta["insertdate"])
    delta["updatedate"] = convertTSToDatetime(delta["updatedate"])
    delta["lastModified"] = delta["updatedate"]
    if not summary:
        content = evaldict(delta.get("content", {}))
        delta["addition"] = content.get("addition", {})
        delta["reduction"] = content.get("reduction", {})
    else:
        del delta["content"]
    return APIResponse.genResponse(request, [delta], headers=headers)


# =========================================================
# /api/{sitename}/deltas/{delta_id}/actions/{action}
# =========================================================


@router.put(
    "/{sitename}/deltas/{delta_id}/actions/{action}",
    summary="Perform Action on Delta",
    description=(
        "Performs a specified action on a delta by its ID for the given site name. Actions information:\n"
        f" - commit: Commit delta. Only commits if delta state is in accepted state. ({DELTA_COMMIT_TIMEOUT // 60} minutes timeout to received commit call)\n"
        f" - remove: Remove delta. Only removes if delta state is in accepted. (Way to bypass the {DELTA_COMMIT_TIMEOUT // 60} minutes timeout)\n"
        " - forcecommit: Force commit delta. Only commits if delta state is in one of: accepted, activated, failed state. (No timeout for forcecommit - use with caution due to overlaps!)\n"
        " - forceapply: Force apply delta on the system. (No timeout for forceapply - use with caution due to overlaps!)"
    ),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Action performed successfully",
                "content": {"application/json": {"example": {"result": "Action completed successfully"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
            400: {
                "description": "Bad Request",
                "content": {"application/json": {"example": {"detail": "Delta state 'X' is not valid for action 'Y'. Only 'Z' state is allowed."}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def performActionOnDelta(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to perform the action on the delta for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to perform the action on."),
    action: Literal["commit", "forcecommit", "forceapply"] = Path(..., description="The action to perform on the delta."),
    deps=Depends(apiAdminDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Perform a specified action on a delta by its ID for the given site name.
    """
    checkSite(deps, sitename)
    # actions are commit, forceapply
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(deps):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API is not in a ready state to accept requests. Server restart? Failing service?. Retry later.",
        )
    # Check if delta state is valid for commit action;
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database.",
        )
    if delta["state"] != "accepted" and action == "commit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Delta state '{delta['state']}' is not valid for commit action. Only 'accepted' state is allowed. Current state: {delta['state']}",
        )
    if delta["state"] not in ["activated", "failed", "accepted"] and action == "forcecommit":
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
    if delta["state"] in ["accepted"] and action == "remove":
        # Remove delta from the database
        deps["dbI"].delete("deltas", [["uid", delta_id]])
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid action '{action}' specified. Valid actions are 'commit', 'forcecommit', 'forceapply'.",
    )


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
            200: {
                "description": "Time states retrieved successfully",
                "content": {"application/json": {"example": {"time_states": "example_time_states"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                            "delta_no_timestates": {"detail": "No time states found for the specified delta ID."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getTimeStatesForDelta(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the time states for the delta.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to retrieve the time states for."),
    limit: int = Query(
        LIMIT_DEFAULT,
        description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit")),
):
    """
    Get time states for the specified delta ID.
    """
    checkSite(deps, sitename)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database.",
        )

    # Retrieve time states from the database
    timestates = deps["dbI"].get(
        "states",
        search=[["deltaid", delta_id]],
        orderby=["insertdate", "DESC"],
        limit=limit,
    )
    if not timestates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No time states found for the specified delta ID.",
        )
    return APIResponse.genResponse(request, timestates)


@router.post(
    "/{sitename}/deltas/{delta_id}/timestates",
    summary="Create Time State for Delta",
    description=("Creates a new time state for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            201: {
                "description": "Time state created successfully",
                "content": {"application/json": {"example": {"time_state": "example_time_state"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def createTimeStateForDelta(
    request: Request,
    item: DeltaTimeState,
    sitename: str = Path(
        ...,
        description="The site name to create the time state for the delta.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to create the time state for."),
    deps=Depends(apiWriteDeps),
):
    """
    Create a new time state for the specified delta ID.
    """
    checkSite(deps, sitename)
    # Check if the delta is in a state that allows creating a time state
    deps["dbI"].insert(
        "deltatimestates",
        [
            {
                "insertdate": getUTCnow(),
                "uuid": item.uuid,
                "uuidtype": item.uuidtype,
                "hostname": item.hostname,
                "hostport": item.hostport,
                "uuidstate": item.uuidstate,
            }
        ],
    )
    return APIResponse.genResponse(
        request,
        [
            {
                "status": "Time state created successfully",
                "delta_id": delta_id,
                "time_state": item.dict(),
            }
        ],
        status_code=status.HTTP_201_CREATED,
    )
