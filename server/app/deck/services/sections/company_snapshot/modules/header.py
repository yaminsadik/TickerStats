"""
Header module — identity line + positioning sentence + quick stats row.

This module is always required. It assembles the top-line identity from
the company input and delegates quick-stats computation to fallbacks.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_quick_stats,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute header context from orchestrator inputs."""
    company = inputs.get("company") or {}
    financials = inputs.get("financials") or {}

    stats, low_flag = resolve_quick_stats(financials)

    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "ticker": company.get("ticker") or inputs.get("ticker", "N/A"),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry"),
        "quick_stats": stats,
        "low_confidence_flag": low_flag,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment that instructs the LLM on the header."""
    stats_hint = ""
    if ctx["quick_stats"]:
        items = ", ".join(
            f'{s["label"]}: {s["value"]}' for s in ctx["quick_stats"]
        )
        stats_hint = f"\nPre-computed quick stats (use these values exactly): {items}"
    else:
        stats_hint = "\nNo financial data available — quick_stats array should be empty."

    return f"""## HEADER
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"] or "not specified"}
Industry: {ctx["industry"] or "not specified"}
{stats_hint}

INSTRUCTIONS:
- Write ONE concise positioning_sentence (max 30 words) describing what the company does and why it matters.
- Copy the quick_stats array exactly as provided above. Do NOT invent financial figures.
- Set low_confidence_flag to {"true" if ctx["low_confidence_flag"] else "false"}.
"""
