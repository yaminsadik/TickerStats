"""
Competition module — competitive set and positioning.

HARD RULES:
- NO TAM numbers unless already provided by the market module.
- List 3–8 competitors with type and relevance.
- Provide a 2-axis positioning map description.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute competition context from inputs."""
    company = inputs.get("company") or {}
    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "ticker": company.get("ticker") or inputs.get("ticker", ""),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry") or inputs.get("industry"),
        "description": company.get("description") or inputs.get("description", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the competition module."""
    return f"""## MODULE: competition
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"] or "not specified"}, Industry: {ctx["industry"] or "not specified"}
Description: {ctx["description"] or "N/A"}

INSTRUCTIONS:
- List 3–8 competitors. For each: name, type (direct/adjacent/substitute), why_relevant (1 sentence).
- Provide a positioning axis: x_label, y_label, company_position (e.g. "top-right"), key_differentiator.

HARD RULES:
- Do NOT include TAM numbers or market size figures — those belong to the market module.
- Do NOT make moat/valuation claims — those belong to other modules.
- If you cannot identify specific competitor names from available data, use category-level descriptions (e.g. "large incumbents").
- Set confidence: "high" if named competitors are well-established, "medium" if partially inferred, "low" if mostly generic.
"""
