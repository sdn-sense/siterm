#!/usr/bin/env python3
# pylint: disable=line-too-long, too-many-arguments, too-many-positional-arguments
"""
Delta API Calls
Title                   : siterm
Author                  : Justas Balcas
Email                   : jbalcas (at) es (dot) net
@Copyright              : Copyright (C) 2025 ESnet
@License                : Apache License, Version 2.0
Date                    : 2025/07/14
"""

import hashlib
import os
from asyncio import sleep
from contextlib import suppress
from typing import Literal, Optional

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Path,
    Query,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, constr
from SiteFE.REST.dependencies import (
    DEFAULT_RESPONSES,
    APIResponse,
    StrictBool,
    apiReadDeps,
    apiWriteDeps,
    checkReadyState,
    checkSite,
    depGetModel,
    forbidExtraQueryParams,
)
from SiteRMLibs.CustomExceptions import ModelNotFound, WrongInputError
from SiteRMLibs.DefaultParams import (
    DELTA_ACCEPT_TIMEOUT,
    DELTA_COMMIT_TIMEOUT,
    IDEMPOTENCY_STALE_TIMEOUT,
    LIMIT_DEFAULT,
    LIMIT_MAX,
    LIMIT_MIN,
)
from SiteRMLibs.MainUtilities import (
    convertTSToDatetime,
    evaldict,
    getFileContentAsJson,
    getModTime,
    getstartupconfig,
    getUTCnow,
    httpdate,
    jsondumps,
    removeFile,
    saveContent,
)
from sqlalchemy.exc import IntegrityError

router = APIRouter()

startupConfig = getstartupconfig()

_SENSE_REQUEST_HEADERS = [
    "sense-request-email",
    "sense-request-fullname",
    "sense-request-host",
    "sense-request-organization",
]


def _extract_sense_headers(request):
    """Extract SENSE caller identity headers from the HTTP request."""
    return {hdr: request.headers.get(hdr, "") for hdr in _SENSE_REQUEST_HEADERS}


def _record_delta_action(dbI, username, delta_id, action, sense_headers):
    """Write a delta user-tracking record to deltasusertracking."""
    dbI.insert(
        "deltasusertracking",
        [
            {
                "username": username,
                "insertdate": getUTCnow(),
                "deltaid": delta_id,
                "useraction": action,
                "otherinfo": jsondumps(sense_headers),
            }
        ],
    )


def _parse_delta_tracking_record(record):
    """Return a delta user-tracking record with parsed request metadata."""
    current = dict(record)
    try:
        current["otherinfo"] = evaldict(current.get("otherinfo", {}))
    except WrongInputError:
        current["otherinfo"] = {}
    return current


def _get_delta_request_info(dbI, delta_id, limit=LIMIT_DEFAULT):
    """Get requestor and tracking information for a delta."""
    tracking = [
        _parse_delta_tracking_record(record)
        for record in dbI.get(
            "deltasusertracking",
            search=[["deltaid", delta_id]],
            orderby=["insertdate", "ASC"],
            limit=limit,
        )
    ]
    submit_record = next((record for record in tracking if record.get("useraction") == "submit"), None)
    request_record = submit_record or (tracking[0] if tracking else {})
    request_headers = request_record.get("otherinfo", {}) if request_record else {}
    request_info = {
        "username": request_record.get("username", ""),
        "insertdate": request_record.get("insertdate", ""),
        "useraction": request_record.get("useraction", ""),
        "email": request_headers.get("sense-request-email", ""),
        "fullname": request_headers.get("sense-request-fullname", ""),
        "host": request_headers.get("sense-request-host", ""),
        "organization": request_headers.get("sense-request-organization", ""),
        "otherinfo": request_headers,
    }
    return {"requestInfo": request_info, "userTracking": tracking}


