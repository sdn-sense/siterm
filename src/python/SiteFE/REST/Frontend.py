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
from fastapi import APIRouter, Depends, Path, HTTPException, status, Query

from SiteFE.REST.dependencies import allAPIDeps, checkSite
from SiteFE.REST.dependencies import DEFAULT_RESPONSES
from SiteRMLibs.MainUtilities import getFileContentAsJson
from SiteRMLibs.MainUtilities import evaldict

router = APIRouter()

# ==========================================================
# /api/frontend/sites
@router.get("/frontend/sites",
            summary="Get All Sites",
            description=("Returns a list of all sites configured in the system."),
            tags=["Frontend"],
            responses={**{
                200: {
                    "description": "List of all sites successfully returned.",
                    "content": {"application/json": {"example": ["T1_US_ESnet", "T2_US_ESnet"]}}
                },
                404: {
                    "description": "No sites configured in the system.",
                    "content": {"application/json": {"example": {"detail": "No sites configured in the system."}}}
                }
            },
            **DEFAULT_RESPONSES})
async def getAllSites(deps=Depends(allAPIDeps)):
    """
    Get a list of all sites configured in the system.
    - Returns a list of site names.
    """
    if not deps["config"]["MAIN"].get("general", {}).get("sites", []):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sites configured in the system."
        )
    out = deps["config"]["MAIN"].get("general", {}).get("sites", [])
    if not out:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No sites configured in the system."
        )
    return out

# =========================================================
# /api/frontend/configuration
# =========================================================
@router.get("/frontend/configuration",
            summary="Get Frontend Configuration",
            description=("Returns the frontend configuration in JSON format. "),
            tags=["Frontend"],
            responses={**{
                200: {
                    "description": "Frontend configuration successfully returned. This configuration is similar to the one used in github rm-configs repo (with preset-defaults).",
                    "content": {
                        "application/json": {
                            "example": {
                                "T9_US_SITENAME": {
                                    "domain": "sdn-sense.net",
                                    "latitude": 32.882648,
                                    "longitude": -117.234579,
                                    "plugin": "raw",
                                    "privatedir": "/opt/siterm/config/T9_US_SITENAME/",
                                    "switch": ["switchname1"],
                                    "year": 2025
                                },
                                "switchname1": {
                                    "ports": {
                                        "Pc500": {
                                            "capacity": 800000,
                                            "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500",
                                            "wanlink": True,
                                            "vlan_range": ["3611-3619"],
                                            "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615]
                                        },
                                        "Pc502": {
                                            "capacity": 400000,
                                            "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502",
                                            "wanlink": True,
                                            "vlan_range": ["3611-3619"],
                                            "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615]
                                        }
                                    },
                                    "vlan_range": ["3611-3619"],
                                    "vsw": "switchname1",
                                    "vswmp": "switchname1_mp",
                                    "qos_policy": {
                                        "default": 1,
                                        "bestEffort": 2,
                                        "softCapped": 4,
                                        "guaranteedCapped": 7
                                    },
                                    "rate_limit": False,
                                    "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                                    "all_vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                                },
                                "general": {
                                    "logLevel": "DEBUG",
                                    "privatedir": "/opt/siterm/config/",
                                    "probes": ["https_v4_siterm_2xx"],
                                    "sites": ["T9_US_SITENAME"],
                                    "webdomain": "https://web.sdn-sense.net:443",
                                    "logDir": "/var/log/siterm-site-fe/"
                                },
                                "ansible": {
                                    "private_data_dir": "/opt/siterm/config/ansible/sense/",
                                    "inventory": "/opt/siterm/config/ansible/sense/inventory/inventory.yaml",
                                    "inventory_host_vars_dir": "/opt/siterm/config/ansible/sense/inventory/host_vars/",
                                    "rotate_artifacts": 100,
                                    "ignore_logging": False,
                                    "verbosity": 0,
                                    "debug": False,
                                },
                                "debuggers": {
                                    "iperf-server": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True,
                                            "port": 5201
                                        }
                                    },
                                    "iperf-client": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "minstreams": 1,
                                        "maxstreams": 16,
                                        "defaults": {
                                            "onetime": True,
                                            "streams": 1
                                        }
                                    },
                                    "fdt-client": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "minstreams": 1,
                                        "maxstreams": 16,
                                        "defaults": {
                                            "onetime": True,
                                            "streams": 1
                                        }
                                    },
                                    "fdt-server": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True,
                                            "port": 54321
                                        }
                                    },
                                    "rapid-ping": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "maxmtu": 9000,
                                        "mininterval": 0.2,
                                        "maxtimeout": 30
                                    },
                                    "rapid-pingnet": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "maxtimeout": 30,
                                        "maxcount": 100,
                                        "defaults": {
                                            "onetime": True
                                        }
                                    },
                                    "arp-table": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True
                                        }
                                    },
                                    "tcpdump": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True
                                        }
                                    },
                                    "traceroute": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True
                                        }
                                    },
                                    "traceroutenet": {
                                        "defruntime": 600,
                                        "maxruntime": 86400,
                                        "defaults": {
                                            "onetime": True
                                        }
                                    }
                                },
                                "prefixes": {
                                    "mrs": "http://schemas.ogf.org/mrs/2013/12/topology#",
                                    "nml": "http://schemas.ogf.org/nml/2013/03/base#",
                                    "owl": "http://www.w3.org/2002/07/owl#",
                                    "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
                                    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
                                    "schema": "http://schemas.ogf.org/nml/2012/10/ethernet",
                                    "sd": "http://schemas.ogf.org/nsi/2013/12/services/definition#",
                                    "site": "urn:ogf:network",
                                    "xml": "http://www.w3.org/XML/1998/namespace#",
                                    "xsd": "http://www.w3.org/2001/XMLSchema#"
                                },
                                "servicedefinitions": {
                                    "debugip": "http://services.ogf.org/nsi/2019/08/descriptions/config-debug-ip",
                                    "globalvlan": "http://services.ogf.org/nsi/2019/08/descriptions/global-vlan-exclusion",
                                    "multipoint": "http://services.ogf.org/nsi/2018/06/descriptions/l2-mp-es",
                                    "l3bgpmp": "http://services.ogf.org/nsi/2019/08/descriptions/l3-bgp-mp"
                                },
                                "snmp": {
                                    "mibs": ["ifDescr", "ifType", "ifMtu", "ifAdminStatus", "ifOperStatus",
                                             "ifHighSpeed", "ifAlias", "ifHCInOctets", "ifHCOutOctets",
                                             "ifInDiscards", "ifOutDiscards", "ifInErrors", "ifOutErrors",
                                              "ifHCInUcastPkts", "ifHCOutUcastPkts", "ifHCInMulticastPkts",
                                              "ifHCOutMulticastPkts", "ifHCInBroadcastPkts", "ifHCOutBroadcastPkts"
                                    ]
                                }
                            }
                        }
                    }
                    },
                404: {
                    "description": "Frontend configuration file not found",
                    "content": {
                        "application/json": {
                            "example": {"detail": "Frontend configuration file not found for site"}
                        }
                    }
                }
            },
            **DEFAULT_RESPONSES})
