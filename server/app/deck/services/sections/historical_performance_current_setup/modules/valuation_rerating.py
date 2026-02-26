"""
Valuation Rerating module — multiples history, median comparison, peer context.

HARD RULE: Only multiples/premium/median context, no operating KPIs.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    has_rerating_data as _has_rerating,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute rerating context with fallbacks."""
    rerating = (
        inputs.get("rerating")
        or inputs.get("valuation_multiples")
        or inputs.get("multiples")
        or {}
    )
    if not isinstance(rerating, dict):
        rerating = {}

    has_data = _has_rerating(inputs)

    current = rerating.get("current")
    median = rerating.get("median") or rerating.get("historical_median")
    series = rerating.get("series") or []
    if not isinstance(series, list):
        series = []

    peer_context = rerating.get("peer_context") or rerating.get("comps_context") or []
    if not isinstance(peer_context, list):
        peer_context = [peer_context] if peer_context else []

    # Build current_vs_median statements only if both values present
    current_vs_median: list[str] = []
    if current is not None and median is not None:
        multiple_name = rerating.get("multiple_name", "EV/EBITDA")
        current_vs_median.append(
            f"Current {multiple_name}: {current} vs historical median: {median}"
        )

    confidence: str
    notes: str | None = None
    if has_data and (current is not None or series):
        confidence = "high"
    elif has_data:
        confidence = "medium"
    else:
        confidence = "low"
        notes = "No valuation multiples data provided"

    return {
        "has_data": has_data,
        "current": current,
        "median": median,
        "series": series[:2],  # cap at 2
        "current_vs_median": current_vs_median[:3],
        "peer_context": peer_context[:3],
        "confidence": confidence,
        "notes": notes,
        "multiple_name": rerating.get("multiple_name", ""),
        "company_name": inputs.get("company_name", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the rerating module."""
    parts: list[str] = ["## VALUATION RERATING MODULE"]
    parts.append(
        "BOUNDARY: Only multiples/premium/median context. NO operating KPIs, "
        "NO price charts, NO revenue/margin discussion."
    )

    if ctx["has_data"]:
        if ctx["current"] is not None:
            parts.append(f"Current multiple value: {ctx['current']}")
        if ctx["median"] is not None:
            parts.append(f"Historical median: {ctx['median']}")
        if ctx["multiple_name"]:
            parts.append(f"Multiple name: {ctx['multiple_name']}")

        if ctx["current_vs_median"]:
            parts.append("Current vs median statements (use as provided):")
            for s in ctx["current_vs_median"]:
                parts.append(f"  - {s}")

        if ctx["peer_context"]:
            parts.append("Peer context statements (use as provided):")
            for s in ctx["peer_context"]:
                parts.append(f"  - {s}")

        if ctx["series"]:
            parts.append("Historical multiple series:")
            for ms in ctx["series"]:
                if isinstance(ms, dict):
                    name = ms.get("multiple_name", "unknown")
                    points = ms.get("points", [])
                    parts.append(f"  {name}: {len(points)} data points")
    else:
        parts.append(
            "No valuation multiples data provided. Set confidence to 'low', "
            "use empty lists for current_vs_median, peer_context, series. "
            "Provide 2 generic rerating takeaways noting data limitations."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- current_vs_median: 0-3 statements ONLY if inputs provide both current and median values.\n"
        "- peer_context: 0-3 statements ONLY if peer/comps data is provided.\n"
        "- takeaways: 2-4 sentences interpreting the multiple trajectory.\n"
        "- NEVER fabricate multiple values. Use only provided data."
    )

    return "\n\n".join(parts)
