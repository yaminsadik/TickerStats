"""
Variant View module — market-believes vs we-believe deltas.

Boundary: Only variant deltas. No new facts, no thesis sentence, no pillars.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.investment_thesis_variant_view.fallbacks import (
    build_variant_deltas,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute variant view context from inputs."""
    thesis = inputs.get("thesis") or {}

    market_believes = thesis.get("market_believes")
    we_believe = thesis.get("we_believe")
    deltas = build_variant_deltas(market_believes, we_believe)

    return {
        "market_believes_raw": market_believes,
        "we_believe_raw": we_believe,
        "pre_split_deltas": deltas,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for variant view."""
    parts = ["## MODULE: variant_view"]

    if ctx.get("market_believes_raw"):
        parts.append(f"\nMarket believes (user-provided): \"{ctx['market_believes_raw']}\"")
    else:
        parts.append("\nMarket believes: NOT PROVIDED")

    if ctx.get("we_believe_raw"):
        parts.append(f"We believe (user-provided): \"{ctx['we_believe_raw']}\"")
    else:
        parts.append("We believe: NOT PROVIDED")

    if ctx["pre_split_deltas"]:
        parts.append(f"\nPre-split into {len(ctx['pre_split_deltas'])} delta(s) for reference.")

    parts.extend([
        "",
        "INSTRUCTIONS:",
        "- variant_deltas: list of {market_believes, we_believe} pairs.",
        "- Polish each side for institutional clarity, but preserve meaning.",
        "- 1-3 pairs maximum. If user provided multiple points (newline or semicolon separated), split into separate deltas.",
        "- If either market_believes or we_believe is missing, return an empty variant_deltas list.",
        "",
        "HARD RULES:",
        "- Do NOT introduce new facts, numbers, or claims not present in user inputs.",
        "- Do NOT fabricate a market consensus or variant view if not provided.",
    ])

    return "\n".join(parts)
