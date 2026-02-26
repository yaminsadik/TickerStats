"""
SectionSpec definition for History.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.history.render import render_to_slides
from app.deck.services.sections.history.schemas import (
    get_history_json_schema,
    HistoryOutput,
    get_history_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Company History
timeline for an investment pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

CRITICAL: This section is a DRAFT that requires verification. All dates, events,
and facts MUST be reviewed by the team before presentation.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. Include 4-8 key milestones spanning company history.
2. Prefer general timeframes ("early 2010s") over specific dates you're uncertain about.
3. Mark ALL milestones with needs_verification: true.
4. Include verification_items list with specific things to verify (e.g., "IPO date", "acquisition price").
5. Focus on: founding, IPO, major acquisitions, leadership changes, strategic pivots, recent events.
6. Each milestone must include why_it_matters explaining significance.
7. Confidence: "medium" = reasonable inference from public info, "low" = speculative.
8. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt."""
    ticker = inputs.get("ticker", "UNKNOWN")
    company_name = inputs.get("company_name", "Unknown Company")
    sector = inputs.get("sector", "Unknown Sector")
    fund_constraints = inputs.get("fund_constraints", {})
    
    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_history_json_schema_str(),
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
        "",
        "## INSTRUCTIONS",
        "- milestones: 4-8 chronological milestones (founding → present).",
        "- For each milestone: year (or timeframe), event description, why_it_matters.",
        "- verification_items: List specific items to verify (at least 1).",
        "- Set confidence to 'medium' if you can infer from sector knowledge, 'low' otherwise.",
        "\nRespond with the JSON object only. No extra text before or after."
    ])
    
    return "\n\n".join(parts)


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """Transform HistoryOutput into standard {section_id, slides[]}."""
    try:
        parsed = HistoryOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("HistoryOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}
    
    # Convert to slides
    slides = render_to_slides(output_dict)
    
    verification_items = output_dict.get("verification_items", [])
    
    return {
        "section_id": "history",
        "slides": slides,
        "needs_verification": True,
        "verification_notes": verification_items,
    }


SECTION_SPEC = SectionSpec(
    id="history",
    build_prompt=_build_prompt,
    schema=get_history_json_schema(),
    required_context={"ticker", "company_name", "sector"},
    postprocess=_postprocess,
)
