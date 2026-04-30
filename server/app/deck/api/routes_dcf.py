"""
FastAPI routes for deterministic DCF valuation.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, ValidationError, field_validator

from app.core.middleware import request_id_var
from app.deck.services.dcf_calculator import calculate_dcf
from app.deck.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/valuation", tags=["valuation"])


class DCFAssumptionsSchema(BaseModel):
    """User-editable DCF assumptions."""

    forecastYears: int = Field(default=5, ge=5, le=10)
    fcfGrowthRate: float = Field(default=0.08, ge=-0.5, le=1.0)
    terminalGrowthRate: float = Field(default=0.025, ge=0, le=0.05)
    wacc: float = Field(default=0.09, gt=0, le=0.3)


class DCFOverridesSchema(BaseModel):
    """Manual overrides for DCF inputs."""

    sharesOutstanding: Optional[float] = None
    cash: Optional[float] = None
    debt: Optional[float] = None
    fcf0: Optional[float] = None
    marketPrice: Optional[float] = None


class DCFRequest(BaseModel):
    """Request schema for POST /api/v1/valuation/dcf."""

    ticker: str = Field(..., min_length=1, max_length=10)
    assumptions: Optional[DCFAssumptionsSchema] = None
    overrides: Optional[DCFOverridesSchema] = None

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, value: str) -> str:
        if isinstance(value, str):
            return value.upper().strip()
        return value


def _request_id(request: Request) -> str | None:
    return request.headers.get("x-request-id") or request_id_var.get(None)


async def _parse_dcf_request(request: Request) -> DCFRequest:
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Content-Type must be application/json",
                "request_id": _request_id(request),
            },
        )
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Content-Type must be application/json",
                "request_id": _request_id(request),
            },
        )
    try:
        return DCFRequest(**data)
    except ValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": f"Invalid request: {exc}", "request_id": _request_id(request)},
        )


@router.post("/dcf")
async def calculate_dcf_valuation(request: Request):
    """Calculate DCF target price."""
    dcf_request = await _parse_dcf_request(request)
    assumptions_dict = (
        dcf_request.assumptions.model_dump()
        if dcf_request.assumptions
        else None
    )
    overrides_dict = (
        dcf_request.overrides.model_dump()
        if dcf_request.overrides
        else None
    )

    logger.info("Calculating DCF for %s", dcf_request.ticker)
    result = await asyncio.to_thread(
        calculate_dcf,
        ticker=dcf_request.ticker,
        assumptions=assumptions_dict,
        overrides=overrides_dict,
    )

    if result.get("error"):
        logger.warning("DCF calculation error: %s", result["error"])
    else:
        valuation = result.get("valuation", {})
        logger.info(
            "DCF result for %s: target=$%s, market=$%s, upside=%.1f%%",
            dcf_request.ticker,
            valuation.get("targetPrice"),
            valuation.get("marketPrice"),
            valuation.get("upsidePct", 0) * 100,
        )

    return result


@router.get("/dcf/inputs/{ticker}")
async def get_dcf_inputs(ticker: str):
    """Get DCF inputs for a ticker without calculating valuation."""
    from app.deck.services.dcf_data_provider import get_dcf_data_provider

    normalized_ticker = ticker.upper().strip()
    provider = get_dcf_data_provider()
    inputs, sources, warnings = await asyncio.to_thread(provider.get_inputs, normalized_ticker)

    return {
        "ticker": normalized_ticker,
        "inputs": inputs.to_dict(),
        "sources": sources.to_dict(),
        "warnings": warnings,
    }


@router.get("/dcf/health")
async def dcf_health():
    """Health check endpoint for DCF service."""
    return {"status": "ok", "service": "dcf-calculator", "version": "1.0.0"}
