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
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    allAPIDeps,
    checkReadyState,
    checkSite,
)
from SiteRMLibs.DefaultParams import (
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
    SERVICE_DOWN_TIMEOUT,
)
from SiteRMLibs.MainUtilities import evaldict, getFileContentAsJson, getUTCnow

router = APIRouter()


# =========================================================
# /api/alive
# =========================================================
@router.get(
    "/alive",
    summary="Check API Health",
    description=("Checks if the API is alive and responsive. It does not check readiness or liveness."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "API is alive.", "content": {"application/json": {"example": {"status": "alive"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def checkAPIHealth(request: Request, _deps=Depends(allAPIDeps)):
    """
    Check the health of the API.
    """
    return APIResponse.genResponse(request, {"status": "alive"})


# =========================================================
# /api/ready
# =========================================================
@router.get(
    "/ready",
    summary="Check API Readiness",
    description=("Checks if the API is ready to serve requests. It requires to wait for LookupService and ProvisioningService to be ready after first run."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "API is ready.", "content": {"application/json": {"example": {"status": "ready"}}}},
            503: {"description": "API is not ready to serve requests.", "content": {"application/json": {"example": {"detail": "API is not ready to serve requests."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def checkAPIReady(request: Request, deps=Depends(allAPIDeps)):
    """
    Check the readiness of the API.
    """
    if not checkReadyState(deps):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="API is not ready to serve requests.")
    return APIResponse.genResponse(request, {"status": "ready"})


# =========================================================
# /api/liveness
# =========================================================
@router.get(
    "/liveness",
    summary="Check API Liveness Status",
    description=("Checks if the API Liveness is functioning correctly. Possible values: ok, error, disabled, unknown."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "Liveness status", "content": {"application/json": {"example": {"status": "ok"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def checkAPILiveness(request: Request, _deps=Depends(allAPIDeps)):
    """
    Check the health of the API.
    """
    if os.path.exists("/tmp/siterm-liveness-disabled"):
        return APIResponse.genResponse(request, {"status": "disabled"})
    if os.path.exists("/tmp/siterm-liveness"):
        with open("/tmp/siterm-liveness", "r", encoding="utf-8") as fd:
            code = fd.read().strip()
            if code == "0":
                return APIResponse.genResponse(request, {"status": "ok"})
            return APIResponse.genResponse(request, {"status": "error", "code": code})
    return APIResponse.genResponse(request, {"status": "unknown", "code": "liveness file not found"})


# =========================================================
# /api/readiness
# =========================================================
@router.get(
    "/readiness",
    summary="Check API Readiness",
    description=("Checks if the API is ready to serve requests. Possible values: ok, error, disabled, unknown."),
    tags=["Frontend"],
    responses={
        **{200: {"description": "API is ready.", "content": {"application/json": {"example": {"status": "ok"}}}}},
        **DEFAULT_RESPONSES,
    },
)
async def checkAPIReadiness(request: Request, _deps=Depends(allAPIDeps)):
    """
    Check the readiness of the API.
    """
    if os.path.exists("/tmp/siterm-readiness-disabled"):
        return APIResponse.genResponse(request, {"status": "disabled"})
    if os.path.exists("/tmp/siterm-readiness"):
        with open("/tmp/siterm-readiness", "r", encoding="utf-8") as fd:
            code = fd.read().strip()
            if code == "0":
                return APIResponse.genResponse(request, {"status": "ok"})
            return APIResponse.genResponse(request, {"status": "error", "code": code})
    return APIResponse.genResponse(request, {"status": "unknown", "code": "readiness file not found"})


# ==========================================================
# /api/frontend/sites
# ==========================================================
@router.get(
    "/frontend/sitename",
    summary="Get Site Name",
    description=("Returns the sitename configured in the system."),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "Site name successfully returned.", "content": {"application/json": {"example": ["T1_US_ESnet"]}}},
            404: {"description": "No site configured in the system.", "content": {"application/json": {"example": {"detail": "No site configured in the system."}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getAllSites(request: Request, deps=Depends(allAPIDeps)):
    """
    Get a site name configured in the system.
    - Returns a site name in a list.
    """
    if not deps["config"]["MAIN"].get("general", {}).get("sitename", []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No site configured in the system.")
    out = deps["config"]["MAIN"].get("general", {}).get("sitename", [])
    if not out:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No site configured in the system.")
    return APIResponse.genResponse(request, [out])


# =========================================================
# /api/frontend/configuration
# =========================================================
@router.get(
    "/frontend/configuration",
    summary="Get Frontend Configuration",
    description=("Returns the frontend configuration in JSON format. "),
    tags=["Frontend"],
    responses={
        **{
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
                                "year": 2025,
                            },
                            "switchname1": {
                                "ports": {
                                    "Pc500": {
                                        "capacity": 800000,
                                        "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:PortChannel500",
                                        "wanlink": True,
                                        "vlan_range": ["3611-3619"],
                                        "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                                    },
                                    "Pc502": {
                                        "capacity": 400000,
                                        "isAlias": "urn:ogf:network:sense-isAlias-sdn-sense.dev:2025:switchname2:Port-Channel502",
                                        "wanlink": True,
                                        "vlan_range": ["3611-3619"],
                                        "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                                    },
                                },
                                "vlan_range": ["3611-3619"],
                                "vsw": "switchname1",
                                "vswmp": "switchname1_mp",
                                "qos_policy": {"traffic_classes": {"default": 1, "bestEffort": 2, "softCapped": 4, "guaranteedCapped": 7}, "max_policy_rate": "268000", "burst_size": "256"},
                                "rate_limit": False,
                                "vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                                "all_vlan_range_list": [3616, 3617, 3618, 3619, 3611, 3612, 3613, 3614, 3615],
                            },
                            "general": {
                                "logLevel": "DEBUG",
                                "privatedir": "/opt/siterm/config/",
                                "probes": ["https_v4_siterm_2xx"],
                                "sitename": "T9_US_SITENAME",
                                "webdomain": "https://web.sdn-sense.net:443",
                                "logDir": "/var/log/siterm-site-fe/",
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
                                "iperf-server": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True, "port": 5201}},
                                "iperf-client": {"deftime": 600, "maxruntime": 86400, "minstreams": 1, "maxstreams": 16, "defaults": {"onetime": True, "streams": 1}},
                                "fdt-client": {"deftime": 600, "maxruntime": 86400, "minstreams": 1, "maxstreams": 16, "defaults": {"onetime": True, "streams": 1}},
                                "fdt-server": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True, "port": 54321}},
                                "rapid-ping": {"deftime": 600, "maxruntime": 86400, "maxmtu": 9000, "mininterval": 0.2, "maxtimeout": 30},
                                "rapid-pingnet": {"deftime": 600, "maxruntime": 86400, "maxtimeout": 30, "maxcount": 100, "defaults": {"onetime": True}},
                                "arp-table": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True}},
                                "tcpdump": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True}},
                                "traceroute": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True}},
                                "traceroutenet": {"deftime": 600, "maxruntime": 86400, "defaults": {"onetime": True}},
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
                                "xsd": "http://www.w3.org/2001/XMLSchema#",
                            },
                            "servicedefinitions": {
                                "debugip": "http://services.ogf.org/nsi/2019/08/descriptions/config-debug-ip",
                                "globalvlan": "http://services.ogf.org/nsi/2019/08/descriptions/global-vlan-exclusion",
                                "multipoint": "http://services.ogf.org/nsi/2018/06/descriptions/l2-mp-es",
                                "l3bgpmp": "http://services.ogf.org/nsi/2019/08/descriptions/l3-bgp-mp",
                            },
                            "snmp": {
                                "mibs": [
                                    "ifDescr",
                                    "ifType",
                                    "ifMtu",
                                    "ifAdminStatus",
                                    "ifOperStatus",
                                    "ifHighSpeed",
                                    "ifAlias",
                                    "ifHCInOctets",
                                    "ifHCOutOctets",
                                    "ifInDiscards",
                                    "ifOutDiscards",
                                    "ifInErrors",
                                    "ifOutErrors",
                                    "ifHCInUcastPkts",
                                    "ifHCOutUcastPkts",
                                    "ifHCInMulticastPkts",
                                    "ifHCOutMulticastPkts",
                                    "ifHCInBroadcastPkts",
                                    "ifHCOutBroadcastPkts",
                                ]
                            },
                        }
                    }
                },
            },
            404: {"description": "Frontend configuration file not found", "content": {"application/json": {"example": {"detail": "Frontend configuration file not found for site"}}}},
        },
        **DEFAULT_RESPONSES,
    },
)
async def getfeconfig(request: Request, deps=Depends(allAPIDeps)):
    """
    Get frontend configuration in JSON format for the given site.
    - Returns frontend configuration as JSON if found, else 404 if file is missing.
    """
    if not deps.get("config", {}).getraw("MAIN"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Frontend configuration file not found for site")
    return APIResponse.genResponse(request, deps["config"]["MAIN"])


# =========================================================
# /api/{sitename}/frontend/getswitchdata
# =========================================================


@router.get(
    "/{sitename}/frontend/getswitchdata",
    summary="Get Switch Data",
    description=("Returns switch data stored in the database for the specified site."),
    tags=["Frontend"],
    responses={
        **{
            200: {
                "description": "Returns switch data stored in the database for the specified site.",
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "id": 2,
                                "sitename": "T9_US_JUSTASDEV",
                                "device": "fake1",
                                "insertdate": 1752233655,
                                "updatedate": 1753030607,
                                "output": '{"event_data": {"res": {"ansible_facts": {"ansible_net_interfaces": {"Pc500": {}, "Pc502": {}}}}}}',
                            },
                            {
                                "id": 1,
                                "sitename": "T2_US_UCSD_OASIS",
                                "device": "oasis",
                                "insertdate": 1752197919,
                                "updatedate": 1752231421,
                                "output": '{"event_data": {"res": {"ansible_facts": {"ansible_net_interfaces": {"6_3_1": {}, "6_3_2": {}, "Pc459": {}, "Pc500": {}, "Pc502": {}, "Pc701": {}}}}}}',
                            },
                        ]
                    }
                },
            },
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system\n" " - No switch data available for the specified site.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_switch_data": {"detail": "No switch data available for the specified site."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getswitchdata(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the switch data for."),
    limit: int = Query(LIMIT_DEFAULT, description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.", ge=LIMIT_MIN, le=LIMIT_MAX),
    deps=Depends(allAPIDeps),
):
    """
    Get switch data from the database of all registered switches.
    - Returns a list of switches with their information.
    """
    checkSite(deps, sitename)
    return APIResponse.genResponse(request, deps["dbI"].get("switch", orderby=["updatedate", "DESC"], limit=limit))


# =========================================================
# /api/{sitename}/frontend/activedeltas
# =========================================================


@router.get(
    "/{sitename}/frontend/activedeltas",
    summary="Get Active Deltas",
    description=("Returns the most recent active delta information from the database. This includes all parsed information from Submitted deltas and their current state."),
    tags=["Frontend"],
    responses={
        **{
            200: {
                "description": "Returns the most recent active delta information. This includes all parsed information from Submitted deltas and their current state.",
                "content": {
                    "application/json": {
                        "example": {
                            "id": 1,
                            "insertdate": 1752198423,
                            "updatedate": 1753031057,
                            "output": {"singleport": {}, "vsw": {}, "rst": {}, "usedIPs": {"deltas": {}, "system": {}}, "usedVLANs": {"deltas": {}, "system": {}}},
                        }
                    }
                },
            }
        },
        **DEFAULT_RESPONSES,
    },
)
async def getactivedeltas(request: Request, sitename: str = Path(..., description="The site name to retrieve the active deltas for."), deps=Depends(allAPIDeps)):
    """
    Get active delta data from the database.
    - Returns a list of active deltas with their information.
    """
    checkSite(deps, sitename)
    activeDeltas = deps["dbI"].get("activeDeltas", orderby=["insertdate", "DESC"], limit=1)
    if activeDeltas:
        activeDeltas = activeDeltas[0]
        activeDeltas["output"] = evaldict(activeDeltas["output"])
    else:
        activeDeltas = {"output": {}}
    return APIResponse.genResponse(request, activeDeltas)


# =========================================================
# /api/{sitename}/frontend/qosdata
# =========================================================
@router.get(
    "/{sitename}/frontend/qosdata",
    summary="Get QoS Data",
    description=(
        "Returns QoS statistics for all IPv6 ranges. This includes the maximum throughput for each range based on the configured QoS policies and interface capabilities, usage. Used in calculating QoS parameters for the host."
    ),
    tags=["Frontend"],
    responses={
        **{
            200: {"description": "QoS data successfully returned.", "content": {"application/json": {"TODO": "ADD OUTPUT EXAMPLE HERE"}}},
            404: {
                "description": "Not Found. Possible Reasons:\n" " - No sites configured in the system.",
                "content": {"application/json": {"example": {"no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getqosdata(
    request: Request,
    sitename: str = Path(..., description="The site name to retrieve the QoS data for."),
    limit: int = Query(LIMIT_DEFAULT, description=f"The maximum number of hosts to lookup. Defaults to {LIMIT_DEFAULT}.", ge=LIMIT_MIN, le=LIMIT_MAX),
    deps=Depends(allAPIDeps),
):
    """
    Get QoS data from the database.
    - Returns a list of QoS data with their information.
    """
    checkSite(deps, sitename)
    # pylint: disable=too-many-nested-blocks
    hosts = deps["dbI"].get("hosts", orderby=["updatedate", "DESC"], limit=limit)
    out = {}
    for host in hosts:
        if host.get("updatedate", 0) and (int(host["updatedate"]) + SERVICE_DOWN_TIMEOUT) < getUTCnow():
            print(f"Host {host.get('hostname', 'null')} did not update state for {SERVICE_DOWN_TIMEOUT} , skipping QoS data calculation for it.")
            continue
        if not host.get("hostinfo", ""):
            print(f"Host {host.get('hostname', 'null')} does not have hostinfo, skipping QoS data calculation for it.")
            continue
        tmpH = getFileContentAsJson(host.get("hostinfo", ""))
        tmpInf = tmpH.get("Summary", {}).get("config", {}).get("qos", {}).get("interfaces", {})
        if not tmpInf:
            continue
        for _intf, intfDict in tmpInf.items():
            maxThrg = tmpH.get("Summary", {}).get("config", {}).get(intfDict["master_intf"], {}).get("bwParams", {}).get("maximumCapacity", None)
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
                print(f"QoS Configure for {intfDict['master_intf']} {host.get('hostname', 'null')}, but it is not defined in agent config. Misconfig.")
    return APIResponse.genResponse(request, [out])
