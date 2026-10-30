#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Topology API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""

import asyncio
import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from fastapi.responses import HTMLResponse
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    apiReadDeps,
    checkSite,
    forbidExtraQueryParams,
)
from SiteRMLibs.ArchifyTopology import (
    ArchifyRenderError,
    ArchifyUnavailable,
    activePath,
    activePaths,
    buildDiagram,
    renderDiagramHTML,
    summarizeServiceStates,
)
from SiteRMLibs.MainUtilities import (
    evaldict,
    getFileContentAsJson,
    getstartupconfig,
    getUTCnow,
)

router = APIRouter()

startupConfig = getstartupconfig()

# The rendered page runs its own scripts; force an opaque origin even if the URL is opened directly.
ARCHIFY_HEADERS = {
    "Content-Security-Policy": "sandbox allow-scripts allow-downloads",
    "X-Content-Type-Options": "nosniff",
    "Cache-Control": "no-store",
}


def loadTopology(deps, sitename):
    """Load topology.json for the site or raise 404."""
    topodir = os.path.join(deps["config"].get(sitename, "privatedir"), "Topology")
    topofname = os.path.join(topodir, "topology.json")
    if not os.path.isfile(topofname):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology file not found for site '{sitename}'",
        )
    return getFileContentAsJson(topofname)


def loadActiveDeltas(deps):
    """Return the activeDeltas output (empty dict when there are none)."""
    rows = deps["dbI"].get("activeDeltas", orderby=["insertdate", "DESC"], limit=1)
    return evaldict(rows[0]["output"]) if rows else {}


# =========================================================
# /api/{sitename}/topo/gettopology
# =========================================================


@router.get(
    "/{sitename}/topo/gettopology",
    summary="Get Topology JSON",
    description=("Returns the topology in JSON format for the given site name. If the topology file is not found, a 404 error is returned."),
    tags=["Topology"],
    responses={
        **{
            200: {
                "description": "Topology JSON successfully returned",
                "content": {
                    "application/json": {
                        "example": {
                            "switchname1": {
                                "topo": {},
                                "DeviceInfo": {"type": "switch", "name": "switchname1"},
                                "_id": 0,
                            },
                            "wan2": {
                                "_id": 2,
                                "topo": {
                                    "PortChannel500": {
                                        "device": "switchname1",
                                        "port": {
                                            "capacity": 800000,
                                            "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500",
                                            "wanlink": True,
                                            "vlan_range": ["3611-3619"],
                                            "vlan_range_list": [
                                                3616,
                                                3617,
                                                3618,
                                                3619,
                                                3611,
                                                3612,
                                                3613,
                                                3614,
                                                3615,
                                            ],
                                        },
                                    }
                                },
                                "DeviceInfo": {
                                    "type": "cloud",
                                    "name": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500",
                                },
                            },
                            "wan3": {
                                "_id": 3,
                                "topo": {
                                    "Port-Channel502": {
                                        "device": "switchname1",
                                        "port": {
                                            "capacity": 400000,
                                            "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502",
                                            "wanlink": True,
                                            "vlan_range": ["3611-3619"],
                                            "vlan_range_list": [
                                                3616,
                                                3617,
                                                3618,
                                                3619,
                                                3611,
                                                3612,
                                                3613,
                                                3614,
                                                3615,
                                            ],
                                        },
                                    }
                                },
                                "DeviceInfo": {
                                    "type": "cloud",
                                    "name": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502",
                                },
                            },
                        }
                    }
                },
            },
            404: {
                "description": "Topology file not found",
                "content": {"application/json": {"example": {"detail": "Topology file not found for site"}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def gettopology(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name whose topology is requested.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Get topology in JSON format for the given site.

    - **sitename**: The site name whose topology is requested.
    - Returns topology as JSON if found, else 404 if file is missing.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, loadTopology(deps, sitename))


# =========================================================
# /api/{sitename}/topo/archify
# =========================================================


@router.get(
    "/{sitename}/topo/archify",
    summary="Get Topology as Archify diagram",
    description=(
        "Renders the site topology as a self-contained Archify HTML diagram. "
        "Optional repeated `switch` and `server` query parameters limit the diagram to those devices; WAN peers follow their switches."
    ),
    tags=["Topology"],
    response_class=HTMLResponse,
    responses={
        **{
            200: {"description": "Archify HTML diagram", "content": {"text/html": {}}},
            404: {
                "description": "Topology file not found or no devices match the filters",
                "content": {"application/json": {"example": {"detail": "Topology file not found for site"}}},
            },
            500: {
                "description": "Archify rejected or failed to render the diagram",
                "content": {"application/json": {"example": {"detail": "Archify failed to render topology: ..."}}},
            },
            503: {
                "description": "Archify renderer is not installed",
                "content": {"application/json": {"example": {"detail": "Archify renderer unavailable: ..."}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getarchify(
    sitename: str = Path(
        ...,
        description="The site name whose topology is requested.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    switch: Optional[List[str]] = Query(None, description="Only include these switches (repeatable)."),
    server: Optional[List[str]] = Query(None, description="Only include these servers (repeatable)."),
    path: Optional[str] = Query(None, max_length=1024, description="Only show the devices and links of this active L2 connection id."),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("switch", "server", "path")),
):
    """
    Get topology rendered as an Archify HTML diagram.

    - **sitename**: The site name whose topology is requested.
    - **switch** / **server**: Optional device filters.
    """
    checkSite(deps, sitename)
    filters = {"switch": switch, "server": server}
    if path:
        filters["path"] = activePath(loadActiveDeltas(deps), path)
        if filters["path"] is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Active connection '{path}' not found for site '{sitename}'")
    health = summarizeServiceStates(deps["dbI"].get("servicestates"), getUTCnow())
    diagram = buildDiagram(loadTopology(deps, sitename), sitename, filters, health)
    if not diagram["ir"]["components"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No topology devices match the selected filters for site '{sitename}'",
        )
    try:
        html = await asyncio.to_thread(renderDiagramHTML, diagram)
    except ArchifyUnavailable as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Archify renderer unavailable: {ex}") from ex
    except ArchifyRenderError as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Archify failed to render topology: {ex}") from ex
    return HTMLResponse(content=html, headers=ARCHIFY_HEADERS)


# =========================================================
# /api/{sitename}/topo/paths
# =========================================================


@router.get(
    "/{sitename}/topo/paths",
    summary="List active L2 paths",
    description="Lists active L2 connections (activeDeltas vsw) with their VLANs, state and devices, for the topology path filter.",
    tags=["Topology"],
    responses={
        200: {"description": "Active L2 connections", "content": {"application/json": {"example": [{"id": "urn:...:conn+abc", "state": "activated", "vlans": [3610], "devices": ["sw1", "dtn1"]}]}}},
        **DEFAULT_RESPONSES,
    },
)
async def getpaths(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name whose active paths are requested.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    List active L2 connections for the topology path filter.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, activePaths(loadActiveDeltas(deps)))
