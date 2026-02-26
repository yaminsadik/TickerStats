"""SectionSpec definition for Catalysts & Timeline."""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.catalysts_timeline.render import render_to_slides
from app.deck.services.sections.catalysts_timeline.schemas import (
    CatalystsTimelineOutput,
    get_catalysts_timeline_json_schema,
    get_catalysts_timeline_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Catalysts & Timeline
section for a stock pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. Each catalyst must have a name. Timing, mechanism, and impact are optional but encouraged.
2. Order catalysts chronologically (nearest first).
3. NEVER fabricate specific dates or earnings numbers.
4. Timing should use quarter/half-year format (Q2 2025, H1 2025) when possible.
5. Mechanism: explain WHAT changes and WHY the market cares.
6. Confidence: "high" = user-provided catalysts, "medium" = partially provided, "low" = AI-generated.
7. Use concise, institutional phrasing.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt for catalysts."""
    ticker = inputs.get("ticker", "UNKNOWN")
    company_name = inputs.get("company_name", "Unknown Company")
    sector = inputs.get("sector", "Unknown Sector")
    fund_constraints = inputs.get("fund_constraints", {})
    data_trust_mode = inputs.get("data_trust_mode", "user_auto_fetch")
    position = inputs.get("position")
    user_catalysts = inputs.get("catalysts") or []  # list of dicts

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_catalysts_timeline_json_schema_str(),
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

    if user_catalysts:
        parts.append("\n## USER-PROVIDED CATALYSTS")
        for i, cat in enumerate(user_catalysts, 1):
            entry = f"{i}. {cat.get('name', 'Unnamed')}"
            if cat.get("timing_window"):
                entry += f" [{cat['timing_window']}]"
            parts.append(entry)
            if cat.get("mechanism"):
                parts.append(f"   Mechanism: {cat['mechanism']}")
            if cat.get("evidence"):
                parts.append(f"   Evidence: {cat['evidence']}")
        parts.append(
            "\nRefine and structure the user's catalysts. You may add timing "
            "precision or mechanism detail, but do NOT remove or contradict "
            "user-provided catalysts."
        )
    else:
        parts.append(
            "\n## INSTRUCTIONS\n"
            "No user catalysts provided. Identify 3-5 plausible near-term and "
            "medium-term catalysts for this company based on public knowledge. "
            "Mark confidence as 'low'."
        )

    parts.append("\nRespond with the JSON object only. No extra text.")
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform CatalystsTimelineOutput into standard {section_id, slides[]}."""
    try:
        parsed = CatalystsTimelineOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("CatalystsTimelineOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("confidence") == "low":
        verification_notes.append("Low confidence — catalysts were AI-generated, not user-provided")

    return {
        "section_id": "catalysts_timeline",
        "slides": slides,
        "needs_verification": output_dict.get("confidence") == "low",
        "verification_notes": verification_notes,
    }


SECTION_SPEC = SectionSpec(
    id="catalysts_timeline",
    build_prompt=_build_prompt,
    schema=get_catalysts_timeline_json_schema(),
    required_context={"ticker", "fund_constraints"},
    postprocess=_postprocess,
)
