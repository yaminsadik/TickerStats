"""
Money Model module — how the company makes money.

HARD RULE: ONLY pricing unit, contract structure, recurrence, cost drivers.
No segment mix, no KPIs.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_money_model,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute money model context with fallbacks."""
    company = inputs.get("company") or {}
    raw_pricing = inputs.get("money_model", {})
    if isinstance(raw_pricing, dict):
        pricing_unit = raw_pricing.get("pricing_unit")
        contract_structure = raw_pricing.get("contract_structure")
        recurrence = raw_pricing.get("recurrence")
        cost_drivers = raw_pricing.get("cost_drivers")
    else:
        pricing_unit = None
        contract_structure = None
        recurrence = None
        cost_drivers = None

    resolved_unit, confidence, notes = resolve_money_model(
        pricing_unit,
        sector=company.get("sector") or inputs.get("sector"),
        industry=company.get("industry"),
    )

    return {
        "pricing_unit": resolved_unit,
        "contract_structure": contract_structure,
        "recurrence": recurrence,
        "cost_drivers": cost_drivers,
        "confidence": confidence,
        "notes": notes,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the money model module."""
    parts = [f"## MODULE: money_model"]

    if ctx["pricing_unit"]:
        parts.append(f"Pricing unit (pre-resolved): {ctx['pricing_unit']}")
    if ctx["contract_structure"]:
        parts.append(f"Contract structure: {ctx['contract_structure']}")
    if ctx["recurrence"]:
        parts.append(f"Recurrence: {ctx['recurrence']}")
    if ctx["cost_drivers"]:
        drivers = ", ".join(ctx["cost_drivers"])
        parts.append(f"Known cost drivers: {drivers}")

    conf = ctx["confidence"]
    notes_hint = ""
    if ctx["notes"]:
        notes_hint = f'\n- Set notes to: "{ctx["notes"]}"'

    parts.append(f"""
INSTRUCTIONS:
- pricing_unit: use the pre-resolved value above. If it says "not disclosed", keep it as-is.
- contract_structure: describe as "multi-year contracted", "transactional", "annual renewable", etc.
  If unknown, infer from sector but note the inference.
- recurrence: one of "mostly recurring", "mostly cyclical", "mixed".
  If unknown, infer from sector but note the inference.
- cost_drivers: provide 2 to 4 key cost drivers. If data is sparse, infer plausible drivers from industry.
- Set confidence to "{conf}".{notes_hint}

HARD RULES:
- ONLY pricing unit, contract structure, recurrence, cost drivers.
- No segment mix, no KPIs, no financial ratios.
- Never fabricate numeric pricing figures.
""")

    return "\n".join(parts)
