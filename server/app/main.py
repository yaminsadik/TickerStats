"""
FastAPI application entry point for TicketStats API.

Architecture: FastAPI is the primary ASGI server.
The legacy Flask deck-generation service is mounted under /legacy
via Starlette's WSGIMiddleware so that both run on a single port.
All new user-facing endpoints live on FastAPI.  Flask routes remain
available at their original paths (e.g. /api/v1/deck/generate) by
mounting Flask at "/" – requests that don't match any FastAPI route
fall through to Flask.
"""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response
from starlette.middleware.wsgi import WSGIMiddleware

from app.api.routes import router
from app.api.routes_user import router as user_router, admin_router
from app.core.config import API_VERSION
from app.core.middleware import RequestTimingMiddleware
from app.core.error_handlers import register_error_handlers

# Configure structured JSON logging (reuse the deck service's formatter)
from app.deck.utils.logging import configure_logging

configure_logging(level="INFO", json_output=True)

logger = logging.getLogger(__name__)


def _get_flask_app():
    """Lazily import the Flask app to avoid circular imports."""
    from app.deck.app import get_app
    return get_app()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    logger.info(f"Starting TickerStats API v{API_VERSION}")
    yield
    logger.info("Shutting down TickerStats API")


app = FastAPI(
    title="TickerStats API",
    description="A production-lean FastAPI backend that powers a relative table for student investment clubs using yfinance.",
    version=API_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Register standardized error handlers (before middleware, after app creation)
register_error_handlers(app)

# Add request timing middleware (runs outermost, before CORS)
app.add_middleware(RequestTimingMiddleware)

# Add CORS middleware for frontend access
_raw_allowed_origins = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://127.0.0.1:3000",
)
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in _raw_allowed_origins.split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Total-Count", "Link"],
)

# Fallback CORS headers for error responses (ensures ACAO on 500s)
@app.middleware("http")
async def _cors_fallback(request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        response = await call_next(request)

    origin = request.headers.get("origin")
    if origin in ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Headers"] = request.headers.get(
            "access-control-request-headers", "*"
        )
        response.headers["Access-Control-Allow-Methods"] = request.headers.get(
            "access-control-request-method", "*"
        )
    return response

# Include FastAPI routers
app.include_router(router)
app.include_router(user_router)  # User-specific routes (protected)
app.include_router(admin_router)  # Admin-only routes

# Mount Flask (deck generation + legacy relative API) under root
# Flask handles /api/v1/deck/*, /api/v1/valuation/*, /api/v1/sections, /health
# FastAPI routes are matched first; anything unmatched falls through to Flask.
app.mount("/", WSGIMiddleware(_get_flask_app()))

logger.info(f"TickerStats API v{API_VERSION} initialized (FastAPI + Flask via WSGIMiddleware)")
