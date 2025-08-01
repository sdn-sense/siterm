#!/usr/bin/env python3
# pylint: disable=line-too-long
"""
Prometheus API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""
import os
from typing import Any, Dict

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
from prometheus_client import CONTENT_TYPE_LATEST
from pydantic import BaseModel
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    allAPIDeps,
    checkSite,
)
from SiteRMLibs.DefaultParams import LIMIT_DEFAULT, LIMIT_MAX, LIMIT_MIN
from SiteRMLibs.MainUtilities import getUTCnow, jsondumps

router = APIRouter()


# =========================================================
# /api/{sitename}/monitoring/prometheus/metrics
# =========================================================
@router.get(
    "/{sitename}/monitoring/prometheus/metrics",
    summary="Get Prometheus Metrics for Site",
    description=("Retrieves service metrics from Prometheus."),
    tags=["Monitoring Metrics"],
    responses={
        **{
            200: {"description": "TODO", "content": {CONTENT_TYPE_LATEST: {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getprommetrics(sitename: str = Path(..., description="The site name to retrieve the service metrics for."), deps=Depends(allAPIDeps)):
    """
    Get service metrics from Prometheus.
    """
    checkSite(deps, sitename)
    snmpdir = os.path.join(deps["config"].get(sitename, "privatedir"), "SNMPData")
    fname = os.path.join(snmpdir, "snmpinfo.txt")
    if not os.path.exists(fname):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics are not available")
    try:
        with open(fname, "rb") as fd:
            data = fd.read()
        return Response(content=data, media_type=CONTENT_TYPE_LATEST)
    except FileNotFoundError as ex:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metrics are not available") from ex
    except Exception as ex:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Unable to retrieve metrics") from ex


# =========================================================
# /{sitename}/monitoring/prometheus/passthrough/{hostname}
# =========================================================
# TODO
@router.get(
    "/{sitename}/monitoring/prometheus/passthrough/{hostname}",
    summary="Prometheus monitoring Passthrough",
    description=("This endpoint is a passthrough to a host-level Prometheus output."),
    tags=["Monitoring Metrics"],
    responses={
        **{
            200: {"description": "TODO", "content": {CONTENT_TYPE_LATEST: {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def prometheuspassthrough(
    sitename: str = Path(..., description="The site name to retrieve the Prometheus passthrough for."),
    hostname: str = Path(..., description="The hostname to retrieve the Prometheus passthrough for."),
    deps=Depends(allAPIDeps),
):
    """
    This endpoint is a passthrough of host-level Prometheus output.
    """
    checkSite(deps, sitename)
    # Placeholder for actual implementation
    # This should check if the hostname is valid and then forward the request to the appropriate Prometheus endpoint
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Prometheus passthrough not implemented yet")


# =========================================================
# /{sitename}/monitoring/stats
# =========================================================
class MonStats(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    hostname: str
    output: Dict[str, Any]


@router.get(
    "/{sitename}/monitoring/stats",
    summary="Get Monitoring Statistics for Site",
    description=("Retrieves monitoring statistics for a specific site."),
    tags=["Monitoring Metrics"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getmonitoringstats(
    request: Request,
    limit: int = Query(LIMIT_DEFAULT, description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.", ge=LIMIT_MIN, le=LIMIT_MAX),
    sitename: str = Path(..., description="The site name to retrieve the monitoring statistics for."),
    deps=Depends(allAPIDeps),
):
    """
    Get monitoring statistics for a specific site.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, deps["dbI"].get("snmpmon", orderby=["updatedate", "DESC"], limit=limit))


@router.post(
    "/{sitename}/monitoring/stats",
    summary="Post Monitoring Statistics for Site",
    description=("Posts monitoring statistics for a specific site."),
    tags=["Monitoring Metrics"],
    responses={
        **{
            200: {"description": "TODO", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def postmonitoringstats(
    item: MonStats,
    request: Request,
    sitename: str = Path(..., description="The site name to post the monitoring statistics for."),
    deps=Depends(allAPIDeps),
):
    """
    Post monitoring statistics for a specific site.
    """
    checkSite(deps, sitename)
    host = deps["dbI"].get("snmpmon", limit=1, search=[["hostname", item.hostname]])
    updatestate = "UPDATED"
    if host:
        out = {"id": host[0]["id"], "hostname": item.hostname, "updatedate": getUTCnow(), "output": jsondumps(item.output)}
        deps["dbI"].update("snmpmon", [out])
    else:
        out = {"hostname": item.hostname, "insertdate": getUTCnow(), "updatedate": getUTCnow(), "output": jsondumps(item.output)}
        updatestate = "INSERTED"
        deps["dbI"].insert("snmpmon", [out])
    return APIResponse.genResponse(request, {"Status": updatestate})
