"""
API routes for the TickerStats relative table backend.
"""

import asyncio
import csv
import io
import logging
from typing import Optional

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_with_upsert, require_paid_or_admin
from app.core.database import get_db
from app.models import User
from app.services.usage_limits import (
    compute_compare_hash,
    check_compare_limit_async,
    enforce_compare_limit_and_increment_async,
)
from app.core.config import (
    DEFAULT_SNAPSHOT_FIELDS,
    MAX_SYMBOLS_PER_REQUEST,
    PERF_METRICS_ALLOWLIST,
    SNAPSHOT_FIELDS_ALLOWLIST,
    VALID_PERF_PERIODS,
    UNITS_METADATA,
)
from app.schemas import (
    ErrorResponse,
    HealthResponse,
    PerfRequest,
    RelativeTableResponse,
    RequestedParams,
    RowData,
)
from app.services.yfinance_service import yfinance_service

logger = logging.getLogger(__name__)

router = APIRouter()


def parse_and_validate_symbols(symbols_str: str) -> list[str]:
    """Parse, validate, and de-duplicate symbols."""
    if not symbols_str or not symbols_str.strip():
        raise HTTPException(status_code=400, detail="symbols parameter is required")

    # Split, strip, uppercase, and filter empty
    raw_symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

    if not raw_symbols:
        raise HTTPException(status_code=400, detail="At least one symbol is required")

    # De-duplicate while preserving order
    seen = set()
    symbols = []
    for s in raw_symbols:
        if s not in seen:
            seen.add(s)
            symbols.append(s)

    if len(symbols) > MAX_SYMBOLS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols allowed per request",
        )

    return symbols


def parse_and_validate_fields(fields_str: Optional[str]) -> list[str]:
    """Parse and validate snapshot fields."""
    if not fields_str or not fields_str.strip():
        return DEFAULT_SNAPSHOT_FIELDS.copy()

    fields = [f.strip() for f in fields_str.split(",") if f.strip()]

    invalid_fields = [f for f in fields if f not in SNAPSHOT_FIELDS_ALLOWLIST]
    if invalid_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid fields: {', '.join(invalid_fields)}. Allowed: {', '.join(SNAPSHOT_FIELDS_ALLOWLIST.keys())}",
        )

    return fields


def parse_and_validate_perf(
    perf_str: Optional[str], perf_period: Optional[str]
) -> tuple[Optional[list[str]], Optional[str]]:
    """Parse and validate performance metrics and period."""
    if not perf_str or not perf_str.strip():
        return None, None

    # Performance is requested, period is required
    if not perf_period or not perf_period.strip():
        raise HTTPException(
            status_code=400,
            detail=f"perfPeriod is required when perf is specified. Valid periods: {', '.join(VALID_PERF_PERIODS)}",
        )

    perf_period = perf_period.strip()
    if perf_period not in VALID_PERF_PERIODS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid perfPeriod: {perf_period}. Valid periods: {', '.join(VALID_PERF_PERIODS)}",
        )

    metrics = [m.strip() for m in perf_str.split(",") if m.strip()]
    invalid_metrics = [m for m in metrics if m not in PERF_METRICS_ALLOWLIST]
    if invalid_metrics:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid perf metrics: {', '.join(invalid_metrics)}. Allowed: {', '.join(PERF_METRICS_ALLOWLIST)}",
        )

    return metrics, perf_period


def build_units_metadata(fields: list[str], perf_metrics: Optional[list[str]], include_dcf: bool = False) -> dict[str, str]:
    """Build units metadata for the requested fields and metrics."""
    units = {}
    for field in fields:
        if field in UNITS_METADATA:
            units[field] = UNITS_METADATA[field]
    if perf_metrics:
        for metric in perf_metrics:
            if metric in UNITS_METADATA:
                units[metric] = UNITS_METADATA[metric]
    if include_dcf:
        units["dcfPrice"] = UNITS_METADATA.get("dcfPrice", "currency")
        units["dcfUpside"] = UNITS_METADATA.get("dcfUpside", "decimal")
    return units


@router.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return HealthResponse(status="ok")


