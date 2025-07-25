#!/usr/bin/env python3
"""FastAPI application for SiteFE REST API."""
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from SiteFE.REST.Topo import router as topo_router
from SiteFE.REST.Frontend import router as fe_router
from SiteFE.REST.Delta import router as delta_router
from SiteFE.REST.Host import router as host_router
from SiteFE.REST.Prometheus import router as prometheus_router
from SiteFE.REST.Debug import router as debug_router
from SiteFE.REST.Model import router as model_router
from SiteFE.REST.Service import router as service_router

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

for route in app.routes:
    print(f"{route.path} - {route.name}")