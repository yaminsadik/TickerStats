"""
Quick Stats module — financial headline numbers row.

This module primarily delegates to the fallback helper. The prompt fragment
instructs the LLM to pass through the pre-computed stats verbatim.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_quick_stats,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute quick stats from financials."""
    financials = inputs.get("financials") or {}
    stats, low_flag = resolve_quick_stats(financials)
    return {
        "stats": stats,
        "low_confidence_flag": low_flag,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for quick stats (purely pass-through)."""
    if not ctx["stats"]:
        return """## MODULE: quick_stats
No financial data provided. The quick_stats array in the header must be empty.
"""
    items = "\n".join(
        f'  - {s["label"]}: {s["value"]}' for s in ctx["stats"]
    )
    return f"""## MODULE: quick_stats
Use these pre-computed values verbatim in header.quick_stats:
{items}

HARD RULES:
- Maximum 6 items. Do NOT add stats that are not listed above.
- Do NOT fabricate financial figures.
- Prefer: Market Cap, EV, Revenue, EBITDA/OpInc, FCF, Net Debt/Leverage.
"""
