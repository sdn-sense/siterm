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
from dataclasses import dataclass
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from SiteFE.REST.dependencies import DEFAULT_RESPONSES, allAPIDeps, checkSite
from SiteRMLibs.MainUtilities import (
    dumpFileContentAsJson,
    getFileContentAsJson,
    getUTCnow,
)

router = APIRouter()

# =========================================================
# /api/{sitename}/hosts
# =========================================================


@dataclass
class HostItem(BaseModel):
    """Service Item Model."""
    # pylint: disable=too-few-public-methods
    hostname: str
    ip: str
    # Optional fields
    insertTime: int = None
    updateTime: int = None
    class Config:
        # pylint: disable=missing-class-docstring
        # Allow extra fields
        extra = "allow"


# get (GET)
@router.get(
    "/{sitename}/hosts",
    summary="Get All Registered Hosts",
    description=("TODO"),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def gethosts(
    sitename: str = Path(..., description="The site name to retrieve the hosts for."),
    limit: int = Query(100, description="The maximum number of results to return. Defaults to 100.", ge=1, le=100),
    deps=Depends(allAPIDeps),
):
    """
    Get host data from the database of all registered hosts.
    - Returns a list of hosts with their information.
    """
    checkSite(deps, sitename)
    hosts = deps["dbI"].get("hosts", orderby=["updatedate", "DESC"], limit=limit)
    out = []
    for host in hosts:
        host["hostinfo"] = getFileContentAsJson(host.get("hostinfo", ""))
        out.append(host)
    return out


# add (POST)
# ---------------------------------------------------------
@router.post(
    "/{sitename}/hosts",
    summary="Add or Update Host",
    description=("Adds a new host in the database."),
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
async def addhost(item: HostItem, sitename: str = Path(..., description="The site name to add or update the host for."), deps=Depends(allAPIDeps)):
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
        out = {"hostname": item.hostname, "ip": item.ip, "insertdate": item.insertTime or getUTCnow(), "updatedate": item.updateTime or getUTCnow(), "hostinfo": fname}
        dumpFileContentAsJson(fname, item.dict())
        deps["dbI"].insert("hosts", [out])
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This host is already in db. Use PUT to update existing host.")
    return {"Status": "ADDED"}


# update (PUT)
# ---------------------------------------------------------
@router.put(
    "/{sitename}/hosts",
    summary="Update Host",
    description=("Updates an existing host in the database."),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "Host updated successfully", "content": {"application/json": {"example": {"Status": "UPDATED"}}}},
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
async def updatehost(item: HostItem, sitename: str = Path(..., description="The site name to update the host for."), deps=Depends(allAPIDeps)):
    """
    Update an existing host in the database.
    - If the host does not exist, it will raise an exception.
    """
    checkSite(deps, sitename)
    host = deps["dbI"].get("hosts", limit=1, search=[["ip", item.ip]])
    if host:
        fpath = os.path.join(deps["config"].get(sitename, "privatedir"), "HostData")
        fname = os.path.join(fpath, item.hostname, "hostinfo.json")
        out = {"id": host[0]["id"], "hostname": item.hostname, "ip": item.ip, "insertdate": item.insertTime or getUTCnow(), "updatedate": item.updateTime or getUTCnow(), "hostinfo": fname}
        dumpFileContentAsJson(fname, item.dict())
        deps["dbI"].update("hosts", [out])
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This host is not in db. Use POST to add new host.")
    return {"Status": "UPDATED"}


# delete (DELETE)
# ---------------------------------------------------------
@router.delete(
    "/{sitename}/hosts",
    summary="Delete Host",
    description=("Deletes an existing host from the database."),
    tags=["Hosts"],
    responses={
        **{
            200: {"description": "Host deleted successfully", "content": {"application/json": {"example": {"Status": "DELETED"}}}},
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
async def deletehost(item: HostItem, sitename: str = Path(..., description="The site name to delete the host for."), deps=Depends(allAPIDeps)):
    """
    Delete an existing host from the database.
    - If the host does not exist, it will raise an exception.
    """
    checkSite(deps, sitename)
    host = deps["dbI"].get("hosts", limit=1, search=[["ip", item.ip], ["hostname", item.hostname]])
    if host:
        fpath = os.path.join(deps["config"].get(sitename, "privatedir"), "HostData")
        fname = os.path.join(fpath, item.hostname, "hostinfo.json")
        os.remove(fname)
        deps["dbI"].delete("hosts", [host[0]["id"]])
    else:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This host is not in db. Why to delete non-existing host?")
    return {"Status": "DELETED"}
