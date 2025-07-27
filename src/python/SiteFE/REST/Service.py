#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Service API Calls
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
from pydantic import BaseModel
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    allAPIDeps,
    checkSite,
)
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.DefaultParams import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    LIMIT_SERVICE_DEFAULT,
    LIMIT_SERVICE_MAX,
    LIMIT_SERVICE_MIN,
)
from SiteRMLibs.MainUtilities import (
    HOSTSERVICES,
    dumpFileContentAsJson,
    evaldict,
    getUTCnow,
)

router = APIRouter()


def _host_supportedService(servicename):
    """Check if service is supported."""
    if servicename == "ALL":
        return True
    if servicename in HOSTSERVICES:
        return True
    return False


# =========================================================
# /api/{sitename}/services
# =========================================================


def __updateServiceData(item, sitename, dbI, config):
    """Update service data in the database."""
    servicest = "Undefined"
    fpath = os.path.join(config.get(sitename, "privatedir"), "ServiceData")
    fname = os.path.join(fpath, item.hostname, "serviceinfo.json")
    out = {
        "hostname": item.hostname,
        "servicename": item.servicename,
        "insertdate": getUTCnow(),
        "updatedate": getUTCnow(),
        "serviceinfo": fname,
    }
    search = []
    if item.hostname:
        search.append(["hostname", item.hostname])
    if item.servicename:
        search.append(["servicename", item.servicename])
    host = dbI.get("services", limit=1, search=search)
    if not host:
        dumpFileContentAsJson(fname, item.dict())
        dbI.insert("services", [out])
        servicest = "ADDED"
    else:
        out["id"] = host[0]["id"]
        dumpFileContentAsJson(fname, item.dict())
        dbI.update("services", [out])
        servicest = "UPDATED"
    return {"Status": servicest}


