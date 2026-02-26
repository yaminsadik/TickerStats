"""
Customers module — customer types, concentration, credit quality.

HARD RULE: ONLY customer types and concentration and credit quality if relevant.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_customer_concentration,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute customers context with fallbacks."""
    raw_customers = inputs.get("customers") or {}
    if isinstance(raw_customers, dict):
        types_ = raw_customers.get("types") or raw_customers.get("customer_types")
        concentration = raw_customers.get("concentration")
        credit_quality = raw_customers.get("credit_quality")
    else:
        types_ = None
        concentration = None
        credit_quality = None

    resolved_conc, max_confidence = resolve_customer_concentration(concentration)

    return {
        "types": types_,
        "concentration": resolved_conc,
        "credit_quality": credit_quality,
        "confidence": max_confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the customers module."""
    types_hint = ""
    if ctx["types"]:
        types_hint = f"Known customer types: {', '.join(ctx['types'])}"
    else:
        types_hint = "No customer types provided — infer 2-3 plausible types from sector/industry."

    cq_hint = ""
    if ctx["credit_quality"]:
        cq_hint = f"\nCredit quality: {ctx['credit_quality']}"

    return f"""## MODULE: customers
{types_hint}
Concentration: {ctx["concentration"]}{cq_hint}

INSTRUCTIONS:
- types: list 2 to 5 customer types. Use provided types if available; otherwise infer.
- concentration: use the value above verbatim.
- credit_quality: include only if relevant (e.g. investment-grade counterparties). Set null otherwise.
- Set confidence to at most "{ctx["confidence"]}". Lower if types are fully inferred.

HARD RULES:
- ONLY customer types, concentration, credit quality.
- No revenue mix, no segment data, no geographic data, no KPIs.
"""
