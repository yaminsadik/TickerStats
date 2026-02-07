"""
Flask routes for relative table API (ported from FastAPI).
"""

import csv
import io
import logging
from typing import Optional

from flask import Blueprint, jsonify, request, Response

from app.core.config import (
    DEFAULT_SNAPSHOT_FIELDS,
    MAX_SYMBOLS_PER_REQUEST,
    PERF_METRICS_ALLOWLIST,
    SNAPSHOT_FIELDS_ALLOWLIST,
    VALID_PERF_PERIODS,
    UNITS_METADATA,
)
from app.services.yfinance_service import yfinance_service

logger = logging.getLogger(__name__)

relative_bp = Blueprint("relative", __name__, url_prefix="/api")


def parse_and_validate_symbols(symbols_str: str) -> list[str]:
    """Parse, validate, and de-duplicate symbols."""
    if not symbols_str or not symbols_str.strip():
        raise ValueError("symbols parameter is required")

    # Split, strip, uppercase, and filter empty
    raw_symbols = [s.strip().upper() for s in symbols_str.split(",") if s.strip()]

    if not raw_symbols:
        raise ValueError("At least one symbol is required")

    # De-duplicate while preserving order
    seen = set()
    symbols = []
    for s in raw_symbols:
        if s not in seen:
            seen.add(s)
            symbols.append(s)

    if len(symbols) > MAX_SYMBOLS_PER_REQUEST:
        raise ValueError(f"Maximum {MAX_SYMBOLS_PER_REQUEST} symbols allowed per request")

    return symbols


