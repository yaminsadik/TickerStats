"""
Liquidity module — cash, liquidity metrics, and runway.

HARD RULE: Only cash/liquidity/runway. No leverage ratios, no maturities,
no share count.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    has_burn_rate,
    resolve_liquidity_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute liquidity context with fallbacks."""
    liquidity = inputs.get("liquidity") or inputs.get("cash") or {}
    if not isinstance(liquidity, dict):
        liquidity = {}

    # Extract metrics
    raw_metrics = liquidity.get("metrics") or []
    if not isinstance(raw_metrics, list):
        raw_metrics = []

    metrics: list[dict[str, Any]] = []
    for m in raw_metrics[:5]:
        if isinstance(m, dict) and m.get("label") and m.get("value"):
            metrics.append({
                "label": m["label"],
                "value": str(m["value"]),
                "as_of": m.get("as_of"),
            })

    # Shortcut: if no structured metrics but we have a cash value, add it
    if not metrics:
        cash_val = liquidity.get("cash") or liquidity.get("cash_and_equivalents")
        if cash_val is not None:
            metrics.append({
                "label": "Cash & equivalents",
                "value": str(cash_val),
                "as_of": None,
            })

    # Runway — ONLY if burn rate is provided as numeric
    runway: dict[str, str] | None = None
    if has_burn_rate(inputs):
        raw_runway = liquidity.get("runway")
        if isinstance(raw_runway, dict) and raw_runway.get("basis") and raw_runway.get("estimate"):
            runway = {
                "basis": raw_runway["basis"],
                "estimate": raw_runway["estimate"],
            }

    confidence = resolve_liquidity_confidence(len(metrics), runway is not None)

    return {
        "metrics": metrics,
        "runway": runway,
        "confidence": confidence,
        "has_burn_rate": has_burn_rate(inputs),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the liquidity module."""
    parts: list[str] = ["## LIQUIDITY MODULE"]
    parts.append(
        "BOUNDARY: Only cash/liquidity/runway. NO leverage ratios, "
        "NO maturities, NO share count."
    )

    if ctx["metrics"]:
        parts.append("Provided liquidity metrics:")
        for m in ctx["metrics"]:
            as_of = f" (as of {m['as_of']})" if m.get("as_of") else ""
            parts.append(f"  {m['label']}: {m['value']}{as_of}")
    else:
        parts.append("No liquidity metrics provided.")

    if ctx["runway"]:
        parts.append(f"Runway: {ctx['runway']['basis']} → {ctx['runway']['estimate']}")
    elif ctx["has_burn_rate"]:
        parts.append(
            "Burn rate data exists but no pre-computed runway. "
            "Do NOT compute runway yourself — set runway to null."
        )
    else:
        parts.append(
            "No burn rate provided. Set runway to null. "
            "Do NOT fabricate or estimate runway."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- takeaways: 1-3 bullet strings grounded in the data above.\n"
        "- NEVER fabricate cash amounts, revolver availability, or runway.\n"
        "- runway: include ONLY if provided above; otherwise null."
    )

    return "\n\n".join(parts)