class ServiceItem(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: str
    servicename: str
    # Optional fields
    serviceinfo: Optional[Dict[str, Any]] = {}


# GET
# ---------------------------------------------------------
@router.get(
    "/{sitename}/services",
    summary="Get Service",
    description=("Retrieves a service state from the database based on hostname and servicename."),
    tags=["Service States"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getservice(
    request: Request,
    _sitename: str = Path(..., description="The site name to retrieve the service for."),
    hostname: str = Query(default=None, description="Hostname to filter by"),
    servicename: str = Query(default=None, description="Service name to filter by"),
    deps=Depends(allAPIDeps),
):
    """
    Get a service state from the database based on hostname and servicename.
    """
    checkSite(deps, _sitename)
    search = []
    if hostname:
        search.append(["hostname", hostname])
    if servicename:
        search.append(["servicename", servicename])
    return APIResponse.genResponse(request, deps["dbI"].get("services", search=search))


# POST
# ---------------------------------------------------------
@router.post(
    "/{sitename}/services",
    summary="Create Service",
    description=("Creates a new service state in the database."),
    tags=["Service States"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def createservice(request: Request, item: ServiceItem, sitename: str = Path(..., description="The site name to create the service for."), deps=Depends(allAPIDeps)):
    """
    Create a new service state in the database.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, __updateServiceData(item, sitename, deps["dbI"], deps["config"]))


# PUT
# ---------------------------------------------------------
@router.put(
    "/{sitename}/services",
    summary="Update Service",
    description=("Updates an existing service state in the database."),
    tags=["Service States"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def updateservice(request: Request, item: ServiceItem, sitename: str = Path(..., description="The site name to update the service for."), deps=Depends(allAPIDeps)):
    """
    Update an existing service state in the database.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, __updateServiceData(item, sitename, deps["dbI"], deps["config"]))


# DELETE
# ---------------------------------------------------------


@router.delete(
    "/{sitename}/services",
    summary="Delete Service state from database",
    description=("Deletes an existing service state from the database."),
    tags=["Service States"],
    responses={
        **{
            200: {"description": "Service successfully deleted", "content": {"application/json": {"example": {"Status": "DELETED <hostname>"}}}},
            400: {"description": "Bad Request", "content": {"application/json": {"example": {"detail": "At least one of 'hostname' or 'servicename' query parameters must be provided."}}}},
            404: {"description": "Service not found", "content": {"application/json": {"example": {"detail": "Service with hostname 'example' and servicename 'example' not found."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def deleteservice(
    request: Request, item: ServiceItem = Query(..., description="Service item to delete"), sitename: str = Path(..., description="The site name to delete the service for."), deps=Depends(allAPIDeps)
):
    """
    Delete an existing service state from the database.
    """
    checkSite(deps, sitename)
    if not item.hostname and not item.servicename:
        raise HTTPException(
            status_code=400,
            detail="At least one of 'hostname' or 'servicename' query parameters must be provided.",
        )
    search = []
    if item.hostname:
        search.append(["hostname", item.hostname])
    if item.servicename:
        search.append(["servicename", item.servicename])
    host = deps["dbI"].get("services", limit=1, search=search)
    if not host:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Service with hostname '{item.hostname}' and servicename '{item.servicename}' not found.")
    # Delete from services
    deps["dbI"].delete("services", [["id", host[0]["id"]]])
    return APIResponse.genResponse(request, {"Status": f"DELETED {host[0]['hostname']}"})


# =========================================================
# /api/{sitename}/servicestates
# =========================================================


class ServiceStateItem(BaseModel):
    """Service State Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: str
    servicename: str
    servicestate: str
    # Optional fields
    runtime: Optional[int] = -1  # Runtime in seconds, default is -1
    version: Optional[str] = "UNSET"  # Version of the service, default is "UNSET"
    exc: Optional[str] = "Exc Not Provided"  # Exception message, default is "Exc Not Provided"


# GET
# ---------------------------------------------------------
@router.get(
    "/{sitename}/servicestates",
    summary="Get Service States",
    description=("Returns the current service states from the database."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getservicestates(
    request: Request,
    limit: int = Query(LIMIT_SERVICE_DEFAULT, description=f"The maximum number of results to return. Defaults to {LIMIT_SERVICE_DEFAULT}.", ge=LIMIT_SERVICE_MIN, le=LIMIT_SERVICE_MAX),
    sitename: str = Path(..., description="The site name to retrieve the service states for."),
    deps=Depends(allAPIDeps),
):
    """
    Get service state data from the database.
    - Returns a list of service states with their information.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, deps["dbI"].get("servicestates", orderby=["updatedate", "DESC"], limit=limit))


# add/update (POST)
# ---------------------------------------------------------


@router.post(
    "/{sitename}/servicestates",
    summary="Add/Update Service State",
    description=("Adds a new service state or updates an existing one."),
    tags=["Service States"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def addservicestate(request: Request, item: ServiceStateItem, sitename: str = Path(..., description="The site name to add/update the service state for."), deps=Depends(allAPIDeps)):
    """
    Add a new service state or update an existing one.
    """
    checkSite(deps, sitename)
    if not _host_supportedService(item.servicename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"This Service {item.servicename} is not supported by Frontend")
    try:
        dbOut = {
            "hostname": item.hostname,
            "servicestate": item.servicestate,
            "servicename": item.servicename,
            "runtime": item.runtime,
            "version": item.version,
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
            "exc": str(item.exc)[:4095],
        }
        services = deps["dbI"].get("servicestates", search=[["hostname", item.hostname], ["servicename", item.servicename]])
        if services:
            deps["dbI"].update("servicestates", [dbOut])
        else:
            deps["dbI"].insert("servicestates", [dbOut])
    except Exception as ex:
        raise Exception(f"Error details in reportServiceStatus. Exc: {str(ex)}") from ex
    return APIResponse.genResponse(request, {"Status": "Updated"})


# =========================================================
# /api/{sitename}/serviceaction
# =========================================================
class ServiceActionItem(BaseModel):
    """Service Action Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: str  # Hostname to filter by
    servicename: str  # Service name to filter by
    action: str  # Action to perform (e.g., "start", "stop", etc.)


# GET
# ---------------------------------------------------------
@router.get(
    "/{sitename}/serviceaction",
    summary="Get Service Action",
    description=("Retrieves service actions from the database."),
    tags=["Service Actions"],
    responses={
        **{
            200: {"description": "Service actions retrieved successfully.", "content": {"application/json": {"example": {"Status": "Retrieved <actions>"}}}},
            404: {"description": "No service actions found for the given parameters.", "content": {"application/json": {"example": {"detail": "No service actions found for the given parameters."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getserviceaction(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the service action for."),
    hostname: str = Query(default=None, description="Hostname to filter by"),
    servicename: str = Query(default=None, description="Service name to filter by"),
    limit: int = Query(LIMIT_DEFAULT, description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.", ge=LIMIT_MIN, le=LIMIT_MAX),
    deps=Depends(allAPIDeps),
):
    """Get service actions from the database."""
    checkSite(deps, sitename)
    search = []
    if hostname:
        search.append(["hostname", hostname])
    if servicename:
        search.append(["servicename", servicename])
    actions = deps["dbI"].get("serviceaction", search=search, limit=limit)
    if not actions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No service actions found for the given parameters.")
    return APIResponse.genResponse(request, actions)


# POST
# ---------------------------------------------------------
@router.post(
    "/{sitename}/serviceaction",
    summary="Record Service Action",
    description=("Records a service action in the database."),
    tags=["Service Actions"],
    responses={
        **{
            200: {"description": "Service action recorded successfully.", "content": {"application/json": {"example": {"Status": "Recorded <hostname> <servicename> <action>"}}}},
            400: {
                "description": "Bad Request",
                "content": {"application/json": {"example": {"detail": "No Services identified for params: {'servicename': 'ALL', 'action': 'start', 'hostname': 'ALL'}"}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def serviceaction(request: Request, item: ServiceActionItem, sitename: str = Path(..., description="The site name to record the service action for."), deps=Depends(allAPIDeps)):
    """
    Record a service action in the database.
    """
    checkSite(deps, sitename)
    if not _host_supportedService(item.servicename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"This Service {item.servicename} is not supported by Frontend")
    services = [item.servicename]
    if services == ["ALL"]:
        services = HOSTSERVICES
    runningServices = deps["dbI"].get("servicestates")
    dbOuts = []
    for service in runningServices:
        add = False
        if service["servicename"] in services:
            if item.hostname != "ALL" and service["hostname"] == item.hostname:
                add = True
            elif item.hostname == "ALL":
                add = True
            else:
                statein = deps["dbI"].get("serviceaction", search=[["hostname", service["hostname"]], ["servicename", service["servicename"]], ["serviceaction", item.action]])
                if statein:
                    add = True
        if add:
            dbOut = {
                "hostname": service["hostname"],
                "servicename": service["servicename"],
                "serviceaction": item.action,
                "insertdate": getUTCnow(),
            }
            deps["dbI"].insert("serviceaction", [dbOut])
            dbOuts.append(dbOut)
    if not dbOuts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"No Services identified for params: {item}")
    return APIResponse.genResponse(request, {"Status": "Recorded", "DB": dbOuts})


# DELETE
# ---------------------------------------------------------
@router.delete(
    "/{sitename}/serviceaction",
    summary="Delete Service Action",
    description=("Deletes a service action from the database."),
    tags=["Service Actions"],
    responses={
        **{
            200: {"description": "Service action deleted successfully.", "content": {"application/json": {"example": {"Status": "Deleted <hostname> <servicename> <action>"}}}},
            404: {"description": "Service action not found.", "content": {"application/json": {"example": {"detail": "Service action not found for the given parameters."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def deleteserviceaction(request: Request, item: ServiceActionItem, _sitename: str = Path(..., description="The site name to delete the service action for."), deps=Depends(allAPIDeps)):
    """Delete a service action from the database."""
    checkSite(deps, _sitename)
    if not _host_supportedService(item.servicename):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"This Service {item.servicename} is not supported by Frontend")
    search = []
    if item.hostname:
        search.append(["hostname", item.hostname])
    if item.servicename:
        search.append(["servicename", item.servicename])
    if not search:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hostname or servicename provided to delete service action.")
    actions = deps["dbI"].get("serviceaction", search=search)
    if not actions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service action not found for the given parameters.")
    deps["dbI"].delete("serviceaction", search)
    return APIResponse.genResponse(request, {"Status": f"Deleted {item.hostname} {item.servicename} {item.action}"})


# TODO: Move to its own file
# =========================================================
# /api/{sitename}/setinstancestartend
# =========================================================


class InstanceStartEndItem(BaseModel):
    # pylint: disable=too-few-public-methods
    """
    Set Instance Start and End Time API Call
    - Sets the start and end time for a specific instance.
    - Requires instance ID in the input data.
    """
    instanceid: str
    starttimestamp: int
    endtimestamp: int


@router.post(
    "/{sitename}/setinstancestartend",
    summary="Set Instance Start and End Time",
    description=("Sets the start and end time for a specific instance. Used to override a specific instance start and end time."),
    tags=["Service Actions"],
    responses={
        **{
            200: {"description": "Instance start and end time successfully set.", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system\n" " - No active deltas found.\n" " - No instance found.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_active_deltas": {"detail": "No Active Deltas found."},
                            "no_instance": {"detail": "Instance ID <instanceid> is not found in activeDeltas."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def setinstancestartend(
    request: Request, item: InstanceStartEndItem, sitename: str = Path(..., description="The site name to retrieve the instance start and end time for."), deps=Depends(allAPIDeps)
):
    """
    Set the start and end time for a specific instance.
    - Requires instance ID in the input data.
    """
    checkSite(deps, sitename)
    # Validate that these entries are known...
    activeDeltas = deps["dbI"].get("activeDeltas", orderby=["updatedate", "DESC"], limit=1)
    if not activeDeltas:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No Active Deltas found.")

    activeDeltas = activeDeltas[0]
    activeDeltas["output"] = evaldict(activeDeltas["output"])
    found = False
    if item.instanceid in activeDeltas.get("output", {}).get("vsw", {}):
        found = True
    if item.instanceid in activeDeltas.get("output", {}).get("rst", {}):
        found = True
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Instance ID {item.instanceid} is not found in activeDeltas.")
    # Insert start and end time in instancestartend table
    out = {
        "instanceid": item.instanceid,
        "insertdate": getUTCnow(),
        "endtimestamp": item.endtimestamp,
        "starttimestamp": item.starttimestamp,
    }
    insOut = deps["dbI"].insert("instancestartend", [out])
    return APIResponse.genResponse(request, {"Status": insOut[0], "ID": insOut[2]})
