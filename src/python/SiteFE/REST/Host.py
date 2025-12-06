#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Frontend API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""
import os

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    apiAdminDeps,
    apiReadDeps,
    apiWriteDeps,
    checkSite,
    forbidExtraQueryParams,
    StrictBool
)
from SiteRMLibs.DefaultParams import LIMIT_DEFAULT, LIMIT_MAX, LIMIT_MIN
from SiteRMLibs.MainUtilities import (
    dumpFileContentAsJson,
    getFileContentAsJson,
    getstartupconfig,
    getUTCnow,
    removeFile,
)

router = APIRouter()

startupConfig = getstartupconfig()


# =========================================================
# /api/{sitename}/hosts
# =========================================================
class HostItem(BaseModel):
    """Host Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: constr(strip_whitespace=True, min_length=1, max_length=255)
    ip: constr(strip_whitespace=True, min_length=1, max_length=45)

    class Config:
        # pylint: disable=missing-class-docstring
        # Allow extra fields
        extra = "allow"


# get (GET)
@router.get(
    "/{sitename}/hosts",
    summary="Get All Registered Hosts",
    description="Get all registered hosts for a specific site.",
    tags=["Hosts"],
    responses={
        200: {
            "description": "List of registered hosts",
            "content": {
                "application/json": {
                    "schema": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "integer"},
                                "ip": {"type": "string"},
                                "hostname": {"type": "string"},
                                "insertdate": {"type": "integer"},
                                "updatedate": {"type": "integer"},
                                "hostinfo": {
                                    "type": "object",
                                    "properties": {
                                        "hostname": {"type": "string"},
                                        "ip": {"type": "string"},
                                        "Summary": {
                                            "type": "object",
                                            "properties": {
                                                "config": {
                                                    "type": "object",
                                                    "properties": {
                                                        "agent": {"type": "object"},
                                                        "enp65s0f1np1": {"type": "object"},
                                                    },
                                                }
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "example": [
                        {
                            "id": 3,
                            "ip": "132.249.252.210",
                            "hostname": "node-2-7.sdsc.optiputer.net",
                            "insertdate": 1746465664,
                            "updatedate": 1753745473,
                            "hostinfo": {
                                "hostname": "node-2-7.sdsc.optiputer.net",
                                "ip": "132.249.252.210",
                                "Summary": {
                                    "config": {
                                        "agent": {"hostname": "node-2-7.sdsc.optiputer.net", "interfaces": ["enp65s0f1np1"], "noqos": True, "norules": False, "rsts_enabled": "ipv4,ipv6"},
                                        "enp65s0f1np1": {
                                            "bwParams": {"granularity": 1000, "maximumCapacity": 100000, "minReservableCapacity": 1000, "priority": 0, "type": "guaranteedCapped", "unit": "mbps"}
                                        },
                                    }
                                },
                            },
                        }
                    ],
                }
            },
        },
        404: {
            "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - No hosts found in the database.",
            "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                                                         "no_hosts": {"detail": "No hosts found in the database."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def gethosts(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the hosts for.", example=startupConfig.get("SITENAME", "default")),
    hostname: str = Query(None, description="Filter by hostname."),
    details: StrictBool = Query(False, description="If True, returns detailed host information. In case detail, limit is ignored and set to 1."),
    limit: int = Query(LIMIT_DEFAULT, description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.", ge=LIMIT_MIN, le=LIMIT_MAX),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("hostname", "details", "limit")),
):
    """
    Get host data from the database of all registered hosts.
    - Returns a list of hosts with their information.
    """
    checkSite(deps, sitename)
    search = []
    if hostname:
        search.append(["hostname", hostname])
        limit = 1
    if details:
        limit = 1
    hosts = deps["dbI"].get("hosts", orderby=["updatedate", "DESC"], limit=limit, search=search)
    out = []
    if not hosts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No hosts found in the database.")
    for host in hosts:
        if details:
            host["hostinfo"] = getFileContentAsJson(host.get("hostinfo", ""))
            out.append(host)
            break
        else:
            host.pop("hostinfo", None)
        out.append(host)
    return APIResponse.genResponse(request, out)


# add (POST)
# ---------------------------------------------------------
@router.post(
    "/{sitename}/hosts",
    summary="Add new host to the database. THIS IS INTERNAL API CALL FOR AGENTS TO ADD HOSTS.",
    description=("Adds a new host in the database. THIS IS INTERNAL API CALL FOR AGENTS TO ADD HOSTS."),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "Host added successfully", "content": {"application/json": {"example": {"Status": "ADDED"}}}},
            400: {"description": "Host already exists", "content": {"application/json": {"example": {"detail": "This host is already in db. Use PUT to update existing host."}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def addhost(
    request: Request,
    item: HostItem,
    sitename: str = Path(..., description="The site name to add or update the host for.", example=startupConfig.get("SITENAME", "default")),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Add or update a host in the database.
    - If the host does not exist, it will be added.
    - If the host exists, it will raise an exception.
    """
    checkSite(deps, sitename)
    host = deps["dbI"].get("hosts", limit=1, search=[["ip", item.ip]])
    if not host:
        fpath = os.path.join(deps["config"].get(sitename, "privatedir"), "HostData")
        fname = os.path.join(fpath, item.hostname, "hostinfo.json")
        out = {"hostname": item.hostname, "ip": item.ip, "insertdate": getUTCnow(), "updatedate": getUTCnow(), "hostinfo": fname}
        dumpFileContentAsJson(fname, item.dict())
        deps["dbI"].insert("hosts", [out])
        return APIResponse.genResponse(request, {"status": "ADDED"})
    else:
        out = {"id": host[0]["id"], "hostname": item.hostname, "ip": item.ip, "insertdate": getUTCnow(), "updatedate": getUTCnow(), "hostinfo": host[0]["hostinfo"]}
        # Check if there is a data update
        if "nodatachange" in item.dict() and item.nodatachange:
            deps["dbI"].update("hosts", [{"id": host[0]["id"], "updatedate": getUTCnow()}])
        else:
            dumpFileContentAsJson(host[0]["hostinfo"], item.dict())
            deps["dbI"].update("hosts", [out])
    return APIResponse.genResponse(request, {"status": "UPDATED"})