def _deltasearch(**kwargs):
    """Build delta search filters from deltaID and updatedate."""
    search = []
    if kwargs.get("deltaID"):
        search.append(["uid", kwargs.get("deltaID")])
    if kwargs.get("updatedate"):
        search.append(["updatedate", ">", kwargs.get("updatedate")])
    return search


def _getdeltas(dbI, **kwargs):
    """Get delta from database."""
    # Order by autoincrement id (not insertdate) so limit/offset pages are stable when insertdates tie.
    out = dbI.get(
        "deltas",
        search=_deltasearch(**kwargs),
        limit=kwargs.get("limit", LIMIT_DEFAULT),
        offset=kwargs.get("offset", 0),
        orderby=["id", "DESC"],
    )
    if out and kwargs.get("deltaID"):
        return out[0]
    return out


_IDEMPOTENT_REPLAYED = {"Idempotent-Replayed": "true"}


def _parseIdempotencyKey(rawKey):
    """Return the Idempotency-Key header value without sf-string quotes, or None if not sent."""
    if rawKey is None:
        return None
    key = rawKey.strip()
    if len(key) >= 2 and key[0] == key[-1] == '"':
        key = key[1:-1]
    if not 1 <= len(key) <= 255 or not (key.isascii() and key.isprintable()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Idempotency-Key header. Expected 1-255 printable ASCII characters.",
        )
    return key


def _deltaFingerprint(item):
    """Return a SHA-256 fingerprint of the submitted delta payload."""
    return hashlib.sha256(jsondumps(item.dict()).encode("utf-8")).hexdigest()


def _deltaPaths(deps, sitename, deltaID):
    """Return the PolicyService (httpnew, httpfinished) file paths for a delta."""
    policyDir = os.path.join(deps["config"].get(sitename, "privatedir"), "PolicyService")
    return os.path.join(policyDir, "httpnew", f"{deltaID}.json"), os.path.join(policyDir, "httpfinished", f"{deltaID}.json")


def _getAcceptOutput(dbI, deltaID, since, paths):
    """Return PolicyService accept output for a delta submitted at or after since, or None while still pending."""
    newName, finishedName = paths
    try:
        out = getFileContentAsJson(finishedName)
    except OSError:
        # Another request waiting on the same delta removed the file between the existence check and the read.
        out = {}
    if out:
        with suppress(FileNotFoundError):
            removeFile(finishedName)
        return out
    if os.path.isfile(newName):
        # Not picked up by PolicyService yet, so any deltas row is from an earlier submission.
        return None
    # PolicyService also records the result in the deltas table; use it when the result file was already consumed.
    rows = dbI.get("deltas", search=[["uid", deltaID], ["insertdate", ">=", since]], orderby=["id", "DESC"], limit=1)
    if not rows:
        return None
    row = rows[0]
    out = {
        "ID": row["uid"],
        "insertdate": row["insertdate"],
        "updatedate": row["insertdate"],
        "content": evaldict(row["content"]),
        "State": "failed" if row["state"] == "failed" else "accepted",
        "modelId": row["modelid"],
    }
    if row.get("error"):
        out["Error"] = evaldict(row["error"])
    return out


def _acceptResult(request, sitename, out):
    """Return the delta POST (status code, body) for PolicyService accept output."""
    body = {key: out.get(key) for key in ("ID", "insertdate", "updatedate", "content", "State", "modelId")}
    body["id"] = out["ID"]
    body["lastModified"] = convertTSToDatetime(out["updatedate"])
    body["href"] = f"{request.base_url}api/{sitename}/deltas/{out['ID']}"
    if body["State"] == "accepted":
        return status.HTTP_201_CREATED, body
    error = out.get("Error", f"Unknown Error. Error Message: None. Full dump: {jsondumps(out)}")
    return status.HTTP_400_BAD_REQUEST, {"detail": f"Failed to accept delta. Error Message: {error}."}