async def getfeconfig(deps=Depends(allAPIDeps)):
    """
    Get frontend configuration in JSON format for the given site.
    - Returns frontend configuration as JSON if found, else 404 if file is missing.
    """
    if not deps.get("config", {}).getraw("MAIN"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Frontend configuration file not found for site"
        )
    return deps["config"]["MAIN"]

# =========================================================
# /api/{sitename}/frontend/getswitchdata
# =========================================================

@router.get("/{sitename}/frontend/getswitchdata",
            summary="Get Switch Data",
            description=("Returns switch data stored in the database for the specified site."),
            tags=["Frontend"],
            responses={**{
                200: {
                    "description": "Returns switch data stored in the database for the specified site.",
                    "content": {"application/json": {"example": [
                        {
                            "id": 2,
                            "sitename": "T9_US_JUSTASDEV",
                            "device": "fake1",
                            "insertdate": 1752233655,
                            "updatedate": 1753030607,
                            "output": "{\"event_data\": {\"res\": {\"ansible_facts\": {\"ansible_net_interfaces\": {\"Pc500\": {}, \"Pc502\": {}}}}}}"
                        },
                        {
                            "id": 1,
                            "sitename": "T2_US_UCSD_OASIS",
                            "device": "oasis",
                            "insertdate": 1752197919,
                            "updatedate": 1752231421,
                            "output": "{\"event_data\": {\"res\": {\"ansible_facts\": {\"ansible_net_interfaces\": {\"6_3_1\": {}, \"6_3_2\": {}, \"Pc459\": {}, \"Pc500\": {}, \"Pc502\": {}, \"Pc701\": {}}}}}}"
                        }
                        ]}}
                    },
                404: {
                    "description": "Not Found. Possible Reasons:\n"
                                   " - No sites configured in the system\n"
                                   " - No switch data available for the specified site.",
                    "content": {"application/json":
                                   {"example":
                                       {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                                        "no_switch_data": {"detail": "No switch data available for the specified site."}}}}
                }
                },
            **DEFAULT_RESPONSES})
