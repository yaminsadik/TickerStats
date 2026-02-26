"""
Moat module — moat drivers categorized with mechanism and evidence.

HARD RULES:
- State drivers neutrally: mechanism + evidence, no hype language.
- No valuation talk, no price targets, no multiples.
- Evidence must be grounded; if none, set evidence to null.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute moat context from inputs."""
    company = inputs.get("company") or {}
    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "ticker": company.get("ticker") or inputs.get("ticker", ""),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry") or inputs.get("industry"),
        "description": company.get("description") or inputs.get("description", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the moat module."""
    return f"""## MODULE: moat
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"] or "not specified"}, Industry: {ctx["industry"] or "not specified"}

INSTRUCTIONS:
- Identify 3–5 moat pillars. For each: pillar name, mechanism (how it works), evidence (from disclosed data or null).
- State every driver neutrally — describe the mechanism and cite evidence. No hype language, no superlatives.

HARD RULES:
- Do NOT discuss valuation, price targets, multiples, or financial projections.
- Do NOT use hype language (e.g. "unassailable", "best-in-class", "dominant"). Use neutral institutional phrasing.
- If no grounded evidence exists for a pillar, set evidence to null.
- Set confidence: "high" if evidence is available for most pillars, "medium" if partially evidenced, "low" if mostly inferred.
"""
