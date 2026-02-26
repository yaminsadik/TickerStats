"""
Business Model module — what they sell, who, revenue flow, pricing/contract.

HARD RULE: No segment mix %, no unit economics metrics.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.business_model_segments.fallbacks import (
    has_pricing_notes,
    resolve_business_model_confidence,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute business model context with fallbacks."""
    bm = inputs.get("business_model") or {}
    confidence, notes = resolve_business_model_confidence(inputs)

    return {
        "what_they_sell": bm.get("what_they_sell") or [],
        "who_they_sell_to": bm.get("who_they_sell_to") or [],
        "revenue_flow": bm.get("revenue_flow") or [],
        "has_pricing_notes": has_pricing_notes(inputs),
        "pricing_contract_notes": (
            bm.get("pricing_contract_notes")
            or bm.get("pricing_notes")
            or []
        ),
        "description": (
            inputs.get("company_description")
            or inputs.get("business_description")
            or bm.get("description")
            or ""
        ),
        "sector": inputs.get("sector", ""),
        "industry": inputs.get("industry", ""),
        "company_name": inputs.get("company_name", ""),
        "confidence": confidence,
        "notes": notes,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the business_model module."""
    parts: list[str] = ["## BUSINESS MODEL MODULE"]
    parts.append(
        "BOUNDARY: Only what they sell, who they sell to, revenue generation flow, "
        "and pricing/contract notes (if disclosed). NO segment mix %, NO unit economics metrics."
    )

    if ctx["description"]:
        parts.append(f"Company description: {ctx['description']}")
    if ctx["sector"]:
        parts.append(f"Sector: {ctx['sector']}")
    if ctx["industry"]:
        parts.append(f"Industry: {ctx['industry']}")

    if ctx["what_they_sell"]:
        items = ", ".join(ctx["what_they_sell"])
        parts.append(f"Known products/services: {items}")

    if ctx["who_they_sell_to"]:
        items = ", ".join(ctx["who_they_sell_to"])
        parts.append(f"Known customer types: {items}")

    if ctx["revenue_flow"]:
        flow_str = "\n".join(
            f"  {i+1}. {s.get('step', s) if isinstance(s, dict) else s}"
            for i, s in enumerate(ctx["revenue_flow"])
        )
        parts.append(f"Provided revenue flow:\n{flow_str}")
    else:
        parts.append(
            "No explicit revenue flow provided — infer a plausible 4-6 step flow "
            "from the company description and sector. Add notes explaining inference."
        )

    if ctx["has_pricing_notes"]:
        notes_list = ctx["pricing_contract_notes"]
        if isinstance(notes_list, list):
            notes_str = "; ".join(str(n) for n in notes_list)
        else:
            notes_str = str(notes_list)
        parts.append(f"Pricing/contract notes (disclosed): {notes_str}")
    else:
        parts.append(
            "No pricing/contract notes disclosed — set pricing_contract_notes to empty list []."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    if ctx["notes"]:
        parts.append(f'Set notes to: "{ctx["notes"]}"')

    parts.append(
        "\nINSTRUCTIONS:\n"
        "- what_they_sell: 2-5 items describing products/services.\n"
        "- who_they_sell_to: 2-5 customer type descriptions.\n"
        "- revenue_flow: 4-6 FlowStep objects with step and optional note.\n"
        "- pricing_contract_notes: 0-3 items, ONLY if explicitly disclosed.\n"
        "- Do NOT fabricate pricing details."
    )

    return "\n".join(parts)