def parse_and_validate_fields(fields_str: Optional[str]) -> list[str]:
    """Parse and validate snapshot fields."""
    if not fields_str or not fields_str.strip():
        return DEFAULT_SNAPSHOT_FIELDS.copy()

    fields = [f.strip() for f in fields_str.split(",") if f.strip()]

    invalid_fields = [f for f in fields if f not in SNAPSHOT_FIELDS_ALLOWLIST]
    if invalid_fields:
        raise ValueError(
            f"Invalid fields: {', '.join(invalid_fields)}. Allowed: {', '.join(SNAPSHOT_FIELDS_ALLOWLIST.keys())}"
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
        raise ValueError(
            f"perfPeriod is required when perf is specified. Valid periods: {', '.join(VALID_PERF_PERIODS)}"
        )

    perf_period = perf_period.strip()
    if perf_period not in VALID_PERF_PERIODS:
        raise ValueError(
            f"Invalid perfPeriod: {perf_period}. Valid periods: {', '.join(VALID_PERF_PERIODS)}"
        )

    metrics = [m.strip() for m in perf_str.split(",") if m.strip()]
    invalid_metrics = [m for m in metrics if m not in PERF_METRICS_ALLOWLIST]
    if invalid_metrics:
        raise ValueError(
            f"Invalid perf metrics: {', '.join(invalid_metrics)}. Allowed: {', '.join(PERF_METRICS_ALLOWLIST)}"
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


@relative_bp.route("/relative", methods=["GET"])
def get_relative_table():
    """
    Get relative table data for multiple symbols.
    
    Query params:
    - symbols: Comma-separated ticker symbols (required)
    - fields: Comma-separated snapshot fields (optional)
    - perf: Comma-separated performance metrics (optional)
    - perfPeriod: Performance period (required if perf specified)
    - dcf: Include DCF valuation (true/false, optional)
    """
    try:
        symbols = request.args.get("symbols")
        fields = request.args.get("fields")
        perf = request.args.get("perf")
        perf_period = request.args.get("perfPeriod")
        dcf = request.args.get("dcf", "false").lower() == "true"

        logger.info(f"Relative table request: symbols={symbols}, fields={fields}, perf={perf}, perfPeriod={perf_period}, dcf={dcf}")

        # Parse and validate inputs
        validated_symbols = parse_and_validate_symbols(symbols)
        validated_fields = parse_and_validate_fields(fields)
        validated_perf_metrics, validated_perf_period = parse_and_validate_perf(perf, perf_period)

        # Fetch data
        rows_data, cache_hit = yfinance_service.get_relative(
            symbols=validated_symbols,
            fields=validated_fields,
            perf_metrics=validated_perf_metrics,
            perf_period=validated_perf_period,
            include_dcf=dcf,
        )

        # Build response
        as_of = yfinance_service.get_as_of_timestamp()

        perf_request = None
        if validated_perf_metrics and validated_perf_period:
            perf_request = {"period": validated_perf_period, "metrics": validated_perf_metrics}

        requested = {
            "symbols": validated_symbols,
            "fields": validated_fields,
            "perf": perf_request,
            "dcf": dcf,
        }

        # Build units metadata
        units = build_units_metadata(validated_fields, validated_perf_metrics, dcf)

        rows = [
            {
                "symbol": r["symbol"],
                "snapshot": r["snapshot"],
                "performance": r["performance"],
                "dcf": r.get("dcf") if dcf else None,
                "missingFields": r["missingFields"],
                "missingPerf": r["missingPerf"],
                "error": r["error"],
            }
            for r in rows_data
        ]

        response = jsonify({
            "asOf": as_of,
            "requested": requested,
            "units": units,
            "rows": rows,
        })
        response.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
        
        return response

    except ValueError as e:
        return jsonify({"error": "Bad request", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error processing relative table request: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500


@relative_bp.route("/relative/export", methods=["GET"])
def export_relative_table():
    """
    Export relative table data as CSV, XLSX, or PDF.
    
    Query params:
    - symbols: Comma-separated ticker symbols (required)
    - fields: Comma-separated snapshot fields (optional)
    - perf: Comma-separated performance metrics (optional)
    - perfPeriod: Performance period (required if perf specified)
    - dcf: Include DCF valuation (true/false, optional)
    - format: Export format (csv, xlsx, pdf; default: csv)
    """
    from app.services.export_service import build_table_rows, generate_csv, generate_xlsx, generate_pdf

    try:
        fmt = request.args.get("format", "csv").lower()
        if fmt not in ("csv", "xlsx", "pdf"):
            return jsonify({"error": "Bad request", "message": "Supported formats: csv, xlsx, pdf"}), 400

        symbols = request.args.get("symbols")
        fields = request.args.get("fields")
        perf = request.args.get("perf")
        perf_period = request.args.get("perfPeriod")
        dcf = request.args.get("dcf", "false").lower() == "true"

        logger.info(f"Export request (format={fmt}): symbols={symbols}, fields={fields}, perf={perf}, perfPeriod={perf_period}, dcf={dcf}")

        # Parse and validate inputs
        validated_symbols = parse_and_validate_symbols(symbols)
        validated_fields = parse_and_validate_fields(fields)
        validated_perf_metrics, validated_perf_period = parse_and_validate_perf(perf, perf_period)

        # Fetch data
        rows_data, cache_hit = yfinance_service.get_relative(
            symbols=validated_symbols,
            fields=validated_fields,
            perf_metrics=validated_perf_metrics,
            perf_period=validated_perf_period,
            include_dcf=dcf,
        )

        as_of = yfinance_service.get_as_of_timestamp()

        # Build normalised table data
        headers, flat_rows = build_table_rows(
            rows_data, validated_fields, validated_perf_metrics, include_dcf=dcf,
        )

        if fmt == "csv":
            content = generate_csv(headers, flat_rows)
            resp = Response(content, mimetype="text/csv")
            resp.headers["Content-Disposition"] = "attachment; filename=relative_table.csv"
        elif fmt == "xlsx":
            content = generate_xlsx(headers, flat_rows)
            resp = Response(content, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            resp.headers["Content-Disposition"] = "attachment; filename=relative_table.xlsx"
        else:  # pdf
            content = generate_pdf(headers, flat_rows)
            resp = Response(content, mimetype="application/pdf")
            resp.headers["Content-Disposition"] = "attachment; filename=relative_table.pdf"

        resp.headers["X-AsOf"] = as_of
        resp.headers["X-Cache"] = "HIT" if cache_hit else "MISS"
        return resp

    except ValueError as e:
        return jsonify({"error": "Bad request", "message": str(e)}), 400
    except Exception as e:
        logger.error(f"Error processing export request: {e}", exc_info=True)
        return jsonify({"error": "Internal server error", "message": "An unexpected error occurred"}), 500


@relative_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok"})
