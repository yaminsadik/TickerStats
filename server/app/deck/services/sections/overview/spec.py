"""
SectionSpec definition for Overview.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.overview.fallbacks import compute_low_confidence_flag
from app.deck.services.sections.overview.render import render_to_slides
from app.deck.services.sections.overview.schemas import (
    get_overview_json_schema,
    OverviewOutput,
    get_overview_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Company Overview
section for an investment pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. Business description: ONLY core value prop, what they do, who they serve. NO catalysts.
2. Why now: ONLY timing thesis and factors. NO business description, NO specific catalysts.
3. Catalysts: ONLY near-term and medium-term catalysts. NO general market trends.
4. NEVER fabricate numbers — revenue, market size, growth rates, etc. Use null when not provided.
5. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative.
6. Set low_confidence_flag = true if ANY module confidence == "low".
7. Use concise, institutional phrasing throughout. No marketing language.
8. Do NOT include URLs or citations in any field.
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
        get_overview_json_schema_str(),
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
    
    portfolio_context = fund_constraints.get('portfolio_context')
    if portfolio_context:
        parts.append(f"Portfolio Context: {portfolio_context}")
    
    if comps_summary:
        parts.append(f"\n## COMPARABLES DATA\n{comps_summary}")
    
    if dcf_summary:
        parts.append(f"\n## DCF VALUATION\n{dcf_summary}")

    # Inject user-provided thesis context
    thesis = inputs.get("thesis")
    if thesis:
        thesis_lines = ["## USER-PROVIDED THESIS (use for 'why now' context)"]
        if thesis.get("thesis_sentence"):
            thesis_lines.append(f"Thesis: {thesis['thesis_sentence']}")
        if thesis.get("market_believes"):
            thesis_lines.append(f"Market believes: {thesis['market_believes']}")
        if thesis.get("we_believe"):
            thesis_lines.append(f"We believe: {thesis['we_believe']}")
        for p in (thesis.get("pillars") or []):
            thesis_lines.append(f"- Pillar: {p}")
        parts.append("\n".join(thesis_lines))

    # Inject user-provided catalysts
    user_catalysts = inputs.get("catalysts")
    if user_catalysts:
        cat_lines = ["## USER-PROVIDED CATALYSTS (incorporate into catalysts module)"]
        for c in user_catalysts:
            line = f"- {c.get('name', '')}"
            if c.get("timing_window"):
                line += f" [{c['timing_window']}]"
            if c.get("mechanism"):
                line += f" -- {c['mechanism']}"
            cat_lines.append(line)
        parts.append("\n".join(cat_lines))

    parts.append(
        "\n## INSTRUCTIONS\n"
        "- business_description.core_value_proposition: One sentence describing what makes this company unique.\n"
        "- business_description.what_they_do: 2-4 bullet descriptions of products/services.\n"
        "- business_description.who_they_serve: 1-3 bullet descriptions of customer segments.\n"
        "- why_now.thesis_statement: One sentence explaining why this is the right time to invest.\n"
        "- why_now.timing_factors: 2-4 bullets explaining market timing, trends, inflection points.\n"
        "- catalysts.near_term: 2-4 catalysts expected in next 6-12 months.\n"
        "- catalysts.medium_term: 0-3 catalysts expected in 12-24 months.\n"
        "\nRespond with the JSON object only. No extra text before or after."
    )
    
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform OverviewOutput into standard {section_id, slides[]}."""
    try:
        parsed = OverviewOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("OverviewOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}
    
    # Recompute low_confidence_flag
    biz_conf = output_dict.get("business_description", {}).get("confidence", "low")
    why_conf = output_dict.get("why_now", {}).get("confidence", "low")
    cat_conf = output_dict.get("catalysts", {}).get("confidence", "low")
    
    output_dict["low_confidence_flag"] = compute_low_confidence_flag(
        biz_conf, why_conf, cat_conf
    )
    
    # Convert to slides
    slides = render_to_slides(output_dict)
    
    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append("Low confidence — limited data available for one or more modules")
    
    return {
        "section_id": "overview",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


SECTION_SPEC = SectionSpec(
    id="overview",
    build_prompt=_build_prompt,
    schema=get_overview_json_schema(),
    required_context={"ticker", "fund_constraints"},
    postprocess=_postprocess,
)