def _respond(request, statusCode, body, headers=None):
    """Return the delta POST response, raising HTTPException for an error result."""
    if statusCode >= 400:
        raise HTTPException(status_code=statusCode, detail=body["detail"], headers=headers)
    return APIResponse.genResponse(request, body, status_code=statusCode, headers=headers)


def _getIdempotencyRecord(dbI, username, idemKey):
    """Get the delta POST Idempotency-Key record of a user."""
    rows = dbI.get("deltaidempotency", search=[["username", username], ["idemkey", idemKey]], limit=1)
    return rows[0] if rows else None


def _claimIdempotencyKey(dbI, username, idemKey, fingerprint, deltaID):
    """Insert an in-progress record for the key; return its id, or None if another request already holds the key."""
    now = getUTCnow()
    record = {"username": username, "idemkey": idemKey, "fingerprint": fingerprint, "deltaid": deltaID, "insertdate": now, "updatedate": now}
    try:
        _, _, recordID = dbI.insert("deltaidempotency", [record])
    except IntegrityError:
        return None
    return recordID


def _storeIdempotentResult(dbI, recordID, statusCode, body):
    """Save the final delta POST response of an Idempotency-Key record."""
    dbI.update("deltaidempotency", [{"id": recordID, "statuscode": statusCode, "response": jsondumps(body), "updatedate": getUTCnow()}])


async def _awaitIdempotentResult(request, deps, sitename, idemKey, fingerprint):
    """Return the response of the request holding idemKey, waiting while it is in progress; None if no request holds it."""
    dbI, username = deps["dbI"], deps["user"]["user_info"]["sub"]
    for _ in range(DELTA_ACCEPT_TIMEOUT):
        record = _getIdempotencyRecord(dbI, username, idemKey)
        if not record:
            return None
        if record["fingerprint"] != fingerprint:
            raise HTTPException(
                status_code=422,
                detail="Idempotency-Key was already used for a different delta request. Use a new key for a new request.",
            )
        if record["statuscode"] is not None:
            return _respond(request, record["statuscode"], evaldict(record["response"]), _IDEMPOTENT_REPLAYED)
        newName, finishedName = _deltaPaths(deps, sitename, record["deltaid"])
        if out := _getAcceptOutput(dbI, record["deltaid"], record["insertdate"], (newName, finishedName)):
            statusCode, body = _acceptResult(request, sitename, out)
            _storeIdempotentResult(dbI, record["id"], statusCode, body)
            return _respond(request, statusCode, body, _IDEMPOTENT_REPLAYED)
        if getUTCnow() - record["insertdate"] > IDEMPOTENCY_STALE_TIMEOUT and not os.path.isfile(newName):
            # Original submission was lost before PolicyService produced a result; let this request resubmit it.
            dbI.delete("deltaidempotency", [["id", record["id"]]])
            return None
        await sleep(1)
    raise _idempotencyInProgress()


def _idempotencyInProgress():
    """Return the 409 error for an Idempotency-Key whose original request is still in progress."""
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="A delta request with this Idempotency-Key is still being processed. Retry later with the same key.",
        headers={"Retry-After": "10"},
    )


async def _submitToPolicyService(request, deps, sitename, item):
    """Queue the delta for PolicyService and wait for its accept output; None on timeout."""
    outContent = {
        "ID": item.id,
        "insertdate": getUTCnow(),
        "updatedate": getUTCnow(),
        "content": item.dict(),
        "State": "accepting",
        "modelId": item.modelId,
    }
    # Save item to disk; drop any result left behind by an earlier submission of this delta that timed out.
    fname, finishedName = _deltaPaths(deps, sitename, item.id)
    with suppress(FileNotFoundError):
        removeFile(finishedName)
    saveContent(fname, outContent)
    _record_delta_action(deps["dbI"], deps["user"]["user_info"]["sub"], item.id, "submit", _extract_sense_headers(request))
    # Wait (without blocking the event loop) for PolicyService to accept or reject the delta.
    for _ in range(DELTA_ACCEPT_TIMEOUT):
        if out := _getAcceptOutput(deps["dbI"], item.id, outContent["insertdate"], (fname, finishedName)):
            return out
        await sleep(1)
    return None