@router.get(
    "/api/relative",
    response_model=RelativeTableResponse,
    responses={400: {"model": ErrorResponse}},
    tags=["Relative Table"],
)
async def get_relative_table(
    response: Response,
    symbols: str = Query(..., description="Comma-separated ticker symbols (e.g., AAPL,MSFT,NVDA)"),
    fields: Optional[str] = Query(None, description="Comma-separated snapshot fields to include"),
    perf: Optional[str] = Query(None, description="Comma-separated performance metrics to compute (return,volatility,maxDrawdown)"),
    perfPeriod: Optional[str] = Query(None, description="Performance period (1mo,3mo,6mo,ytd,1y,2y,5y,10y,max)"),
    dcf: bool = Query(False, description="Include DCF valuation (dcfPrice, dcfUpside)"),
    current_user: User = Depends(get_current_user_with_upsert),
    db: AsyncSession = Depends(get_db),
):
    """
    Get relative table data for multiple symbols.
    
    Returns snapshot fundamentals/valuation metrics and optionally performance metrics.
    
    **Snapshot fields**: sharePrice, marketCap, enterpriseValue, forwardPE, priceSales, 
    priceBook, evEbitda, evRevenue, profitMargin, roa, roe, debtEquity, beta
    
    **Performance metrics**: return, volatility, maxDrawdown (requires perfPeriod)
    
    **DCF valuation**: Set dcf=true to include dcfPrice (fair value) and dcfUpside (% upside/downside)
    """
    logger.info(f"Relative table request: symbols={symbols}, fields={fields}, perf={perf}, perfPeriod={perfPeriod}, dcf={dcf}")

    # Parse and validate inputs
    validated_symbols = parse_and_validate_symbols(symbols)
    validated_fields = parse_and_validate_fields(fields)
    validated_perf_metrics, validated_perf_period = parse_and_validate_perf(perf, perfPeriod)

    # Enforce monthly compare limits (free tier) with fairness window
    compare_hash = compute_compare_hash(
        validated_symbols,
        validated_fields,
        validated_perf_metrics,
        validated_perf_period,
        dcf,
    )
    now = datetime.utcnow()
    allowed, should_increment, limit = await check_compare_limit_async(
        current_user,
        now,
        compare_hash,
    )
    if not allowed:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Free tier is limited to {limit} compare actions per month. "
                "Upgrade to Pro for unlimited compares."
            ),
        )

    # Fetch data (run in thread to avoid blocking the async event loop)
    rows_data, cache_hit = await asyncio.to_thread(
        yfinance_service.get_relative,
        symbols=validated_symbols,
        fields=validated_fields,
        perf_metrics=validated_perf_metrics,
        perf_period=validated_perf_period,
        include_dcf=dcf,
    )

    if should_increment:
        # Enforce again under row lock to avoid limit bypass under concurrency.
        allowed_after_fetch, locked_limit = await enforce_compare_limit_and_increment_async(
            db,
            current_user.auth0_user_id,
            now,
            compare_hash,
        )
        if not allowed_after_fetch:
            blocked_limit = locked_limit or limit or 0
            raise HTTPException(
                status_code=403,
                detail=(
                    f"Free tier is limited to {blocked_limit} compare actions per month. "
                    "Upgrade to Pro for unlimited compares."
                ),
            )

    # Set cache header
    response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"

    # Build response
    as_of = yfinance_service.get_as_of_timestamp()

    perf_request = None
    if validated_perf_metrics and validated_perf_period:
        perf_request = PerfRequest(period=validated_perf_period, metrics=validated_perf_metrics)

    requested = RequestedParams(
        symbols=validated_symbols,
        fields=validated_fields,
        perf=perf_request,
        dcf=dcf,
    )

    # Build units metadata
    units = build_units_metadata(validated_fields, validated_perf_metrics, dcf)

    rows = [
        RowData(
            symbol=r["symbol"],
            snapshot=r["snapshot"],
            performance=r["performance"],
            dcf=r.get("dcf"),
            missingFields=r["missingFields"],
            missingPerf=r["missingPerf"],
            error=r["error"],
        )
        for r in rows_data
    ]

    return RelativeTableResponse(asOf=as_of, requested=requested, units=units, rows=rows)


@router.get(
    "/api/relative/export",
    responses={400: {"model": ErrorResponse}},
    tags=["Relative Table"],
)
async def export_relative_table(
    response: Response,
    symbols: str = Query(..., description="Comma-separated ticker symbols"),
    fields: Optional[str] = Query(None, description="Comma-separated snapshot fields to include"),
    perf: Optional[str] = Query(None, description="Comma-separated performance metrics to compute"),
    perfPeriod: Optional[str] = Query(None, description="Performance period"),
    format: str = Query("csv", description="Export format: csv, xlsx, or pdf"),
    current_user: "User" = Depends(require_paid_or_admin),
):
    """
    Export relative table data as CSV, XLSX, or PDF.
    Requires a Pro subscription or admin access.
    
    Columns: symbol + requested snapshot fields + requested perf metrics (if any).
    Null values render as empty cells.
    """
    from app.services.export_service import build_table_rows, generate_csv, generate_xlsx, generate_pdf

    fmt = format.lower()
    if fmt not in ("csv", "xlsx", "pdf"):
        raise HTTPException(status_code=400, detail="Supported formats: csv, xlsx, pdf")

    logger.info(f"Export request (format={fmt}): symbols={symbols}, fields={fields}, perf={perf}, perfPeriod={perfPeriod}")

    # Parse and validate inputs
    validated_symbols = parse_and_validate_symbols(symbols)
    validated_fields = parse_and_validate_fields(fields)
    validated_perf_metrics, validated_perf_period = parse_and_validate_perf(perf, perfPeriod)

    # Fetch data (run in thread to avoid blocking the async event loop)
    rows_data, cache_hit = await asyncio.to_thread(
        yfinance_service.get_relative,
        symbols=validated_symbols,
        fields=validated_fields,
        perf_metrics=validated_perf_metrics,
        perf_period=validated_perf_period,
    )

    as_of = yfinance_service.get_as_of_timestamp()

    # Build normalised table data
    headers, flat_rows = build_table_rows(
        rows_data, validated_fields, validated_perf_metrics, include_dcf=False,
    )

    # Common response headers
    extra_headers = {
        "X-AsOf": as_of,
        "X-Cache": "HIT" if cache_hit else "MISS",
    }

    if fmt == "csv":
        content = generate_csv(headers, flat_rows)
        extra_headers["Content-Disposition"] = "attachment; filename=relative_table.csv"
        return Response(content=content, media_type="text/csv", headers=extra_headers)
    elif fmt == "xlsx":
        content = generate_xlsx(headers, flat_rows)
        extra_headers["Content-Disposition"] = "attachment; filename=relative_table.xlsx"
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers=extra_headers,
        )
    else:  # pdf
        content = generate_pdf(headers, flat_rows)
        extra_headers["Content-Disposition"] = "attachment; filename=relative_table.pdf"
        return Response(content=content, media_type="application/pdf", headers=extra_headers)
