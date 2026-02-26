"""
Positioning module — business positioning bullets.

HARD RULE: ONLY the positioning sentence (already in header) plus 3-6
qualitative bullets. NO metrics, NO dollar values, NO percentages.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute positioning context."""
    company = inputs.get("company") or {}
    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the positioning module."""
    return f"""## MODULE: positioning
Company: {ctx["company_name"]}
Sector: {ctx["sector"] or "not specified"}, Industry: {ctx["industry"] or "not specified"}

INSTRUCTIONS:
- Provide 3 to 6 concise institutional-quality bullets describing the company's competitive positioning.
- Each bullet should be one sentence, professional tone.
- Bullets describe *qualitative* positioning: market position, competitive advantages, strategic differentiators.

HARD RULES:
- NO dollar values, percentages, or numeric metrics in bullets.
- NO revenue, margin, growth rate, or financial figures.
- NO segment mix, customer data, geographic data, or KPIs — those belong to other modules.
- Set confidence to "high" if sector/industry are known, "medium" if only sector, "low" if neither.
"""
