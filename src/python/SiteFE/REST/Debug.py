#!/usr/bin/env python3
# pylint: disable=line-too-long
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
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel
from SiteFE.REST.dependencies import DEFAULT_RESPONSES, allAPIDeps, checkSite
from SiteRMLibs import __version__ as runningVersion
from SiteRMLibs.MainUtilities import (
    dumpFileContentAsJson,
    generateRandomUUID,
    getFileContentAsJson,
    getUTCnow,
)
from SiteRMLibs.Validator import validator

router = APIRouter()


def _checkactionrequest(config, action=None):
    """Check if the action is valid for the given config."""
    if not config.getraw("MAIN"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend configuration file not found for site")
    if action and not config["MAIN"].get("debugactions", {}).get(action):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{action} not configured for this FE")


def getDebugEntry(deps, debugvar=None, hostname=None, state=None, details=False, limit=100):
    """Get Debug entry."""
    search = []
    if debugvar:
        search.append(["id", debugvar])
        limit = 1
    if hostname:
        search.append(["hostname", hostname])
    if state:
        search.append(["state", state])
    out = deps["dbI"].get("debugrequests", orderby=["insertdate", "DESC"], search=search, limit=limit)
    if out is None or len(out) == 0:
        return []
    if details and debugvar != "ALL":
        return _getdebuginfo(out[0])
    if details and debugvar == "ALL":
        for i, item in enumerate(out):
            out[i] = _getdebuginfo(item)
    return out


def getactions(config):
    """Get actions for debug calls."""
    _checkactionrequest(config)
    return config["MAIN"]["debugactions"].keys()


def getdefaults(config, service):
    """Get default values for debug calls."""
    _checkactionrequest(config)
    return config["MAIN"]["debuggers"][service]


def defaultkeys():
    """Get default keys for debug calls."""
    return {
        "hostname": {"description": "Hostname to use. In case not set or undefined, requires to have a dynamicfrom set.", "default": None, "required": False},
        "runtime": {
            "description": "Runtime duration in seconds. Instructs process to finish task after <seconds>. If not set, defaults between default and max runtime (random int).",
            "default": 600,
            "required": False,
        },
        "dynamicfrom": {"description": "Dynamic IP selection range. This is required if hostname not set or undefined. Otherwise this is skipped.", "default": None, "required": False},
    }


def getactionkeys(config, action):
    """Get action keys for debug calls."""
    defaults = getdefaults(config, action)
    actionkeys = {
        "iperf-server": {
            "time": {"description": "Duration of the test in seconds. Used as timeout <seconds> iperf3... It must be lower than runtime duration", "default": None, "required": True},
            "port": {"description": "Port to run the iperf server on", "default": 5201, "required": False},
            "ip": {"description": "IP address to bind the server to. Default is all interfaces", "default": "0.0.0.0", "required": False},
            "onetime": {
                "description": "One-time flag. If set, the server will only run for one test and then stop. If server finishes earlier than runtime parameter, iperf3 server will not be restarted.",
                "default": True,
                "required": False,
            },
        },
        "iperf-client": {
            "time": {"description": "Duration of the test in seconds. Used as iperf3 parameter -t <seconds>", "default": None, "required": True},
            "port": {"description": "Port to connect to on the Iperf server", "default": 5201, "required": False},
            "ip": {"description": "IP address of the Iperf server", "default": "0.0.0.0", "required": True},
            "streams": {"description": "Number of streams to use for the test", "default": 1, "required": True},
        },
        "fdt-server": {
            "time": {"description": "Duration of the test in seconds. Used as timeout <seconds> java -jar <jarfile> ... It must be lower than runtime duration", "default": None, "required": True},
            "port": {"description": "Port to run the FDT server on", "default": 54321, "required": False},
            "onetime": {
                "description": "One-time flag. If set, the server will only run for one test and then stop. If server finishes earlier than runtime parameter, fdt process will not be restarted and task will finish.",
                "default": True,
                "required": False,
            },
        },
        "fdt-client": {
            "time": {"description": "Duration of the test in seconds. Used as timeout <seconds> java -jar <jarfile> ... It must be lower than runtime duration", "default": None, "required": True},
            "port": {"description": "Port to connect to on the FDT server", "default": 54321, "required": False},
            "ip": {"description": "IP address of the FDT server", "default": None, "required": True},
            "streams": {"description": "Number of streams to use for the test", "default": 1, "required": True},
        },
        "rapid-pingnet": {
            "ip": {"description": "IP address to ping", "default": None, "required": True},
            "count": {"description": "Number of ping requests to send", "default": defaults.get("defaults", {}).get("count", 5), "required": True},
            "timeout": {"description": "Timeout for each ping request in seconds", "default": defaults.get("defaults", {}).get("timeout", 1), "required": True},
        },
        "rapid-ping": {
            "ip": {"description": "IP address to ping", "default": None, "required": True},
            "interval": {"description": "Interval between ping requests in seconds", "default": defaults.get("defaults", {}).get("interval", 1), "required": True},
            "time": {"description": "Total time to run the ping test in seconds", "default": defaults.get("defruntime", 600), "required": True},
            "packetsize": {"description": "Size of each ping packet in bytes", "default": defaults.get("defaults", {}).get("packetsize", 64), "required": True},
            "interface": {"description": "Network interface to use for the ping request", "default": None, "required": False},
        },
        "arp-table": {"interface": {"description": "Network interface to get the ARP table for", "default": None, "required": True}},
        "tcpdump": {"interface": {"description": "Network interface to capture packets on", "default": None, "required": True}},
        "traceroute": {
            "from_interface": {"description": "Network interface to use for the traceroute", "default": None, "required": False},
            "from_ip": {"description": "IP address to use as the source for the traceroute", "default": None, "required": False},
            "ip": {"description": "IP address to traceroute to", "default": None, "required": True},
        },
        "traceroute-net": {"ip": {"description": "IP address to traceroute to", "default": None, "required": True}},
    }
    if action not in actionkeys:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Action '{action}' not found in debug actions.")
    return {**actionkeys[action], **defaultkeys()}


class DebugItem(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: str
    # Optional fields
    request: dict = {}
    output: dict = {}
    insertTime: int = None
    updateTime: int = None


# TODO few more debug calls to add
# 2. Get a list of hostnames (split by hostname: type)
# 3. Get a list of allowed ipv6 dynamicfrom
# 4. implement ethr-server and ethr-client


# ==========================================================
# /api/{sitename}/debugactions # Return all possible debug actions
# ==========================================================
@router.get(
    "/{sitename}/debugactions",
    summary="Get Debug Actions List",
    description=("Returns a list of all possible debug actions for the given site name."),
    tags=["Debug"],
    responses={
        **{
            200: {"description": "Debug actions list retrieved successfully", "content": {"application/json": {"example": {"debug_actions_list": "example_debug_actions_list"}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActionsList(sitename: str = Path(..., description="The site name to retrieve the debug actions list for."), deps=Depends(allAPIDeps)):
    """
    Get a list of all possible debug actions for the given site name.
    - Returns a list of debug actions.
    """
    checkSite(deps, sitename)
    out = {"actions": getactions(deps["config"]), "version": runningVersion}
    return out


# =========================================================
# /api/{sitename}/debugactioninfo
# =========================================================
@router.get(
    "/{sitename}/debugactioninfo",
    summary="Get Debug Action Information",
    description=("Returns information about a specific debug action for the given site name."),
    tags=["Debug"],
    responses={
        **{
            200: {"description": "Debug action information retrieved successfully", "content": {"application/json": {"example": {"debug_action_info": "example_debug_action_info"}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActionInfo(
    sitename: str = Path(..., description="The site name to retrieve the debug action information for."),
    action: str = Query(..., description="The debug action to retrieve information for."),
    deps=Depends(allAPIDeps),
):
    """
    Get information about a specific debug action for the given site name.
    - Returns information about the debug action.
    """
    checkSite(deps, sitename)
    actions = getactions(deps["config"])
    if action not in actions:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Debug action '{action}' not found for site '{sitename}'.")
    defaults = getactionkeys(deps["config"], action)
    out = {"action": action, "defaults": defaults, "keys": "TODO", "version": runningVersion}
    return out


# =========================================================
# /api/{sitename}/debug
# =========================================================
@router.get(
    "/{sitename}/debug",
    summary="Get Debug Actions",
    description=("Returns the debug actions for the given site name."),
    tags=["Debug"],
    responses={
        **{
            200: {"description": "Debug actions retrieved successfully", "content": {"application/json": {"example": {"debug_actions": "example_debug_actions"}}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActions(
    sitename: str = Path(..., description="The site name to get the debug action information for."),
    debugvar: Optional[str] = Query(None, description="The debug action ID to retrieve information for."),
    limit: int = Query(100, description="Limit the number of debug requests returned. Only applicable for 'ALL'.", ge=1, le=100),
    details: bool = Query(False, description="If set, returns detailed information for the debug request."),
    hostname: str = Query(None, description="Hostname to filter the debug requests by. If not set, all debug requests are returned."),
    state: str = Query(None, description="State to filter the debug requests by. If not set, all debug requests are returned."),
    deps=Depends(allAPIDeps),
):
    """
    Get debug actions for the given site name.
    - Returns a list of debug actions.
    """
    checkSite(deps, sitename)
    return getDebugEntry(deps, debugvar=debugvar, hostname=hostname, state=state, details=details, limit=limit)


# =========================================================
# /api/{sitename}/debug/{debugid}
# =========================================================
def _getdebuginfo(out):
    """Get Debug action information."""
    out["requestdict"] = getFileContentAsJson(out["debuginfo"])
    out["output"] = getFileContentAsJson(out["outputinfo"])
    return out


@router.get(
    "/{sitename}/debug/{debugvar}",
    summary="Get Debug Action Information",
    description=("Returns the debug action information for the given debug ID."),
    tags=["Debug"],
    responses={
        200: {"description": "Debug action information", "content": {"application/json": {"example": {"TODO": "Add example response here"}}}},
        404: {"description": "Debug request not found", "content": {"application/json": {"example": {"detail": "Debug request with ID <debugvar> not found."}}}},
    },
)
async def getDebugInfo(
    sitename: str = Path(..., description="The site name to get the debug action information for."),
    debugvar: str = Path(..., description="The debug action ID to retrieve information for."),
    details: bool = Query(False, description="If set, returns detailed information for the debug request."),
    hostname: str = Query(None, description="Hostname to filter the debug requests by. If not set, all debug requests are returned."),
    state: str = Query(None, description="State to filter the debug requests by. If not set, all debug requests are returned."),
    deps=Depends(allAPIDeps),
):
    """Get Debug action information for a specific ID.
    In case of 'ALL', returns all debug requests.
    In case url param details is set, returns detailed information for the debug request.
    In case limit is set, returns limited number of debug requests. Only appliable for 'ALL'.
    - Returns the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    return getDebugEntry(deps, debugvar=debugvar, hostname=hostname, state=state, details=details)


@router.put(
    "/{sitename}/debug/{debugvar}",
    summary="Update Debug Action Information",
    description=("Updates the debug action information for the given debug ID."),
    tags=["Debug"],
    responses={
        200: {"description": "Debug action information updated successfully", "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}}},
        404: {"description": "Debug request not found", "content": {"application/json": {"example": {"detail": "Debug request with ID <debugvar> not found."}}}},
    },
)
async def updatedebug(
    item: DebugItem,
    sitename: str = Path(..., description="The site name to get the debug action information for."),
    debugvar: str = Path(..., description="The debug action ID to update information for."),
    deps=Depends(allAPIDeps),
):
    """Update Debug action information.
    - Updates the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    dbentry = deps["dbI"].get("debugrequests", search=[["id", debugvar]])
    if not dbentry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Debug request with ID {debugvar} not found.")
    # ==================================
    # Write output file
    dumpFileContentAsJson(dbentry[0]["outputinfo"], item.output)
    # Update the state in database.
    out = {"id": debugvar, "state": item.state, "updatedate": getUTCnow()}
    updOut = deps["dbI"].update("debugrequests", [out])
    return {"Status": updOut[0], "ID": updOut[2]}


@router.delete(
    "/{sitename}/debug/{debugvar}",
    summary="Delete Debug Action Information",
    description=("Deletes the debug action information for the given debug ID."),
    tags=["Debug"],
    responses={
        200: {"description": "Debug action information deleted successfully", "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}}},
        404: {"description": "Debug request not found", "content": {"application/json": {"example": {"detail": "Debug request with ID <debugvar> not found."}}}},
    },
)
async def deletedebug(
    sitename: str = Path(..., description="The site name to get the debug action information for."),
    debugvar: str = Path(..., description="The debug action ID to delete information for."),
    deps=Depends(allAPIDeps),
):
    """Delete Debug action information.
    - Deletes the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    dbentry = deps["dbI"].get("debugrequests", search=[["id", debugvar]])
    if not dbentry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Debug request with ID {debugvar} not found.")
    # ==================================
    updOut = deps["dbI"].delete("debugrequests", [["id", debugvar]])
    if os.path.isfile(dbentry[0]["debuginfo"]):
        os.remove(dbentry[0]["debuginfo"])
    if os.path.isfile(dbentry[0]["outputinfo"]):
        os.remove(dbentry[0]["outputinfo"])
    # ==================================
    # Return the status and ID of the deleted debug request
    return {"Status": updOut[0], "ID": updOut[2]}


# =========================================================
# /api/{sitename}/debug
# =========================================================
# Get a list of all debug calls, allow filtering by type
# like :hostname or :state
@router.post(
    "/{sitename}/debug",
    summary="Submit Debug Action Request",
    description=("Submits a new debug action request for the given site name."),
    tags=["Debug"],
    responses={
        200: {"description": "Debug action request submitted successfully", "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}}},
        400: {"description": "Bad request", "content": {"application/json": {"example": {"detail": "Unsupported symbol in input request. Contact Support"}}}},
    },
)
async def submitdebug(item: DebugItem, sitename: str = Path(..., description="The site name to get the debug action information for."), deps=Depends(allAPIDeps)):
    """Submit new debug action request.
    - Submits a new debug action request for the given site name.
    """
    checkSite(deps, sitename)
    # Check if action is supported;
    # Check if hostname is alive;
    inputDict = validator(deps["config"], item.dict())
    debugdir = os.path.join(deps["config"].get(sitename, "privatedir"), "DebugRequests")
    randomuuid = generateRandomUUID()
    requestfname = os.path.join(debugdir, inputDict["hostname"], randomuuid, "request.json")
    outputfname = os.path.join(debugdir, inputDict["hostname"], randomuuid, "output.json")
    dumpFileContentAsJson(requestfname, inputDict)
    out = {"hostname": inputDict.get("hostname", "undefined"), "state": "new", "insertdate": getUTCnow(), "updatedate": getUTCnow(), "debuginfo": requestfname, "outputinfo": outputfname}
    insOut = deps["dbI"].insert("debugrequests", [out])
    return {"Status": insOut[0], "ID": insOut[2]}
