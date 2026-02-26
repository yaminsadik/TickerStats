"""
Leverage & Interest module — net-debt/EBITDA series and interest burden metrics.

HARD RULE: Only leverage + interest burden. No maturities, no liquidity,
no share count.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    has_leverage_data,
    resolve_leverage_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute leverage & interest context with fallbacks."""
    debt = (
        inputs.get("leverage")
        or inputs.get("debt")
        or inputs.get("capital_structure")
        or {}
    )
    if not isinstance(debt, dict):
        debt = {}

    # Extract leverage series
    raw_series = debt.get("leverage_series") or debt.get("series") or []
    if not isinstance(raw_series, list):
        raw_series = []

    leverage_series: list[dict[str, Any]] = []
    for pt in raw_series:
        if isinstance(pt, dict) and pt.get("period"):
            leverage_series.append({
                "period": pt["period"],
                "net_debt_to_ebitda": pt.get("net_debt_to_ebitda") or pt.get("value"),
            })

    # Current value
    current = (
        debt.get("current_net_debt_to_ebitda")
        or debt.get("net_debt_to_ebitda")
    )

    # Interest metrics
    raw_interest = debt.get("interest_metrics") or []
    if not isinstance(raw_interest, list):
        raw_interest = []

    interest_metrics: list[dict[str, Any]] = []
    for m in raw_interest[:3]:
        if isinstance(m, dict) and m.get("label") and m.get("value"):
            interest_metrics.append({
                "label": m["label"],
                "value": str(m["value"]),
                "as_of": m.get("as_of"),
            })

    # Single interest-coverage shortcut
    if not interest_metrics:
        ic_val = debt.get("interest_coverage")
        if ic_val is not None:
            interest_metrics.append({
                "label": "Interest coverage",
                "value": str(ic_val),
                "as_of": None,
            })

    confidence = resolve_leverage_confidence(
        len(leverage_series),
        current is not None,
    )

    return {
        "leverage_series": leverage_series,
        "current_net_debt_to_ebitda": current,
        "interest_metrics": interest_metrics,
        "confidence": confidence,
        "company_name": inputs.get("company_name", ""),
        "ticker": inputs.get("ticker", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the leverage & interest module."""
    parts: list[str] = ["## LEVERAGE & INTEREST MODULE"]
    parts.append(
        "BOUNDARY: Only leverage + interest burden. NO maturities, "
        "NO liquidity, NO share count."
    )

    if ctx["leverage_series"]:
        parts.append("Provided leverage series:")
        for pt in ctx["leverage_series"]:
            val = pt.get("net_debt_to_ebitda")
            val_str = f"{val}x" if val is not None else "N/A"
            parts.append(f"  {pt['period']}: Net Debt/EBITDA = {val_str}")
    else:
        parts.append(
            "No leverage series provided. Set leverage_series to [] and "
            "confidence to 'low' if no current value either."
        )

    if ctx["current_net_debt_to_ebitda"] is not None:
        parts.append(f"Current Net Debt/EBITDA: {ctx['current_net_debt_to_ebitda']}x")

    if ctx["interest_metrics"]:
        parts.append("Interest metrics:")
        for m in ctx["interest_metrics"]:
            as_of = f" (as of {m['as_of']})" if m.get("as_of") else ""
            parts.append(f"  {m['label']}: {m['value']}{as_of}")
    else:
        parts.append("No interest metrics provided.")

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- takeaways: 2-4 bullet strings grounded in the data above.\n"
        "- NEVER fabricate leverage ratios, interest figures, or coverage.\n"
        "- Use only provided data; set null where missing."
    )

    return "\n\n".join(parts)
