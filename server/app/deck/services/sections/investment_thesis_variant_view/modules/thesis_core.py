"""
Thesis Core module — header, thesis sentence, and pillars.

Boundary: Only header fields, thesis sentence, and pillars.
Does not touch variant deltas, debates, or flip conditions.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.investment_thesis_variant_view.fallbacks import (
    normalize_position,
    select_pillars,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute thesis core context from inputs."""
    thesis = inputs.get("thesis") or {}
    fund_constraints = inputs.get("fund_constraints") or {}

    return {
        "ticker": inputs.get("ticker", "UNKNOWN"),
        "company_name": inputs.get("company_name"),
        "sector": inputs.get("sector"),
        "position": normalize_position(inputs.get("position")),
        "time_horizon": fund_constraints.get("time_horizon") or thesis.get("time_horizon"),
        "thesis_sentence": thesis.get("thesis_sentence"),
        "pillars": select_pillars(thesis.get("pillars")),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for thesis core."""
    parts = [
        "## MODULE: thesis_core",
        f"Ticker: {ctx['ticker']}",
    ]
    if ctx.get("company_name"):
        parts.append(f"Company: {ctx['company_name']}")
    if ctx.get("sector"):
        parts.append(f"Sector: {ctx['sector']}")
    parts.append(f"Position: {ctx['position']}")
    if ctx.get("time_horizon"):
        parts.append(f"Time Horizon: {ctx['time_horizon']}")

    if ctx.get("thesis_sentence"):
        parts.append(f"\nUser thesis sentence: \"{ctx['thesis_sentence']}\"")
    else:
        parts.append("\nUser thesis sentence: NOT PROVIDED")

    if ctx["pillars"]:
        parts.append("User thesis pillars:")
        for i, p in enumerate(ctx["pillars"], 1):
            parts.append(f"  {i}. {p}")
    else:
        parts.append("User thesis pillars: NOT PROVIDED")

    parts.extend([
        "",
        "INSTRUCTIONS:",
        "- Populate header with ticker, company_name, position, time_horizon.",
        "- thesis_sentence: lightly polish the user's sentence for clarity. Do NOT change meaning.",
        "- thesis_pillars: return the user's pillars, polished for institutional phrasing. Do NOT add new pillars.",
        "- If user did not provide a sentence or pillars, set those fields to null / empty list.",
        "",
        "HARD RULES:",
        "- Do NOT invent a thesis sentence if the user did not provide one.",
        "- Do NOT add pillars beyond what the user provided.",
        "- Preserve the user's intended meaning exactly.",
    ])

    return "\n".join(parts)
