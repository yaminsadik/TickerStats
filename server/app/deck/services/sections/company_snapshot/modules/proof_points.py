"""
Proof Points module — operational KPIs only.

HARD RULE: ONLY operational KPIs. No margins, EPS, growth rates, valuation
multiples.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_proof_points_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute proof points context with fallbacks."""
    raw_pp = inputs.get("proof_points") or {}
    if isinstance(raw_pp, dict):
        kpis = raw_pp.get("kpis") or raw_pp.get("operational_kpis") or []
    elif isinstance(raw_pp, list):
        kpis = raw_pp
    else:
        kpis = []

    confidence, notes = resolve_proof_points_confidence(kpis or None)

    return {
        "kpis": kpis,
        "sector": inputs.get("sector") or (inputs.get("company") or {}).get("sector"),
        "industry": inputs.get("industry") or (inputs.get("company") or {}).get("industry"),
        "confidence": confidence,
        "notes": notes,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for proof points."""
    if ctx["kpis"]:
        kpi_list = "\n".join(
            f'  - {k.get("label", "KPI")}: {k.get("value", "N/A")}'
            for k in ctx["kpis"]
            if isinstance(k, dict)
        )
        kpi_hint = f"Known operational KPIs:\n{kpi_list}"
    else:
        context = " / ".join(
            str(value)
            for value in [ctx.get("sector"), ctx.get("industry")]
            if value
        )
        kpi_hint = (
            "No operational KPIs provided — infer 3 plausible KPIs from "
            f"sector/industry if possible. Context: {context or 'not provided'}."
        )

    notes_hint = ""
    if ctx["notes"]:
        notes_hint = f'\n- Set notes to: "{ctx["notes"]}"'

    return f"""## MODULE: proof_points
{kpi_hint}

INSTRUCTIONS:
- kpis: list 3 to 6 operational KPIs with label, value, and optional as_of.
- Use provided KPIs if available. If fewer than 3 are provided, include what exists.
- If inferring KPIs, infer KPI names only; set value to "not provided" unless explicitly supplied.
- Set confidence to "{ctx["confidence"]}".{notes_hint}

HARD RULES:
- ONLY operational KPIs: capacity, units, locations, backlog, ARR, retention, market share, etc.
- NO margins, NO EPS, NO growth rates, NO valuation multiples (P/E, EV/EBITDA, etc.).
- NO revenue or income figures — those belong in quick_stats.
"""