# update (PUT)
# ---------------------------------------------------------
@router.put(
    "/{sitename}/hosts",
    summary="Update Host in Database. THIS IS INTERNAL API CALL FOR AGENTS TO UPDATE HOSTS.",
    description=("Updates an existing host in the database. THIS IS INTERNAL API CALL FOR AGENTS TO UPDATE HOSTS."),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "Host updated successfully", "content": {"application/json": {"example": {"status": "UPDATED"}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.\n" " - Host does not exist in the database.",
                "content": {
                    "application/json": {
                        "example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}},
                        "host_not_found": {"detail": "Host <hostname> does not exist in the database."},
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def updatehost(
    request: Request,
    item: HostItem,
    sitename: str = Path(..., description="The site name to update the host for.", example=startupConfig.get("SITENAME", "default")),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Update an existing host in the database.
    - If the host does not exist, it will raise an exception.
    """
    checkSite(deps, sitename)
    host = deps["dbI"].get("hosts", limit=1, search=[["ip", item.ip]])
    if host:
        out = {"id": host[0]["id"], "hostname": item.hostname, "ip": item.ip, "insertdate": getUTCnow(), "updatedate": getUTCnow(), "hostinfo": host[0]["hostinfo"]}
        # Check if there is a data update
        if "nodatachange" in item.dict() and item.nodatachange:
            deps["dbI"].update("hosts", [{"id": host[0]["id"], "updatedate": getUTCnow()}])
        else:
            dumpFileContentAsJson(host[0]["hostinfo"], item.dict())
            deps["dbI"].update("hosts", [out])
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This host is not in db. Use POST to add new host.")
    return APIResponse.genResponse(request, {"status": "UPDATED"})


# delete (DELETE)
# ---------------------------------------------------------
@router.delete(
    "/{sitename}/hosts",
    summary="Delete Host",
    description=("Deletes an existing host from the database."),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "Host deleted successfully", "content": {"application/json": {"example": {"status": "DELETED"}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.\n" " - Host does not exist in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "host_not_found": {"detail": "This host is not in db. Why to delete non-existing host?"},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def deletehost(
    request: Request,
    item: HostItem,
    sitename: str = Path(..., description="The site name to delete the host for.", example=startupConfig.get("SITENAME", "default")),
    deps=Depends(apiAdminDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Delete an existing host from the database.
    - If the host does not exist, it will raise an exception.
    """
    checkSite(deps, sitename)
    # Delete all servicestates related to this host (even host is not found, we need to clean servicestates)
    deps["dbI"].delete("servicestates", [["hostname", item.hostname]])
    # Delete host entries
    host = deps["dbI"].get("hosts", limit=1, search=[["ip", item.ip], ["hostname", item.hostname]])
    if host:
        removeFile(host[0].get("hostinfo", ""))
        deps["dbI"].delete("hosts", [["id", host[0]["id"]]])
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This host is not in db. Why to delete non-existing host?")
    return APIResponse.genResponse(request, {"status": "DELETED"})
