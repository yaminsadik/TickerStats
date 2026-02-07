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
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.wsgi import WSGIMiddleware

from app.api.routes import router
from app.api.routes_user import router as user_router, admin_router
from app.core.config import API_VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

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

# Add CORS middleware for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include FastAPI routers
app.include_router(router)
app.include_router(user_router)  # User-specific routes (protected)
app.include_router(admin_router)  # Admin-only routes

# Mount Flask (deck generation + legacy relative API) under root
# Flask handles /api/v1/deck/*, /api/v1/valuation/*, /api/v1/sections, /health
# FastAPI routes are matched first; anything unmatched falls through to Flask.
app.mount("/", WSGIMiddleware(_get_flask_app()))

logger.info(f"TickerStats API v{API_VERSION} initialized (FastAPI + Flask via WSGIMiddleware)")
