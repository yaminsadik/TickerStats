"""
Fundamentals module — revenue trend, profitability, cash flow, ROIC/ROE.

HARD RULE: Only operating/financial trends, no price talk.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    filter_series_with_min_points,
    resolve_fundamentals_confidence,
    resolve_window_years,
    select_priority_metrics,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute fundamentals context with fallbacks."""
    financials = inputs.get("financials") or inputs.get("fundamentals") or {}
    if not isinstance(financials, dict):
        financials = {}

    window_years = resolve_window_years(financials)

    # Extract available metric series
    raw_series = financials.get("series") or []
    if not isinstance(raw_series, list):
        raw_series = []

    # Filter to series with >=3 non-null points
    filtered_series = filter_series_with_min_points(raw_series, min_points=3)

    # Identify available metric IDs
    available_metrics = [
        s.get("metric") for s in filtered_series
        if isinstance(s, dict) and s.get("metric")
    ]

    # Select priority metrics
    selected = select_priority_metrics(available_metrics)

    # Keep only selected series (in priority order)
    selected_series = []
    for metric_id in selected:
        for s in filtered_series:
            if isinstance(s, dict) and s.get("metric") == metric_id:
                selected_series.append(s)
                break

    confidence = resolve_fundamentals_confidence(window_years, len(selected_series))

    return {
        "window_years": window_years,
        "series": selected_series,
        "available_metrics": selected,
        "company_name": inputs.get("company_name", ""),
        "ticker": inputs.get("ticker", ""),
        "sector": inputs.get("sector", ""),
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the fundamentals module."""
    parts: list[str] = ["## FUNDAMENTALS MODULE"]
    parts.append(
        "BOUNDARY: Only operating/financial trends. NO price talk, no multiples, "
        "no benchmark comparisons."
    )

    parts.append(f"Window: {ctx['window_years']} years")

    if ctx["series"]:
        parts.append("Provided historical series:")
        for s in ctx["series"]:
            if isinstance(s, dict):
                metric = s.get("metric", "unknown")
                label = s.get("label", metric)
                unit = s.get("unit", "")
                points = s.get("points", [])
                point_strs = []
                for p in points:
                    if isinstance(p, dict):
                        period = p.get("period", "?")
                        val = p.get("value")
                        val_str = str(val) if val is not None else "N/A"
                        point_strs.append(f"{period}={val_str}")
                parts.append(f"  {label} ({unit}): {', '.join(point_strs)}")
    else:
        parts.append(
            "No historical series data provided. Set confidence to 'low' "
            "and generate highlights based only on available context."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- highlights: 3-6 bullet strings grounded in the series data above.\n"
        "- Include ROIC/ROE only if those series were provided above.\n"
        "- NEVER fabricate or infer numeric values. Use only provided data.\n"
        "- If fewer than 3 series, note data limitations in the notes field."
    )

    return "\n\n".join(parts)
