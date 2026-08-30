"""Epsilon FastAPI application.

Entry point for the Epsilon backend. Wires up routers, middleware, and
lifespan events. The vuln_loader is initialized at startup and shared
across requests via app.state.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

# Routers
from app.api.agent import router as agent_router
from app.api.auth import router as auth_router
from app.api.observability import router as observability_router
from app.api.security import router as security_router
from app.api.vulnerabilities import router as vulns_router
from app.config import get_cors_origins, get_settings
from app.errors import sanitize_error_detail
from app.services.letta_client import LettaClient
from app.services.vuln_loader import VulnLoader

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize services on startup, clean up on shutdown."""
    # Load vulnerability configs from disk
    vuln_loader = VulnLoader()
    vuln_loader.load()
    app.state.vuln_loader = vuln_loader
    logger.info(f"Loaded {len(vuln_loader.get_years())} years of vulnerabilities")

    # Initialize LettaClient singleton
    settings = get_settings()
    letta_client = LettaClient(base_url=settings.LETTA_URL)
    app.state.letta_client = letta_client

    # Register custom tools (execute_code, etc.) with Letta.
    # Letta's DB can be reset independently, so we register on every startup.
    await letta_client.ensure_tools_registered()

    yield

    # Shutdown
    await letta_client.close()
    logger.info("Epsilon backend shutdown complete")


app = FastAPI(
    title="Epsilon API",
    version="0.1.0",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(vulns_router, prefix="/vulns", tags=["vulnerabilities"])
app.include_router(agent_router, prefix="/agent", tags=["agent"])
app.include_router(security_router, prefix="/security", tags=["security"])
app.include_router(observability_router, prefix="/observability", tags=["observability"])


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def catch_all(request: Request, exc: Exception):
    """Catch-all handler — sanitize internal errors, add CORS headers."""
    logger.exception("Unhandled error: %s", exc)
    origin = request.headers.get("origin", "")
    allowed = get_cors_origins()
    headers = {}
    if origin in allowed:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
    return JSONResponse(
        status_code=500,
        content={"detail": sanitize_error_detail(exc)},
        headers=headers,
    )
