"""
Stock vs Benchmark module — price performance comparison.

HARD RULE: Only price/benchmark data, no fundamentals.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    has_price_series_data as _has_price,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute stock vs benchmark context."""
    has_data = _has_price(inputs)

    price = inputs.get("price_history") or inputs.get("price_series") or {}
    benchmark_name: str | None = None
    series: list[dict[str, Any]] = []

    if isinstance(price, dict):
        benchmark_name = price.get("benchmark_name") or price.get("benchmark")
        raw_series = price.get("series") or []
        if not isinstance(raw_series, list):
            raw_series = []
        # Also check for flat points
        if not raw_series:
            points = price.get("points") or price.get("prices") or []
            if isinstance(points, list) and points:
                company_name = inputs.get("company_name", inputs.get("ticker", "Company"))
                raw_series = [{"name": company_name, "points": points}]
        series = raw_series[:2]  # cap at 2

    confidence: str
    notes: str | None = None
    if has_data and series:
        confidence = "high" if len(series) >= 2 else "medium"
    else:
        confidence = "low"
        notes = "No price series data provided"

    return {
        "has_data": has_data,
        "benchmark_name": benchmark_name,
        "series": series,
        "confidence": confidence,
        "notes": notes,
        "company_name": inputs.get("company_name", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the stock vs benchmark module."""
    parts: list[str] = ["## STOCK VS BENCHMARK MODULE"]
    parts.append(
        "BOUNDARY: Only price/benchmark comparison. NO fundamentals, "
        "NO multiples, NO operating metrics."
    )

    if ctx["has_data"]:
        if ctx["benchmark_name"]:
            parts.append(f"Benchmark: {ctx['benchmark_name']}")

        for s in ctx["series"]:
            if isinstance(s, dict):
                name = s.get("name", "unknown")
                points = s.get("points", [])
                parts.append(f"  Series '{name}': {len(points)} data points")
    else:
        parts.append(
            "No price series data provided. Set confidence to 'low', "
            "use empty series list. Provide 2 takeaways noting data limitations."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- takeaways: 2-4 sentences about price performance relative to benchmark.\n"
        "- NEVER fabricate price data or returns. Use only provided data.\n"
        "- If no benchmark provided, note that in takeaways."
    )

    return "\n\n".join(parts)
