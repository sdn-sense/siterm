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
import traceback
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    StrictBool,
    apiReadDeps,
    apiWriteDeps,
    checkSite,
    forbidExtraQueryParams,
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


def _checkactionrequest(config, action=None):
    """Check if the action is valid for the given config."""
    if not config.getraw("MAIN"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend configuration file not found for site",
        )
    if action and not config["MAIN"].get("debugactions", {}).get(action):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{action} not configured for this FE",
        )


def getDebugEntry(
    deps,
    debugvar=None,
    hostname=None,
    state=None,
    details=False,
    limit=LIMIT_DEFAULT,
    action=None,
):
    """Get Debug entry."""
    search = []
    if debugvar == "ALL":
        debugvar = None
    if debugvar:
        search.append(["id", debugvar])
        limit = 1
    if hostname:
        search.append(["hostname", hostname])
    if state:
        search.append(["state", state])
    if action:
        search.append(["action", action])
    out = deps["dbI"].get("debugrequests", orderby=["insertdate", "DESC"], search=search, limit=limit)
    if out is None or len(out) == 0:
        return []
    if details and debugvar != "ALL":
        return [_getdebuginfo(out[0])]
    if details and debugvar == "ALL":
        for i, item in enumerate(out):
            out[i] = _getdebuginfo(item)
    return out


def getactions(config):
    """Get actions for debug calls."""
    _checkactionrequest(config)
    return config["MAIN"]["debuggers"].keys()


def getdefaults(config, service):
    """Get default values for debug calls."""
    _checkactionrequest(config)
    return config["MAIN"]["debuggers"][service]


def defaultkeys():
    """Get default keys for debug calls."""
    return {
        "hostname": {
            "description": "Hostname to use. In case not set or undefined, requires to have a dynamicfrom set.",
            "default": None,
            "required": False,
        },
        "runtime": {
            "description": "Runtime duration in seconds. Instructs process to finish task after <seconds>. If not set, defaults between default and max runtime (random int).",
            "default": 600,
            "required": False,
        },
        "dynamicfrom": {
            "description": "Dynamic IP selection range. This is required if hostname not set or undefined. Otherwise this is skipped.",
            "default": None,
            "required": False,
        },
    }


