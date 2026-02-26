"""SectionSpec definition for Investment Thesis & Variant View."""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.investment_thesis.render import render_to_slides
from app.deck.services.sections.investment_thesis.schemas import (
    InvestmentThesisOutput,
    get_investment_thesis_json_schema,
    get_investment_thesis_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating an Investment Thesis
section for a stock pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. thesis_sentence: ONE sentence explaining the core thesis.
2. market_view: What the consensus believes about this stock.
3. variant_view: The contrarian take — why the market is wrong.
4. pillars: 2-5 concise supporting arguments for the thesis.
5. what_changes_mind: 1-2 conditions that would invalidate the thesis.
6. NEVER fabricate numbers. Use null when not provided.
7. Confidence: "high" = user provided full thesis, "medium" = partial, "low" = generated.
8. Use concise, institutional phrasing. No marketing language.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt for investment thesis."""
    ticker = inputs.get("ticker", "UNKNOWN")
    company_name = inputs.get("company_name", "Unknown Company")
    sector = inputs.get("sector", "Unknown Sector")
    fund_constraints = inputs.get("fund_constraints", {})
    data_trust_mode = inputs.get("data_trust_mode", "user_auto_fetch")
    position = inputs.get("position")
    thesis = inputs.get("thesis")  # dict or None

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_investment_thesis_json_schema_str(),
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

    # Inject user thesis if provided
    if thesis:
        parts.append("\n## USER-PROVIDED THESIS")
        if thesis.get("thesis_sentence"):
            parts.append(f"Thesis: {thesis['thesis_sentence']}")
        if thesis.get("market_believes"):
            parts.append(f"Market believes: {thesis['market_believes']}")
        if thesis.get("we_believe"):
            parts.append(f"We believe: {thesis['we_believe']}")
        pillars = thesis.get("pillars") or []
        if pillars:
            parts.append("Thesis pillars:")
            for i, p in enumerate(pillars, 1):
                parts.append(f"  {i}. {p}")
        wcm = thesis.get("what_changes_mind") or []
        if wcm:
            parts.append("What would change my mind:")
            for item in wcm:
                parts.append(f"  - {item}")
        parts.append(
            "\nStructure and polish the user's thesis. Do NOT replace or contradict "
            "the user's view — only refine the framing for an investment committee."
        )
    else:
        parts.append(
            "\n## INSTRUCTIONS\n"
            "No user thesis was provided. Generate a plausible thesis framework "
            "for this company based on public knowledge. Mark confidence as 'low'."
        )

    parts.append("\nRespond with the JSON object only. No extra text.")
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform InvestmentThesisOutput into standard {section_id, slides[]}."""
    try:
        parsed = InvestmentThesisOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("InvestmentThesisOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("confidence") == "low":
        verification_notes.append("Low confidence — thesis was AI-generated, not user-provided")

    return {
        "section_id": "investment_thesis",
        "slides": slides,
        "needs_verification": output_dict.get("confidence") == "low",
        "verification_notes": verification_notes,
    }


SECTION_SPEC = SectionSpec(
    id="investment_thesis",
    build_prompt=_build_prompt,
    schema=get_investment_thesis_json_schema(),
    required_context={"ticker", "fund_constraints"},
    postprocess=_postprocess,
)
