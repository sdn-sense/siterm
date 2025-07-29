#!/usr/bin/env python3
# pylint: disable=no-name-in-module
"""FastAPI application for SiteFE REST API."""
import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from SiteFE.REST.Debug import router as debug_router
from SiteFE.REST.Delta import router as delta_router
from SiteFE.REST.Frontend import router as fe_router
from SiteFE.REST.Host import router as host_router
from SiteFE.REST.Model import router as model_router
from SiteFE.REST.Monitoring import router as monitoring_router
from SiteFE.REST.Service import router as service_router
from SiteFE.REST.Topo import router as topo_router

app = FastAPI()

app.add_middleware(GZipMiddleware, minimum_size=1000)

app.include_router(fe_router, prefix="/api")
app.include_router(host_router, prefix="/api")
app.include_router(model_router, prefix="/api")
app.include_router(delta_router, prefix="/api")
app.include_router(debug_router, prefix="/api")
app.include_router(topo_router, prefix="/api")
app.include_router(monitoring_router, prefix="/api")
app.include_router(service_router, prefix="/api")

app.mount("/", StaticFiles(directory="/var/www/html", html=True), name="ui")


def logdetails(request: Request, status_code: int, message: str = ""):
    """Helper function to log detailed request information"""
    # Log only if GU_LOG_LEVEL is set to DEBUG
    if os.getenv("GU_LOG_LEVEL", "INFO").upper() != "DEBUG":
        return
    try:
        log_data = {
            "timestamp": request.headers.get("date", ""),
            "status_code": status_code,
            "method": request.method,
            "full_url": str(request.url),
            "path": request.url.path,
            "query_string": str(request.url.query),
            "query_params": dict(request.query_params),
            "path_params": request.path_params,
            "client_info": {"ip": request.client.host, "port": request.client.port},
            "headers": dict(request.headers),
            "message": message,
        }
    except Exception as ex:
        log_data = {
            "request": str(request),
            "error": "Failed to log request details",
            "exception": str(ex),
            "status_code": status_code,
            "method": request.method,
            "full_url": str(request.url),
        }
    print(f"Request Log[{status_code}]:", log_data)


@app.exception_handler(400)
async def custom_400_handler(request: Request, exc: HTTPException):
    """Custom 400 error handler."""
    logdetails(request, 400, str(exc))
    return JSONResponse(status_code=400, content={"detail": f"Bad Request. Exception: {exc}"})


@app.exception_handler(401)
async def custom_401_handler(request: Request, exc: HTTPException):
    """Custom 401 error handler."""
    logdetails(request, 401, str(exc))
    return JSONResponse(status_code=401, content={"detail": f"Unauthorized. Exception: {exc}"})

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    """Custom 404 error handler."""
    logdetails(request, 404, str(exc))
    return JSONResponse(status_code=404, content={"detail": f"Not Found. Exception: {exc}"})


@app.exception_handler(405)
async def custom_405_handler(request: Request, exc: HTTPException):
    """Custom 405 error handler."""
    logdetails(request, 405, str(exc))
    return JSONResponse(status_code=405, content={"detail": f"Method Not Allowed. Exception: {exc}"})


@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: HTTPException):
    """Custom 500 error handler."""
    logdetails(request, 500, str(exc))
    return JSONResponse(status_code=500, content={"detail": f"Internal Server Error. Exception: {exc}"})


@app.exception_handler(501)
async def custom_501_handler(request: Request, exc: HTTPException):
    """Custom 501 error handler."""
    logdetails(request, 501, str(exc))
    return JSONResponse(status_code=501, content={"detail": f"Not Implemented. Exception: {exc}"})


@app.exception_handler(503)
async def custom_503_handler(request: Request, exc: HTTPException):
    """Custom 503 error handler."""
    logdetails(request, 503, str(exc))
    return JSONResponse(status_code=503, content={"detail": f"Service Unavailable. Exception: {exc}"})


@app.exception_handler(504)
async def custom_504_handler(request: Request, exc: HTTPException):
    """Custom 504 error handler."""
    logdetails(request, 504, str(exc))
    return JSONResponse(status_code=504, content={"detail": f"Gateway Timeout. Exception: {exc}"})


for route in app.routes:
    print(f"{route.path} - {route.name}")