def getactionkeys(config, action):
    """Get action keys for debug calls."""
    defaults = getdefaults(config, action)
    actionkeys = {
        "iperf-server": {
            "time": {
                "description": "Duration of the test in seconds. Used as timeout <seconds> iperf3... It must be lower than runtime duration",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to run the iperf server on",
                "default": defaults.get("defaults", {}).get("port", None),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "ip": {
                "description": "IP address to bind the server to. Default is all interfaces",
                "default": "0.0.0.0",
                "required": False,
            },
            "onetime": {
                "description": "One-time flag. If set, the server will only run for one test and then stop. If server finishes earlier than runtime parameter, iperf3 server will not be restarted.",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "iperf-client": {
            "time": {
                "description": "Duration of the test in seconds. Used as iperf3 parameter -t <seconds>",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to connect to on the Iperf server",
                "default": defaults.get("defaults", {}).get("port", None),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "ip": {
                "description": "IP address of the Iperf server",
                "default": "0.0.0.0",
                "required": True,
            },
            "streams": {
                "description": "Number of streams to use for the test",
                "default": defaults.get("defaults", {}).get("streams", None),
                "required": not defaults.get("defaults", {}).get("streams", None),
            },
        },
        "ethr-server": {
            "time": {
                "description": "Duration of the test in seconds. Used as timeout <seconds> ethr... It must be lower than runtime duration",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to run the ethr server on",
                "default": defaults.get("defaults", {}).get("port", None),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "ip": {
                "description": "IP address to bind the server to. Default is all interfaces",
                "default": "0.0.0.0",
                "required": True,
            },
        },
        "ethr-client": {
            "time": {
                "description": "Duration of the test in seconds. Used as timeout <seconds> ethr... It must be lower than runtime duration",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to connect to on the ethr server",
                "default": defaults.get("defaults", {}).get("port", None),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "ip": {
                "description": "IP address of the ethr server",
                "default": "0.0.0.0",
                "required": True,
            },
        },
        "fdt-server": {
            "time": {
                "description": "Duration of the test in seconds. Used as timeout <seconds> java -jar <jarfile> ... It must be lower than runtime duration",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to run the FDT server on",
                "default": defaults.get("defaults", {}).get("port", None),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "onetime": {
                "description": "One-time flag. If set, the server will only run for one test and then stop. If server finishes earlier than runtime parameter, fdt process will not be restarted and task will finish.",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "fdt-client": {
            "time": {
                "description": "Duration of the test in seconds. Used as timeout <seconds> java -jar <jarfile> ... It must be lower than runtime duration",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "port": {
                "description": "Port to connect to on the FDT server",
                "default": defaults.get("defaults", {}).get("port", 54321),
                "required": not defaults.get("defaults", {}).get("port", None),
            },
            "ip": {
                "description": "IP address of the FDT server",
                "default": None,
                "required": True,
            },
            "streams": {
                "description": "Number of streams to use for the test",
                "default": defaults.get("defaults", {}).get("streams", None),
                "required": not defaults.get("defaults", {}).get("streams", None),
            },
            "onetime": {
                "description": "One-time flag. If set, the client will only run for one test and then stop.",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "rapid-pingnet": {
            "ip": {
                "description": "IP address to ping",
                "default": None,
                "required": True,
            },
            "count": {
                "description": f"Number of ping requests to send. Max {defaults.get('maxcount', None)}",
                "default": None,
                "required": True,
            },
            "timeout": {
                "description": "Timeout for each ping request in seconds",
                "default": defaults.get("deftime", None),
                "required": not defaults.get("deftime", None),
            },
            "onetime": {
                "description": "If set, only a single ping request is sent",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "rapid-ping": {
            "ip": {
                "description": "IP address to ping",
                "default": None,
                "required": True,
            },
            "interval": {
                "description": "Interval between ping requests in seconds",
                "default": defaults.get("defaults", {}).get("interval", None),
                "required": not defaults.get("defaults", {}).get("interval", None),
            },
            "time": {
                "description": "Total time to run the ping test in seconds",
                "default": defaults.get("deftime", 600),
                "required": not defaults.get("deftime", None),
            },
            "packetsize": {
                "description": "Size of each ping packet in bytes",
                "default": defaults.get("defaults", {}).get("packetsize", 64),
                "required": not defaults.get("defaults", {}).get("packetsize", None),
            },
            "interface": {
                "description": "Network interface to use for the ping request",
                "default": None,
                "required": False,
            },
        },
        "arp-table": {
            "interface": {
                "description": "Network interface to get the ARP table for",
                "default": None,
                "required": True,
                "onetime": {
                    "description": "If set, only a single ARP table is retrieved",
                    "default": defaults.get("defaults", {}).get("onetime", None),
                    "required": not defaults.get("defaults", {}).get("onetime", None),
                },
            }
        },
        "tcpdump": {
            "interface": {
                "description": "Network interface to capture packets on",
                "default": None,
                "required": True,
            },
            "onetime": {
                "description": "If set, only a single packet capture is retrieved",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "traceroute": {
            "from_interface": {
                "description": "Network interface to use for the traceroute",
                "default": None,
                "required": False,
            },
            "from_ip": {
                "description": "IP address to use as the source for the traceroute",
                "default": None,
                "required": False,
            },
            "ip": {
                "description": "IP address to traceroute to",
                "default": None,
                "required": True,
            },
            "onetime": {
                "description": "If set, only a single traceroute is retrieved",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
        "traceroute-net": {
            "ip": {
                "description": "IP address to traceroute to",
                "default": None,
                "required": True,
            },
            "onetime": {
                "description": "If set, only a single traceroute is retrieved",
                "default": defaults.get("defaults", {}).get("onetime", None),
                "required": not defaults.get("defaults", {}).get("onetime", None),
            },
        },
    }
    if action not in actionkeys:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action '{action}' not found in debug actions.",
        )
    return {**actionkeys[action], **defaultkeys()}


class DebugItem(BaseModel):
    """Debug Item Model."""

    # pylint: disable=too-few-public-methods
    id: Optional[int] = None
    hostname: constr(strip_whitespace=True, min_length=1, max_length=255) = "undefined"  # Hostname to use. In case not set or undefined, requires to have a dynamicfrom set.
    state: constr(strip_whitespace=True, min_length=1, max_length=45) = "new"
    request: Optional[Dict[str, Any]] = Field(default_factory=dict)
    output: Optional[Dict[str, Any]] = Field(default_factory=dict)


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
            200: {
                "description": "Debug actions list retrieved successfully",
                "content": {"application/json": {"example": {"debug_actions_list": "example_debug_actions_list"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Action <action> not found in debug actions.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_action": {"detail": "Action <action> not found in debug actions."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActionsList(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the debug actions list for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Get a list of all possible debug actions for the given site name.
    - Returns a list of debug actions.
    """
    checkSite(deps, sitename)
    out = {"actions": list(getactions(deps["config"])), "version": runningVersion}
    return APIResponse.genResponse(request, out)


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
            200: {
                "description": "Debug action information retrieved successfully",
                "content": {"application/json": {"example": {"debug_action_info": "example_debug_action_info"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Debug action <action> not found for site <sitename>.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_action": {"detail": "Debug action <action> not found for site <sitename>."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActionInfo(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    action: str = Query(..., description="The debug action to retrieve information for."),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("action")),
):
    """
    Get information about a specific debug action for the given site name.
    - Returns information about the debug action.
    """
    checkSite(deps, sitename)
    actions = getactions(deps["config"])
    if action not in actions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debug action '{action}' not found for site '{sitename}'.",
        )
    defaults = getactionkeys(deps["config"], action)
    out = {
        "action": action,
        "defaults": defaults,
        "keys": getactionkeys(deps["config"], action),
        "version": runningVersion,
    }
    return APIResponse.genResponse(request, out)


# =========================================================
# /api/{sitename}/dynamicfromranges
# =========================================================
@router.get(
    "/{sitename}/dynamicfromranges",
    summary="Get Dynamic From Ranges",
    description=("Returns a list of allowed dynamicfrom ranges for the given site name."),
    tags=["Debug"],
    responses={
        **{
            200: {
                "description": "Dynamic from ranges retrieved successfully",
                "content": {"application/json": {"example": {"dynamicfrom_ranges": "example_dynamicfrom_ranges"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Dynamic from ranges file not found for site <sitename>.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDynamicFromRanges(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the dynamicfrom ranges for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Get dynamic from ranges for the given site name.
    - Returns a list of allowed dynamicfrom ranges.
    """
    checkSite(deps, sitename)
    fpath = os.path.join(deps["config"].get(sitename, "privatedir"), "ServiceData", "workers-ranges.json")
    if not os.path.isfile(fpath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dynamic from ranges file not found for site '{sitename}'.",
        )
    out = getFileContentAsJson(fpath)
    return APIResponse.genResponse(request, out)


# =========================================================
# /api/{sitename}/debug
# =========================================================
@router.get(
    "/{sitename}/debug",
    summary="Get Debug Action",
    description=("Returns the debug actions for the given site name."),
    tags=["Debug"],
    responses={
        **{
            200: {
                "description": "Debug actions retrieved successfully. No action found returns empty array.",
                "content": {"application/json": {"example": {"debug_actions": "example_debug_actions"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDebugActions(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to get the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    debugvar: Optional[str] = Query(None, description="The debug action ID to retrieve information for."),
    limit: int = Query(
        LIMIT_DEFAULT,
        description="Limit the number of debug requests returned. Only applicable for debugvar 'ALL'.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    details: StrictBool = Query(False, description="If set, returns detailed information for the debug request."),
    hostname: str = Query(
        None,
        description="Hostname to filter the debug requests by. If not set, all debug requests are returned.",
    ),
    state: str = Query(
        None,
        description="State to filter the debug requests by. If not set, all debug requests are returned.",
    ),
    action: str = Query(
        None,
        description="Action to filter the debug requests by. If not set, all debug requests are returned.",
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit", "details", "hostname", "state", "action")),
):
    """
    Get debug actions for the given site name.
    - Returns a list of debug actions.
    """
    checkSite(deps, sitename)
    out = getDebugEntry(
        deps,
        debugvar=debugvar,
        hostname=hostname,
        state=state,
        details=details,
        limit=limit,
        action=action,
    )
    return APIResponse.genResponse(request, out)


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
        200: {
            "description": "Debug action information",
            "content": {"application/json": {"example": {"TODO": "Add example response here"}}},
        },
        404: {
            "description": "Debug request not found",
            "content": {"application/json": {"example": {"detail": "Debug request with ID <debugvar> not found."}}},
        },
    },
)
async def getDebugInfo(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to get the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    debugvar: str = Path(..., description="The debug action ID to retrieve information for."),
    limit: int = Query(
        LIMIT_DEFAULT,
        description="Limit the number of debug requests returned. Only applicable for debugvar 'ALL'.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    details: StrictBool = Query(False, description="If set, returns detailed information for the debug request."),
    hostname: str = Query(
        None,
        description="Hostname to filter the debug requests by. If not set, all debug requests are returned.",
    ),
    state: str = Query(
        None,
        description="State to filter the debug requests by. If not set, all debug requests are returned.",
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit", "details", "hostname", "state")),
):
    """Get Debug action information for a specific ID.
    In case of 'ALL', returns all debug requests.
    In case url param details is set, returns detailed information for the debug request.
    In case limit is set, returns limited number of debug requests. Only appliable for 'ALL'.
    - Returns the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    out = getDebugEntry(
        deps,
        debugvar=debugvar,
        hostname=hostname,
        state=state,
        details=details,
        limit=limit,
    )
    if not out:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debug request with ID {debugvar} not found.",
        )
    return APIResponse.genResponse(request, out)


@router.put(
    "/{sitename}/debug/{debugvar}",
    summary="Update Debug Action",
    description=("Updates the debug action information for the given debug ID."),
    tags=["Debug"],
    responses={
        200: {
            "description": "Debug action information updated successfully",
            "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}},
        },
        404: {
            "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Debug request with ID <debugvar> not found.",
            "content": {
                "application/json": {
                    "example": {
                        "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                        "debug_not_found": {"detail": "Debug request with ID <debugvar> not found."},
                    }
                }
            },
        },
    },
)
async def updatedebug(
    request: Request,
    item: DebugItem,
    sitename: str = Path(
        ...,
        description="The site name to get the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    debugvar: str = Path(..., description="The debug action ID to update information for."),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Update Debug action information.
    - Updates the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    dbentry = deps["dbI"].get("debugrequests", search=[["id", debugvar]])
    if not dbentry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debug request with ID {debugvar} not found.",
        )
    # ==================================
    # Write output file if output is set
    if item.output:
        dumpFileContentAsJson(dbentry[0]["outputinfo"], item.output)
    # Update the state in database.
    out = {"id": debugvar, "state": item.state, "updatedate": getUTCnow()}
    updOut = deps["dbI"].update("debugrequests", [out])
    return APIResponse.genResponse(request, {"Status": updOut[0], "ID": debugvar})


@router.delete(
    "/{sitename}/debug/{debugvar}",
    summary="Delete Debug Action Information",
    description=("Deletes the debug action information for the given debug ID."),
    tags=["Debug"],
    responses={
        200: {
            "description": "Debug action information deleted successfully",
            "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}},
        },
        404: {
            "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Debug request with ID <debugvar> not found.",
            "content": {
                "application/json": {
                    "example": {
                        "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                        "debug_not_found": {"detail": "Debug request with ID <debugvar> not found."},
                    }
                }
            },
        },
    },
)
async def deletedebug(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to get the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    debugvar: str = Path(..., description="The debug action ID to delete information for."),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Delete Debug action information.
    - Deletes the debug action information for the given debug ID.
    """
    checkSite(deps, sitename)
    dbentry = deps["dbI"].get("debugrequests", search=[["id", debugvar]])
    if not dbentry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Debug request with ID {debugvar} not found.",
        )
    # ==================================
    updOut = deps["dbI"].delete("debugrequests", [["id", debugvar]])
    if os.path.isfile(dbentry[0]["debuginfo"]):
        os.remove(dbentry[0]["debuginfo"])
    if os.path.isfile(dbentry[0]["outputinfo"]):
        os.remove(dbentry[0]["outputinfo"])
    # ==================================
    # Return the status and ID of the deleted debug request
    return APIResponse.genResponse(request, {"Status": updOut[0], "ID": updOut[2]})


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
        200: {
            "description": "Debug action request submitted successfully",
            "content": {"application/json": {"example": {"Status": "success", "ID": "<debug_id>"}}},
        },
        404: {
            "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Debug request with ID <debugvar> not found.",
            "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
        },
        400: {
            "description": "Bad request",
            "content": {"application/json": {"example": {"detail": "Bad Request. Possible reasons: Wrong value, parameter, input validation failed."}}},
        },
    },
)
async def submitdebug(
    request: Request,
    item: DebugItem,
    sitename: str = Path(
        ...,
        description="The site name to get the debug action information for.",
        example=startupConfig.get("SITENAME", "default"),
    ),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """Submit new debug action request.
    - Submits a new debug action request for the given site name.
    """
    checkSite(deps, sitename)
    # Insert dummy entry in the database with state pending, so that we get an ID back
    # This id is used for dynamic port generation for transfer service.
    dummyIns = deps["dbI"].insert(
        "debugrequests",
        [
            {
                "hostname": item.hostname,
                "state": "pending",
                "action": "undefined",
                "insertdate": getUTCnow(),
                "updatedate": getUTCnow(),
                "debuginfo": "undefined",
                "outputinfo": "undefined",
            }
        ],
    )
    try:
        inputDict = validator(deps["config"], dummyIns[2], item.request)
    except BadRequestError as exc:
        # Need to delete the dummy entry as validation failed
        deps["dbI"].delete("debugrequests", [["id", dummyIns[2]]])
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    try:
        debugdir = os.path.join(deps["config"].get(sitename, "privatedir"), "DebugRequests")
        randomuuid = generateRandomUUID()
        requestfname = os.path.join(debugdir, inputDict["hostname"], randomuuid, "request.json")
        outputfname = os.path.join(debugdir, inputDict["hostname"], randomuuid, "output.json")
        dumpFileContentAsJson(requestfname, inputDict)
        out = {
            "id": dummyIns[2],
            "hostname": inputDict.get("hostname", "undefined"),
            "state": "new",
            "action": inputDict["action"],
            "insertdate": getUTCnow(),
            "updatedate": getUTCnow(),
            "debuginfo": requestfname,
            "outputinfo": outputfname,
        }
        insOut = deps["dbI"].update("debugrequestsfull", [out])
        return APIResponse.genResponse(request, {"Status": insOut[0], "ID": dummyIns[2]})
    except Exception as exc:  # pylint: disable=broad-except
        print(f"Full traceback: {traceback.format_exc()}")
        # Need to delete the dummy entry as something failed
        deps["dbI"].delete("debugrequests", [["id", dummyIns[2]]])
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