class DeltaItem(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    modelId: Optional[constr(strip_whitespace=True, min_length=1, max_length=255)] = None
    id: constr(strip_whitespace=True, min_length=1, max_length=255)
    # Optional fields
    reduction: Optional[constr(strip_whitespace=True, min_length=1)] = None
    addition: Optional[constr(strip_whitespace=True, min_length=1)] = None


class DeltaTimeState(BaseModel):
    """Service Item Model."""

    # pylint: disable=too-few-public-methods
    uuid: constr(strip_whitespace=True, min_length=1, max_length=255)
    uuidtype: constr(strip_whitespace=True, min_length=1, max_length=64)
    hostname: constr(strip_whitespace=True, min_length=1, max_length=255)
    hostport: constr(strip_whitespace=True, min_length=1, max_length=64)
    uuidstate: constr(strip_whitespace=True, min_length=1, max_length=64)


# =========================================================
# /api/{sitename}/deltas
# =========================================================
@router.get(
    "/{sitename}/deltas",
    summary="Get Delta information",
    description=("Retrieves deltas from the specified site, newest first. Use limit and offset to page through results; the X-Total-Count response header holds the total number of matching deltas."),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Deltas retrieved successfully",
                "headers": {"X-Total-Count": {"description": "Total number of deltas matching the request (ignoring limit and offset).", "schema": {"type": "integer"}}},
                "content": {
                    "application/json": {
                        "example": [
                            {
                                "id": "b1c68762-986d-4767-a796-fdd5f59b7ef0",
                                "lastModified": 1753744800,
                                "state": "activated",
                                "href": "http://sense-dev-sdsc.nrp-nautilus.io/api/T2_US_SDSC_DEV/deltas/b1c68762-986d-4767-a796-fdd5f59b7ef0",
                                "modelId": "f7a1b548-6c08-11f0-bfcf-00000005c83b",
                            },
                            {
                                "id": "c814a8aa-a628-4335-a03e-9264228897e9",
                                "lastModified": 1753744589,
                                "state": "activated",
                                "href": "http://sense-dev-sdsc.nrp-nautilus.io/api/T2_US_SDSC_DEV/deltas/c814a8aa-a628-4335-a03e-9264228897e9",
                                "modelId": "385a0ead-6c08-11f0-b4ef-00000004e9ab",
                            },
                        ]
                    }
                },
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - No deltas found in the system.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "no_deltas": {"detail": "No deltas found in the system."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltas(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the service deltas for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    summary: StrictBool = Query(
        True,
        description="Whether to return a summary of the deltas. Defaults to False.",
    ),
    limit: int = Query(
        LIMIT_DEFAULT,
        description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    offset: int = Query(
        0,
        description="The number of deltas to skip before returning results. Defaults to 0.",
        ge=0,
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit", "summary", "offset")),
):
    """
    Get service deltas from the specified site.
    """
    checkSite(deps, sitename)
    retvals = []
    modTime = getModTime(request.headers)
    deltas = _getdeltas(deps["dbI"], limit=limit, offset=offset, updatedate=modTime)
    if not deltas:
        # return 404 Not Found if no deltas are found
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No deltas found in the system.",
        )
    # We get it here, but would be more valuable to do this in sql query.
    for delta in deltas:
        current = {
            "id": delta["uid"],
            "lastModified": delta["updatedate"],
            "state": delta["state"],
            "href": f"{request.base_url}api/{sitename}/deltas/{delta['uid']}",
            "modelId": delta["modelid"],
        }
        if not summary:
            content = evaldict(delta.get("content", {}))
            current["addition"] = content.get("addition")
            current["reduction"] = content.get("reduction")
        retvals.append(current)
    total = deps["dbI"].count("deltas", search=_deltasearch(updatedate=modTime))
    return APIResponse.genResponse(request, retvals, headers={"X-Total-Count": str(total)})


@router.post(
    "/{sitename}/deltas",
    summary="Submit Delta",
    description=(
        "Submits a new delta for the specified site.\n\n"
        "Send an `Idempotency-Key` header (1-255 characters, unique per request) to retry safely after a timeout or a lost response. "
        "A retry with the same key and payload never submits the delta again: it returns the original result (with `Idempotent-Replayed: true`), "
        "waits for the original request if it is still in progress, or returns 409 if it is still in progress after the wait. "
        "Reusing a key with a different payload returns 422. Keys are scoped per user and kept for 7 days."
    ),
    tags=["Deltas"],
    responses={
        **{
            201: {
                "description": "Delta submitted successfully",
                "content": {"application/json": {"example": {"delta": "example_delta"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Model not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "model_not_found": {"detail": "Model not found in the database. First time run?"},
                        }
                    }
                },
            },
            400: {
                "description": "Bad Request. Possible Reasons:\n - You did POST method, but nor reduction, nor addition is present.\n - Failed to accept delta.\n - Invalid Idempotency-Key header.",
                "content": {
                    "application/json": {
                        "example": {
                            "delta_missing": {"detail": "You did POST method, but nor reduction, nor addition is present."},
                            "delta_failed": {"detail": "Failed to accept delta. Error Message: <error_message>. Full dump: <full_dump>"},
                            "invalid_key": {"detail": "Invalid Idempotency-Key header. Expected 1-255 printable ASCII characters."},
                        }
                    }
                },
            },
            409: {
                "description": "Conflict. A request with the same Idempotency-Key is still being processed. Retry later with the same key (see Retry-After header).",
                "content": {"application/json": {"example": {"detail": "A delta request with this Idempotency-Key is still being processed. Retry later with the same key."}}},
            },
            422: {
                "description": "Unprocessable Content. The Idempotency-Key was already used with a different payload.",
                "content": {"application/json": {"example": {"detail": "Idempotency-Key was already used for a different delta request. Use a new key for a new request."}}},
            },
            504: {
                "description": "Gateway Timeout. Possible Reasons:\n - Failed to accept delta. Timeout reached and output to accept delta is empty. With an Idempotency-Key, retry with the same key to get the result.",
                "content": {"application/json": {"example": {"timeout": {"detail": "Failed to accept delta. Timeout reached and output to accept delta is empty. Please report to site admins."}}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def submitDelta(
    request: Request,
    item: DeltaItem,
    sitename: str = Path(
        ...,
        description="The site name to submit the delta for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    idempotencyKey: Optional[str] = Header(
        None,
        alias="Idempotency-Key",
        description="Optional unique key to make retries of this request safe. Retries with the same key and payload return the original result instead of submitting the delta again.",
    ),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Submit a new delta for the specified site.
    """
    checkSite(deps, sitename)
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(deps):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API is not in a ready state to accept requests. Server restart? Failing service?. Retry later.",
        )
    # If both addition and reduction are empty, raise a Error
    if not item.reduction and not item.addition:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You did POST method, but nor reduction, nor addition is present",
        )
    idemKey = _parseIdempotencyKey(idempotencyKey)
    # Fingerprint before modelId is defaulted below, so a retry of the same payload matches.
    fingerprint = _deltaFingerprint(item)
    # A retry must replay (or wait for) the original result before anything below touches the delta.
    if idemKey and (replay := await _awaitIdempotentResult(request, deps, sitename, idemKey, fingerprint)):
        return replay
    if delta := _getdeltas(deps["dbI"], deltaID=item.id):
        # If delta is not in a final state, we delete it from db, and will add new one.
        if delta["state"] not in [
            "activated",
            "failed",
            "removed",
            "accepted",
            "accepting",
        ]:
            deps["dbI"].delete("deltas", [["uid", delta["uid"]]])
    try:
        # Get latest model, and check if modelId is same as latest
        # If not, raise an Error, as model was updated, and things have changed.
        latestModel = depGetModel(deps["dbI"], limit=1, orderby=["insertdate", "DESC"])[0]
        item.modelId = latestModel["uid"] if not item.modelId else item.modelId  # Set it to the latest, if not provided.
        if latestModel["uid"] != item.modelId:
            # Model ID does not match latest model, and latest model is the one with all committed changes. We will bypass the request and use the latest model ID.
            print(f"WARNING! Bypassing requested modelID {item.modelId}. Using latest model for comparison: {latestModel['uid']}")
    except ModelNotFound as ex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Model not found in the database. First time run?",
        ) from ex
    recordID = None
    if idemKey:
        recordID = _claimIdempotencyKey(deps["dbI"], deps["user"]["user_info"]["sub"], idemKey, fingerprint, item.id)
        if recordID is None:
            # A concurrent request with the same key claimed it first; wait for its result instead of submitting twice.
            if replay := await _awaitIdempotentResult(request, deps, sitename, idemKey, fingerprint):
                return replay
            raise _idempotencyInProgress()
    if not (out := await _submitToPolicyService(request, deps, sitename, item)):
        # An Idempotency-Key record stays in progress, so a retry with the same key picks up the result instead of resubmitting.
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Failed to accept delta. Timeout reached and output to accept delta is empty." + (" Retry with the same Idempotency-Key to get the result." if idemKey else ""),
        )
    result = _acceptResult(request, sitename, out)
    if recordID is not None:
        _storeIdempotentResult(deps["dbI"], recordID, *result)
    return _respond(request, *result)


# =========================================================
# /api/{sitename}/deltas/{delta_id}
# =========================================================
@router.get(
    "/{sitename}/deltas/{delta_id}",
    summary="Get Delta by ID",
    description=("Retrieves delta information by its ID for the given site name."),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Delta information retrieved successfully",
                "content": {"application/json": {"example": {"delta": "example_delta"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
            304: {
                "description": "Delta not modified",
                "content": {"application/json": {"example": {"detail": "Delta not modified. See Last-Modified header for the last modification date."}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltaByID(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the delta information for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to retrieve."),
    summary: StrictBool = Query(
        False,
        description="Whether to return a summary of the deltas. Defaults to False.",
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("summary")),
):
    """
    Get delta information by its ID for the given site name.
    """
    checkSite(deps, sitename)
    modTime = getModTime(request.headers)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database. First time run?",
        )
    # Check if the delta is modified since last request
    if delta["updatedate"] < modTime:
        return Response(
            status_code=status.HTTP_304_NOT_MODIFIED,
            headers={"Last-Modified": httpdate(delta["updatedate"])},
        )
    # Return 200 OK with delta content
    headers = {"Last-Modified": httpdate(delta["updatedate"])}
    delta["insertdate"] = convertTSToDatetime(delta["insertdate"])
    delta["updatedate"] = convertTSToDatetime(delta["updatedate"])
    delta["lastModified"] = delta["updatedate"]
    if not summary:
        content = evaldict(delta.get("content", {}))
        delta["addition"] = content.get("addition", {})
        delta["reduction"] = content.get("reduction", {})
    else:
        del delta["content"]
    delta.update(_get_delta_request_info(deps["dbI"], delta_id))
    return APIResponse.genResponse(request, [delta], headers=headers)


# =========================================================
# /api/{sitename}/deltas/{delta_id}/requestinfo
# =========================================================
@router.get(
    "/{sitename}/deltas/{delta_id}/requestinfo",
    summary="Get Delta Request Information",
    description=("Retrieves the requester and user-tracking information recorded for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Delta request information retrieved successfully",
                "content": {
                    "application/json": {
                        "example": {
                            "requestInfo": {
                                "username": "senseoprod",
                                "insertdate": 1775310535,
                                "useraction": "submit",
                                "email": "tlehman@es.net",
                                "fullname": "Thomas Lehman",
                                "host": "https://sense-o.es.net:8443",
                                "organization": "",
                                "otherinfo": {
                                    "sense-request-email": "tlehman@es.net",
                                    "sense-request-fullname": "Thomas Lehman",
                                    "sense-request-host": "https://sense-o.es.net:8443",
                                    "sense-request-organization": "",
                                },
                            },
                            "userTracking": [],
                        }
                    }
                },
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getDeltaRequestInfo(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the delta request information for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to retrieve request information for."),
    limit: int = Query(
        LIMIT_DEFAULT,
        description=f"The maximum number of tracking records to return. Defaults to {LIMIT_DEFAULT}.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit")),
):
    """
    Get requestor and user-tracking information for the specified delta ID.
    """
    checkSite(deps, sitename)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database.",
        )
    return APIResponse.genResponse(request, _get_delta_request_info(deps["dbI"], delta_id, limit=limit))


# =========================================================
# /api/{sitename}/deltas/{delta_id}/actions/{action}
# =========================================================


@router.put(
    "/{sitename}/deltas/{delta_id}/actions/{action}",
    summary="Perform Action on Delta",
    description=(
        "Performs a specified action on a delta by its ID for the given site name. Actions information:\n"
        f" - commit: Commit delta. Only commits if delta state is in accepted state. ({DELTA_COMMIT_TIMEOUT // 60} minutes timeout to received commit call)\n"
        f" - remove: Remove delta. Only removes if delta state is in accepted. (Way to bypass the {DELTA_COMMIT_TIMEOUT // 60} minutes timeout)\n"
        " - forcecommit: Force commit delta. Only commits if delta state is in one of: accepted, activated, failed state. (No timeout for forcecommit - use with caution due to overlaps!)\n"
        " - forceapply: Force apply delta on the system. (No timeout for forceapply - use with caution due to overlaps!)"
    ),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Action performed successfully",
                "content": {"application/json": {"example": {"result": "Action completed successfully"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
            400: {
                "description": "Bad Request",
                "content": {"application/json": {"example": {"detail": "Delta state 'X' is not valid for action 'Y'. Only 'Z' state is allowed."}}},
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def performActionOnDelta(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to perform the action on the delta for.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to perform the action on."),
    action: Literal["commit", "forcecommit", "forceapply"] = Path(..., description="The action to perform on the delta."),
    deps=Depends(apiWriteDeps),
    _forbid=Depends(forbidExtraQueryParams()),
):
    """
    Perform a specified action on a delta by its ID for the given site name.
    """
    checkSite(deps, sitename)
    # actions are commit, forceapply
    # Check if checkignore is set, if so, check if first run is finished
    if not checkReadyState(deps):
        # If first run is not finished, raise an exception
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API is not in a ready state to accept requests. Server restart? Failing service?. Retry later.",
        )
    # Check if delta state is valid for commit action;
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database.",
        )
    if delta["state"] != "accepted" and action == "commit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Delta state '{delta['state']}' is not valid for commit action. Only 'accepted' state is allowed. Current state: {delta['state']}",
        )
    if delta["state"] not in ["activated", "failed", "accepted"] and action == "forcecommit":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Delta state '{delta['state']}' is not valid for forcecommit action. Only 'activated' or 'failed' states are allowed. Current state: {delta['state']}",
        )
    if action in ["commit", "forcecommit"]:
        # Commit or force commit the delta
        deps["stateMachine"].stateChangerDelta(deps["dbI"], "committed", **delta)
        deps["stateMachine"].modelstatechanger(deps["dbI"], "add", **delta)
        _record_delta_action(deps["dbI"], deps["user"]["user_info"]["sub"], delta_id, action, _extract_sense_headers(request))
        return APIResponse.genResponse(request, {"result": "Action completed successfully"})
    if action == "forceapply":
        # Force apply the delta
        deps["dbI"].insert("forceapplyuuid", [{"uuid": delta_id}])
        return APIResponse.genResponse(request, {"result": "Force apply action completed successfully"})
    if delta["state"] in ["accepted"] and action == "remove":
        # Remove delta from the database
        deps["dbI"].delete("deltas", [["uid", delta_id]])
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Invalid action '{action}' specified. Valid actions are 'commit', 'forcecommit', 'forceapply'.",
    )


# =========================================================
# /api/{sitename}/deltas/{delta_id}/timestates
# =========================================================
@router.get(
    "/{sitename}/deltas/{delta_id}/timestates",
    summary="Get Time States for Delta",
    description=("Retrieves time states for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            200: {
                "description": "Time states retrieved successfully",
                "content": {"application/json": {"example": {"time_states": "example_time_states"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                            "delta_no_timestates": {"detail": "No time states found for the specified delta ID."},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def getTimeStatesForDelta(
    request: Request,
    sitename: str = Path(
        ...,
        description="The site name to retrieve the time states for the delta.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to retrieve the time states for."),
    limit: int = Query(
        LIMIT_DEFAULT,
        description=f"The maximum number of results to return. Defaults to {LIMIT_DEFAULT}.",
        ge=LIMIT_MIN,
        le=LIMIT_MAX,
    ),
    deps=Depends(apiReadDeps),
    _forbid=Depends(forbidExtraQueryParams("limit")),
):
    """
    Get time states for the specified delta ID.
    """
    checkSite(deps, sitename)
    delta = _getdeltas(deps["dbI"], deltaID=delta_id)
    if not delta:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Delta not found in the database.",
        )

    # Retrieve time states from the database
    timestates = deps["dbI"].get(
        "states",
        search=[["deltaid", delta_id]],
        orderby=["insertdate", "DESC"],
        limit=limit,
    )
    if not timestates:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No time states found for the specified delta ID.",
        )
    return APIResponse.genResponse(request, timestates)


@router.post(
    "/{sitename}/deltas/{delta_id}/timestates",
    summary="Create Time State for Delta",
    description=("Creates a new time state for the specified delta ID."),
    tags=["Deltas"],
    responses={
        **{
            201: {
                "description": "Time state created successfully",
                "content": {"application/json": {"example": {"time_state": "example_time_state"}}},
            },
            404: {
                "description": "Not Found. Possible Reasons:\n - No sites configured in the system.\n - Delta not found in the database.",
                "content": {
                    "application/json": {
                        "example": {
                            "no_sites": {"detail": "Site <sitename> is not configured in the system. Please check the request and configuration."},
                            "delta_not_found": {"detail": "Delta not found in the database. First time run?"},
                        }
                    }
                },
            },
        },
        **DEFAULT_RESPONSES,
    },
)
async def createTimeStateForDelta(
    request: Request,
    item: DeltaTimeState,
    sitename: str = Path(
        ...,
        description="The site name to create the time state for the delta.",
        examples=[startupConfig.get("SITENAME", "default")],
    ),
    delta_id: str = Path(..., description="The ID of the delta to create the time state for."),
    deps=Depends(apiWriteDeps),
):
    """
    Create a new time state for the specified delta ID.
    """
    checkSite(deps, sitename)
    # Check if the delta is in a state that allows creating a time state
    deps["dbI"].insert(
        "deltatimestates",
        [
            {
                "insertdate": getUTCnow(),
                "uuid": item.uuid,
                "uuidtype": item.uuidtype,
                "hostname": item.hostname,
                "hostport": item.hostport,
                "uuidstate": item.uuidstate,
            }
        ],
    )
    return APIResponse.genResponse(
        request,
        [
            {
                "status": "Time state created successfully",
                "delta_id": delta_id,
                "time_state": item.dict(),
            }
        ],
        status_code=status.HTTP_201_CREATED,
    )
