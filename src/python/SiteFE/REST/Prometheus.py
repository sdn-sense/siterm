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
from fastapi import APIRouter, Depends, HTTPException, Response, status, Path

from prometheus_client import CONTENT_TYPE_LATEST

from SiteFE.REST.dependencies import allAPIDeps, checkSite
from SiteFE.REST.dependencies import DEFAULT_RESPONSES

router = APIRouter()

# =========================================================
# /api/{sitename}/prometheus/metrics
# =========================================================
@router.get("/{sitename}/prometheus/metrics",
            summary="Get Service Metrics",
            description=("Retrieves service metrics from Prometheus."),
            tags=["Service Metrics"],
            responses={**{
                200: {
                    "description": "TODO",
                    "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}
                    },
                },
            **DEFAULT_RESPONSES})
async def getprommetrics(
    sitename: str = Path(..., description="The site name to retrieve the service metrics for."),
    deps=Depends(allAPIDeps)):
    """
    Get service metrics from Prometheus.
    """
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
# /prometheus/passthrough
# =========================================================
# TODO: Implement a passthrough endpoint for Prometheus queries
@router.get("/{sitename}/prometheus/passthrough/{hostname}",
            summary="Prometheus Passthrough",
            description=("This endpoint is a passthrough of host-level Prometheus output."),
            tags=["Service Metrics"],
            responses={**{
                200: {
                    "description": "TODO",
                    "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}
                    },
                },
            **DEFAULT_RESPONSES})
async def prometheuspassthrough(
    _sitename: str = Path(..., description="The site name to retrieve the Prometheus passthrough for."),
    hostname: str = Path(..., description="The hostname to retrieve the Prometheus passthrough for."),
    deps=Depends(allAPIDeps)):
    """
    This endpoint is a passthrough of host-level Prometheus output.
    """
    # Placeholder for actual implementation
    # This should check if the hostname is valid and then forward the request to the appropriate Prometheus endpoint
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="Prometheus passthrough not implemented yet")
