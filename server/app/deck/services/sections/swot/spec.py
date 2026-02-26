"""
SectionSpec definition for SWOT.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.swot.render import render_to_slides
from app.deck.services.sections.swot.schemas import (
    get_swot_json_schema,
    SWOTOutput,
    get_swot_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a SWOT Analysis
for an investment pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. Strengths & Weaknesses: INTERNAL factors (advantages, capabilities, gaps, challenges).
2. Opportunities & Threats: EXTERNAL factors (market trends, competition, regulations, macro).
3. Include 2-4 items in each SWOT category.
4. Each item must have: point (concise statement) + justification (why it matters for investment).
5. Confidence: "high" = well-known facts, "medium" = reasonable inference, "low" = speculative.
6. Do NOT include URLs or citations in any field.
7. Use concise, institutional phrasing throughout.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt."""
    ticker = inputs.get("ticker", "UNKNOWN")
    company_name = inputs.get("company_name", "Unknown Company")
    sector = inputs.get("sector", "Unknown Sector")
    fund_constraints = inputs.get("fund_constraints", {})
    comps_summary = inputs.get("comps_summary", "")
    dcf_summary = inputs.get("dcf_summary", "")
    
    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_swot_json_schema_str(),
        "",
        _HARD_RULES,
    ]

    # Inject data trust + position framing
    data_trust_mode = inputs.get("data_trust_mode")
    if data_trust_mode:
        parts.append(get_data_trust_instructions(data_trust_mode))
    position = inputs.get("position")
    if position:
        parts.append(get_position_framing(position))

    parts.extend([
        "",
        f"## COMPANY CONTEXT",
        f"Ticker: {ticker}",
        f"Company: {company_name}",
        f"Sector: {sector}",
        f"Fund Style: {fund_constraints.get('style', 'Student investment fund pitch')}",
        f"Time Horizon: {fund_constraints.get('time_horizon', '12-24 months')}",
        f"Risk Profile: {fund_constraints.get('risk_profile', 'Moderate')}",
    ])
    
    if comps_summary:
        parts.append(f"\n## COMPARABLES DATA\n{comps_summary}")
    
    if dcf_summary:
        parts.append(f"\n## DCF VALUATION\n{dcf_summary}")

    # Inject user-provided risks
    risks = inputs.get("risks")
    if risks:
        risk_lines = ["## USER-PROVIDED RISKS (incorporate into Threats analysis)"]
        for r in risks:
            line = f"- {r.get('risk', '')}"
            if r.get("leading_indicator"):
                line += f" | Leading indicator: {r['leading_indicator']}"
            if r.get("mitigant"):
                line += f" | Mitigant: {r['mitigant']}"
            risk_lines.append(line)
        parts.append("\n".join(risk_lines))

    parts.append(
        "\n## INSTRUCTIONS\n"
        "- strengths: 2-4 internal competitive advantages (moat, capabilities).\n"
        "- weaknesses: 2-4 internal challenges (operational gaps, structural issues).\n"
        "- opportunities: 2-4 external favorable conditions (market growth, expansion).\n"
        "- threats: 2-4 external risks (competition, regulation, macro headwinds).\n"
        "- Each item: point (1 sentence) + justification (why it matters).\n"
        "\nRespond with the JSON object only. No extra text before or after."
    )
    
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform SWOTOutput into standard {section_id, slides[]}."""
    try:
        parsed = SWOTOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("SWOTOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}
    
    # Convert to slides
    slides = render_to_slides(output_dict)
    
    return {
        "section_id": "swot",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": [],
    }


SECTION_SPEC = SectionSpec(
    id="swot",
    build_prompt=_build_prompt,
    schema=get_swot_json_schema(),
    required_context={"ticker", "fund_constraints"},
    postprocess=_postprocess,
)
