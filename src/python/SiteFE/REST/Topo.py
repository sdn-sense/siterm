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
    buildArchifyIR,
    renderArchifyHTML,
)
from SiteRMLibs.MainUtilities import getFileContentAsJson, getstartupconfig

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
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("switch", "server")),
):
    """
    Get topology rendered as an Archify HTML diagram.

    - **sitename**: The site name whose topology is requested.
    - **switch** / **server**: Optional device filters.
    """
    checkSite(deps, sitename)
    archIR = buildArchifyIR(loadTopology(deps, sitename), sitename, switch, server)
    if not archIR["components"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No topology devices match the selected filters for site '{sitename}'",
        )
    try:
        html = await asyncio.to_thread(renderArchifyHTML, archIR)
    except ArchifyUnavailable as ex:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"Archify renderer unavailable: {ex}") from ex
    except ArchifyRenderError as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Archify failed to render topology: {ex}") from ex
    return HTMLResponse(content=html, headers=ARCHIFY_HEADERS)
