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
import os
from fastapi import APIRouter, Path, Depends, HTTPException, status

from SiteRMLibs.MainUtilities import getFileContentAsJson
from SiteFE.REST.dependencies import allAPIDeps, DEFAULT_RESPONSES, checkSite

router = APIRouter()

# =========================================================
# /api/{sitename}/topo/gettopology
# =========================================================

@router.get("/{sitename}/topo/gettopology",
            summary="Get Topology JSON",
            description=("Returns the topology in JSON format for the given site name. "
                         "If the topology file is not found, a 404 error is returned."),
            tags=["Topology"],
            responses={**{
                200: {
                    "description": "Topology JSON successfully returned",
                    "content": {
                        "application/json": {
                            "example": {
                                "switchname1":{
                                    "topo":{},
                                    "DeviceInfo":{
                                        "type":"switch",
                                        "name":"switchname1"},
                                    "_id":0},
                                "wan2":{
                                    "_id":2,
                                    "topo":{
                                        "PortChannel500":{
                                            "device":"switchname1",
                                            "port":{
                                                "capacity":800000,
                                                "isAlias":"urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500"
                                                ,"wanlink":True,
                                                "vlan_range":["3611-3619"],
                                                "vlan_range_list":[3616,3617,3618,3619,3611,3612,3613,3614,3615]
                                            }
                                        }
                                    },
                                    "DeviceInfo":{
                                        "type":"cloud",
                                        "name":"urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500"
                                    }
                                },
                                "wan3":{
                                    "_id":3,
                                    "topo":{
                                        "Port-Channel502":{
                                            "device":"switchname1",
                                            "port":{
                                                "capacity":400000,
                                                "isAlias":"urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502",
                                                "wanlink":True,
                                                "vlan_range":["3611-3619"],
                                                "vlan_range_list":[3616,3617,3618,3619,3611,3612,3613,3614,3615]
                                            }
                                        }
                                    },
                                    "DeviceInfo":{
                                        "type":"cloud",
                                        "name":"urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502"
                                    }
                                }
                            }
                        }
                    }
                },
                404: {
                    "description": "Topology file not found",
                    "content": {
                        "application/json": {
                            "example": {"detail": "Topology file not found for site"}
                        }
                    }
                }
            },
            **DEFAULT_RESPONSES})
async def gettopology(sitename: str = Path(..., description="The site name whose topology is requested.", example="T0_US_ESnet"),
                      deps=Depends(allAPIDeps)):
    """
    Get topology in JSON format for the given site.

    - **sitename**: The site name whose topology is requested.
    - Returns topology as JSON if found, else 404 if file is missing.
    """
    checkSite(deps, sitename)
    topodir = os.path.join(deps["config"].get(sitename, "privatedir"), "Topology")
    topofname = os.path.join(topodir, "topology.json")
    if not os.path.isfile(topofname):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Topology file not found for site '{sitename}'"
        )
    topo_data = getFileContentAsJson(topofname)
    return topo_data
