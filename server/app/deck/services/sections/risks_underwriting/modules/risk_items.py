"""
Risk Items module — rewrite user risks for clarity in institutional phrasing.

HARD RULE: DO NOT add new risks, rankings, or indicators.  Only polish
language while preserving meaning.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.risks_underwriting.fallbacks import apply_fallbacks


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute risk items context from user-provided risks."""
    raw_risks = inputs.get("risks") or []

    # Normalize to list of dicts (handle Pydantic model objects)
    risk_dicts: list[dict[str, Any]] = []
    for r in raw_risks:
        if isinstance(r, dict):
            risk_dicts.append(r)
        elif hasattr(r, "model_dump"):
            risk_dicts.append(r.model_dump())
        elif hasattr(r, "dict"):
            risk_dicts.append(r.dict())

    processed, notes = apply_fallbacks(risk_dicts)

    return {
        "risks": processed,
        "notes": notes,
        "risk_count": len(processed),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for risk items."""
    risks = ctx["risks"]

    if not risks:
        return """## MODULE: risk_items
No user-provided risks available.
Set the risks array to an empty list.
"""

    risk_lines: list[str] = []
    for i, r in enumerate(risks, 1):
        parts = [f"{i}. Risk: {r['risk']}"]
        parts.append(f"   Impact: {r['impact']}")
        parts.append(f"   Probability: {r['probability']}")
        if r.get("leading_indicator"):
            parts.append(f"   Leading indicator: {r['leading_indicator']}")
        if r.get("mitigant"):
            parts.append(f"   Mitigant: {r['mitigant']}")
        parts.append(f"   Rank score: {r.get('rank_score', 0)}")
        risk_lines.append("\n".join(parts))

    risk_block = "\n".join(risk_lines)

    return f"""## MODULE: risk_items
User-provided risks (already ranked by score, descending):

{risk_block}

INSTRUCTIONS:
- For each risk, rewrite the risk description for clarity and concise institutional phrasing.
- Keep the meaning identical. Do NOT change the substance.
- Preserve the exact impact, probability, leading_indicator, and mitigant values.
- Preserve rank_score values exactly as given above.
- Set per-item confidence as pre-computed (high/medium/low based on data completeness).

HARD RULES:
- Do NOT add new risks, indicators, or mitigants that are not listed above.
- Do NOT change impact/probability rankings.
- Do NOT invent leading indicators or mitigants.
- If impact or probability is "not_provided", keep it as "not_provided".
"""
