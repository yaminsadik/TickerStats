"""SectionSpec definition for Valuation."""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.valuation.render import render_to_slides
from app.deck.services.sections.valuation.schemas import (
    ValuationOutput,
    get_valuation_json_schema,
    get_valuation_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Valuation section
for a stock pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. methodology_summary: ONE sentence describing the overall valuation approach.
2. valuation_points: 1-6 entries, one per valuation method used.
3. CRITICAL: Do NOT invent valuation inputs (multiples, WACC, growth rates).
   Only use numbers explicitly provided by the user or computed data below.
4. If user provided a price target, include it in price_target_summary.
5. If no user data for a method, describe the approach qualitatively without numbers.
6. Confidence: "high" = user provided full assumptions, "medium" = partial, "low" = qualitative only.
7. Use concise, institutional phrasing. No marketing language.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt for valuation."""
    ticker = inputs.get("ticker", "UNKNOWN")
    company_name = inputs.get("company_name", "Unknown Company")
    sector = inputs.get("sector", "Unknown Sector")
    fund_constraints = inputs.get("fund_constraints", {})
    data_trust_mode = inputs.get("data_trust_mode", "user_auto_fetch")
    position = inputs.get("position")
    valuation = inputs.get("valuation")  # dict or None
    comps_summary = inputs.get("comps_summary", "")
    dcf_summary = inputs.get("dcf_summary", "")

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_valuation_json_schema_str(),
        "",
        get_data_trust_instructions(data_trust_mode),
        "",
        _HARD_RULES,
    ]

    position_framing = get_position_framing(position)
    if position_framing:
        parts.append(position_framing)

    parts.extend([
        "",
        "## COMPANY CONTEXT",
        f"Ticker: {ticker}",
        f"Company: {company_name}",
        f"Sector: {sector}",
        f"Time Horizon: {fund_constraints.get('time_horizon', '12-24 months')}",
        f"Risk Profile: {fund_constraints.get('risk_profile', 'Moderate')}",
    ])

    # Inject computed data
    if comps_summary:
        parts.append(f"\n## COMPARABLES DATA\n{comps_summary}")
    if dcf_summary:
        parts.append(f"\n## DCF VALUATION\n{dcf_summary}")

    # Inject user valuation input
    if valuation:
        parts.append("\n## USER-PROVIDED VALUATION INPUTS")
        methods = valuation.get("methods") or []
        if methods:
            parts.append(f"Selected methods: {', '.join(methods)}")
        peers = valuation.get("peer_tickers") or []
        if peers:
            parts.append(f"Peer tickers: {', '.join(peers)}")
        tmr = valuation.get("target_multiple_range")
        if tmr:
            parts.append(f"Target multiple range: {tmr}")
        dcf_assumptions = valuation.get("dcf_assumptions")
        if dcf_assumptions:
            parts.append(f"DCF assumptions: {dcf_assumptions}")
        pt = valuation.get("price_target")
        if pt:
            parts.append(f"User price target: {pt}")
        parts.append(
            "\nUse ONLY these user-provided inputs and the computed data above. "
            "Do NOT invent additional valuation assumptions."
        )
    else:
        parts.append(
            "\n## INSTRUCTIONS\n"
            "No user valuation inputs provided. Suggest a qualitative valuation "
            "framework appropriate for this company and sector. Do NOT invent "
            "specific multiples or assumptions. Mark confidence as 'low'."
        )

    parts.append("\nRespond with the JSON object only. No extra text.")
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform ValuationOutput into standard {section_id, slides[]}."""
    try:
        parsed = ValuationOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("ValuationOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("confidence") == "low":
        verification_notes.append("Low confidence — valuation is qualitative, no user assumptions provided")

    return {
        "section_id": "valuation",
        "slides": slides,
        "needs_verification": True,  # Valuation always warrants verification
        "verification_notes": verification_notes,
    }


SECTION_SPEC = SectionSpec(
    id="valuation",
    build_prompt=_build_prompt,
    schema=get_valuation_json_schema(),
    required_context={"ticker", "fund_constraints"},
    postprocess=_postprocess,
)
