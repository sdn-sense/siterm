#!/usr/bin/env python3
# pylint: disable=no-name-in-module
"""FastAPI application for SiteFE REST API."""
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from SiteFE.REST.Debug import router as debug_router
from SiteFE.REST.Delta import router as delta_router
from SiteFE.REST.Frontend import router as fe_router
from SiteFE.REST.Host import router as host_router
from SiteFE.REST.Model import router as model_router
from SiteFE.REST.Prometheus import router as prometheus_router
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
app.include_router(prometheus_router, prefix="/api")
app.include_router(service_router, prefix="/api")

app.mount("/", StaticFiles(directory="/var/www/html", html=True), name="ui")

def logdetails(request: Request, status_code: int, message: str = ""):
    """Helper function to log detailed request information"""
    log_data = {"timestamp": request.headers.get("date", ""),
                "status_code": status_code,
                "method": request.method,
                "full_url": str(request.url),
                "path": request.url.path,
                "query_string": str(request.url.query),
                "query_params": dict(request.query_params),
                "path_params": request.path_params,
                "client_info": {"ip": request.client.host,
                                "port": request.client.port},
                "headers": dict(request.headers),
                "message": message}
    print(f"Request Log[{status_code}]:", log_data)

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    """Custom 404 error handler."""
    logdetails(request, 404, exc)
    return JSONResponse(status_code=404, content={"detail": "Not Found"})


@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: HTTPException):
    """Custom 500 error handler."""
    logdetails(request, 500, str(exc))
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})

for route in app.routes:
    print(f"{route.path} - {route.name}")