async def getswitchdata(sitename: str = Path(..., description="The site name to retrieve the switch data for."),
                        limit: int = Query(10, description="The maximum number of results to return. Defaults to 10.", ge=1, le=100),
                        deps=Depends(allAPIDeps)):
    """
    Get switch data from the database of all registered switches.
    - Returns a list of switches with their information.
    """
    checkSite(deps, sitename)
    return deps["dbI"].get("switch", orderby=["updatedate", "DESC"], limit=limit)


# =========================================================
# /api/{sitename}/frontend/activedeltas
# =========================================================

@router.get("/{sitename}/frontend/activedeltas",
            summary="Get Active Deltas",
            description=("Returns the most recent active delta information from the database. This includes all parsed information from Submitted deltas and their current state."),
            tags=["Frontend"],
            responses={**{
                200: {
                    "description": "Returns the most recent active delta information. This includes all parsed information from Submitted deltas and their current state.",
                    "content": {"application/json": {"example": {
                                "id": 1,
                                "insertdate": 1752198423,
                                "updatedate": 1753031057,
                                "output": {
                                    "singleport": {},
                                    "vsw": {},
                                    "rst": {},
                                    "usedIPs": {
                                        "deltas": {},
                                        "system": {}
                                    },
                                    "usedVLANs": {
                                        "deltas": {},
                                        "system": {}
                                    }
                                }
                            }
                        }
                    }
                    }
                },
            **DEFAULT_RESPONSES})
async def getactivedeltas(
    sitename: str = Path(..., description="The site name to retrieve the active deltas for."),
    deps=Depends(allAPIDeps)):
    """
    Get active delta data from the database.
    - Returns a list of active deltas with their information.
    """
    checkSite(deps, sitename)
    activeDeltas = deps["dbI"].get(
        "activeDeltas", orderby=["insertdate", "DESC"], limit=1
    )
    if activeDeltas:
        activeDeltas = activeDeltas[0]
        activeDeltas["output"] = evaldict(activeDeltas["output"])
    else:
        activeDeltas = {"output": {}}
    return activeDeltas

# =========================================================
# /api/{sitename}/frontend/qosdata
# =========================================================
@router.get("/{sitename}/frontend/qosdata",
            summary="Get QoS Data",
            description=("Returns QoS statistics for all IPv6 ranges. This includes the maximum throughput for each range based on the configured QoS policies and interface capabilities, usage. Used in calculating QoS parameters for the host."),
            tags=["Frontend"],
            responses={**{
                200: {
                    "description": "QoS data successfully returned.",
                    "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}
                    },
                404: {
                    "description": "Not Found. Possible Reasons:\n"
                                   " - No sites configured in the system.",
                    "content": {"application/json":
                                   {"example":
                                       {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}}
                }
                },
            **DEFAULT_RESPONSES})
async def getqosdata(
    sitename: str = Path(..., description="The site name to retrieve the QoS data for."),
    limit: int = Query(100, description="The maximum number of hosts to lookup. Defaults to 100.", ge=1, le=100),
    deps=Depends(allAPIDeps)):
    """
    Get QoS data from the database.
    - Returns a list of QoS data with their information.
    """
    checkSite(deps, sitename)
    # pylint: disable=too-many-nested-blocks
    hosts = deps["dbI"].get("hosts", orderby=["updatedate", "DESC"], limit=limit)
    out = {}
    for host in hosts:
        tmpH = getFileContentAsJson(host.get("hostinfo", ""))
        tmpInf = (
            tmpH.get("Summary", {})
            .get("config", {})
            .get("qos", {})
            .get("interfaces", {})
        )
        if not tmpInf:
            continue
        for _intf, intfDict in tmpInf.items():
            maxThrg = (
                tmpH.get("Summary", {})
                .get("config", {})
                .get(intfDict["master_intf"], {})
                .get("bwParams", {})
                .get("maximumCapacity", None)
            )
            if maxThrg:
                for ipkey in ["ipv4", "ipv6"]:
                    tmpIP = intfDict.get(f"{ipkey}_range", None)
                    if isinstance(tmpIP, list):
                        for ipaddr in tmpIP:
                            out.setdefault(ipaddr, 0)
                            out[ipaddr] += maxThrg
                    elif tmpIP:
                        out.setdefault(tmpIP, 0)
                        out[tmpIP] += maxThrg
            else:
                print(
                    f"QoS Configure for {intfDict['master_intf']}, but it is not defined in agent config. Misconfig."
                )
    return [out]
