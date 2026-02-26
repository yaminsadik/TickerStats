"""
Porter's Five Forces module.

HARD RULES:
- Must output EXACTLY 5 forces.
- Pressures must be justified with 1–2 grounded bullets.
- No invented metrics or fabricated numbers.
"""

from __future__ import annotations

from typing import Any

FIVE_FORCES = [
    "Threat of New Entrants",
    "Bargaining Power of Suppliers",
    "Bargaining Power of Buyers",
    "Threat of Substitutes",
    "Competitive Rivalry",
]


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute Porter's context from inputs."""
    company = inputs.get("company") or {}
    return {
        "company_name": company.get("name") or inputs.get("company_name", "Unknown"),
        "ticker": company.get("ticker") or inputs.get("ticker", ""),
        "sector": company.get("sector") or inputs.get("sector"),
        "industry": company.get("industry") or inputs.get("industry"),
        "description": company.get("description") or inputs.get("description", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the Porter's module."""
    forces_list = "\n".join(f"  {i+1}. {f}" for i, f in enumerate(FIVE_FORCES))
    return f"""## MODULE: porters
Company: {ctx["company_name"]} ({ctx["ticker"]})
Sector: {ctx["sector"] or "not specified"}, Industry: {ctx["industry"] or "not specified"}

INSTRUCTIONS:
- Output EXACTLY 5 forces (no more, no fewer):
{forces_list}
- For each force: force name, pressure (low/medium/high), because (1–2 justification bullets), evidence (grounded fact or null).

HARD RULES:
- You MUST include all five forces listed above with those exact names.
- Pressures MUST be justified with 1–2 grounded bullets in the "because" array.
- Do NOT invent metrics. If evidence is unavailable, set evidence to null.
- Set confidence: "high" if grounded reasoning for most forces, "medium" if partially supported, "low" if mostly generic.
"""
