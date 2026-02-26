"""
Maturities module — debt maturity ladder and covenants.

HARD RULE: Only ladder + covenants. No leverage ratios, no liquidity,
no share count.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    has_covenant_data,
    has_maturity_data,
    resolve_maturities_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute maturities context with fallbacks."""
    mat = (
        inputs.get("maturities")
        or inputs.get("debt_maturities")
        or inputs.get("maturity_ladder")
        or {}
    )
    if not isinstance(mat, dict):
        # Might be a list of maturity items directly
        if isinstance(mat, list):
            mat = {"ladder": mat}
        else:
            mat = {}

    raw_ladder = mat.get("ladder") or mat.get("maturities") or []
    if not isinstance(raw_ladder, list):
        raw_ladder = []

    ladder: list[dict[str, Any]] = []
    for item in raw_ladder[:10]:
        if isinstance(item, dict) and item.get("year_bucket"):
            ladder.append({
                "year_bucket": item["year_bucket"],
                "amount": item.get("amount"),
                "instrument": item.get("instrument"),
            })

    # Covenants — only if explicitly provided
    raw_covenants = mat.get("covenants") or inputs.get("covenants") or inputs.get("debt_covenants") or []
    if not isinstance(raw_covenants, list):
        raw_covenants = []

    covenants: list[dict[str, Any]] = []
    for cov in raw_covenants[:3]:
        if isinstance(cov, dict) and cov.get("description"):
            covenants.append({
                "type": cov.get("type", "other"),
                "description": cov["description"],
                "headroom": cov.get("headroom"),
            })

    confidence = resolve_maturities_confidence(len(ladder), bool(covenants))

    notes: str | None = None
    if not ladder:
        notes = "Maturity ladder not provided"

    return {
        "ladder": ladder,
        "covenants": covenants,
        "confidence": confidence,
        "notes": notes,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the maturities module."""
    parts: list[str] = ["## MATURITIES MODULE"]
    parts.append(
        "BOUNDARY: Only debt maturity ladder + covenants. NO leverage ratios, "
        "NO liquidity, NO share count."
    )

    if ctx["ladder"]:
        parts.append("Provided maturity ladder:")
        for item in ctx["ladder"]:
            amt = item.get("amount") or "N/A"
            inst = item.get("instrument") or ""
            inst_str = f" ({inst})" if inst else ""
            parts.append(f"  {item['year_bucket']}: {amt}{inst_str}")
    else:
        parts.append(
            "No maturity ladder provided. Set ladder to [] and "
            "confidence to 'low'. Set notes to 'Maturity ladder not provided'."
        )

    if ctx["covenants"]:
        parts.append("Provided covenant data:")
        for cov in ctx["covenants"]:
            headroom = f" (headroom: {cov['headroom']})" if cov.get("headroom") else ""
            parts.append(f"  [{cov['type']}] {cov['description']}{headroom}")
    else:
        parts.append(
            "No covenant data provided. Set covenants to []. "
            "NEVER infer covenant thresholds."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    if ctx.get("notes"):
        parts.append(f'Set notes to "{ctx["notes"]}".')

    parts.append(
        "\nINSTRUCTIONS:\n"
        "- takeaways: 1-3 bullet strings grounded in the data above.\n"
        "- NEVER fabricate maturities, amounts, or covenant levels.\n"
        "- Only include covenants if explicitly provided above."
    )

    return "\n\n".join(parts)
