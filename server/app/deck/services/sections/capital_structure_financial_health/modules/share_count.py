"""
Share Count module — diluted share history, buybacks, dividends, SBC dilution.

HARD RULE: Only dilution/buybacks/dividends/SBC. No leverage, no maturities,
no liquidity.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    has_share_data,
    resolve_share_count_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute share count context with fallbacks."""
    shares = (
        inputs.get("shares")
        or inputs.get("share_count")
        or inputs.get("dilution")
        or {}
    )
    if not isinstance(shares, dict):
        shares = {}

    # Share series
    raw_series = shares.get("share_series") or shares.get("series") or []
    if not isinstance(raw_series, list):
        raw_series = []

    share_series: list[dict[str, Any]] = []
    for pt in raw_series[:8]:
        if isinstance(pt, dict) and pt.get("period"):
            share_series.append({
                "period": pt["period"],
                "diluted_shares": pt.get("diluted_shares") or pt.get("value"),
            })

    # Buybacks — only if disclosed
    buybacks = shares.get("buybacks") or []
    if not isinstance(buybacks, list):
        buybacks = []
    buybacks = [str(b) for b in buybacks[:3] if b]

    # Dividends — only if disclosed
    dividends = shares.get("dividends") or []
    if not isinstance(dividends, list):
        dividends = []
    dividends = [str(d) for d in dividends[:2] if d]

    # SBC dilution — only if disclosed
    sbc = shares.get("sbc_dilution") or shares.get("sbc") or []
    if not isinstance(sbc, list):
        sbc = []
    sbc = [str(s) for s in sbc[:2] if s]

    confidence = resolve_share_count_confidence(
        len(share_series),
        bool(buybacks),
        bool(sbc),
    )

    return {
        "share_series": share_series,
        "buybacks": buybacks,
        "dividends": dividends,
        "sbc_dilution": sbc,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the share count module."""
    parts: list[str] = ["## SHARE COUNT MODULE"]
    parts.append(
        "BOUNDARY: Only dilution/buybacks/dividends/SBC. NO leverage, "
        "NO maturities, NO liquidity."
    )

    if ctx["share_series"]:
        parts.append("Provided share series (diluted):")
        for pt in ctx["share_series"]:
            val = pt.get("diluted_shares")
            val_str = f"{val}M" if val is not None else "N/A"
            parts.append(f"  {pt['period']}: {val_str}")
    else:
        parts.append(
            "No share series provided. Set share_series to [] and "
            "adjust confidence accordingly."
        )

    if ctx["buybacks"]:
        parts.append("Disclosed buybacks: " + "; ".join(ctx["buybacks"]))
    else:
        parts.append("No buyback disclosures. Set buybacks to [].")

    if ctx["dividends"]:
        parts.append("Disclosed dividends: " + "; ".join(ctx["dividends"]))
    else:
        parts.append("No dividend disclosures. Set dividends to [].")

    if ctx["sbc_dilution"]:
        parts.append("Disclosed SBC dilution: " + "; ".join(ctx["sbc_dilution"]))
    else:
        parts.append("No SBC disclosures. Set sbc_dilution to [].")

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- takeaways: 1-3 bullet strings grounded in the data above.\n"
        "- NEVER infer buyback dollars or SBC; only include if inputs provide.\n"
        "- Use only provided data; set null/empty where missing."
    )

    return "\n\n".join(parts)
