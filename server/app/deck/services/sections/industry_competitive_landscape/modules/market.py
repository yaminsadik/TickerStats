"""
Market module — market definition, sizing, and growth drivers.

HARD RULES:
- NO moat claims, NO competitor ranking.
- TAM only if grounded in disclosed data; otherwise use proxy bullets.
- No invented dollar figures, percentages, or CAGR numbers.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute market context from inputs."""
    company = inputs.get("company") or {}
    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "ticker": company.get("ticker") or inputs.get("ticker", ""),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry") or inputs.get("industry"),
        "description": company.get("description") or inputs.get("description", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the market module."""
    return f"""## MODULE: market
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"] or "not specified"}, Industry: {ctx["industry"] or "not specified"}
Description: {ctx["description"] or "N/A"}

INSTRUCTIONS:
- Provide a 1–2 sentence market definition.
- If TAM is disclosed in public filings or earnings, include tam_value (e.g. "$220B") and tam_basis.
- If TAM is NOT disclosed: leave tam_value null and provide 1–3 proxy_sizing bullets describing market scale qualitatively.
- Provide 2–5 growth drivers as concise bullets.
- growth_chart_notes: only include CAGR or growth statements if they come from disclosed data.

HARD RULES:
- Do NOT invent dollar figures, percentages, or CAGR numbers.
- Do NOT rank competitors or make moat claims — those belong to other modules.
- Set confidence: "high" if using disclosed TAM, "medium" if proxies only, "low" if neither.
"""
