"""
SectionSpec definition for Industry & Competitive Landscape.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.industry_competitive_landscape.fallbacks import (
    compute_low_confidence_flag,
    strip_fabricated_values,
)
from app.deck.services.sections.industry_competitive_landscape.modules import (
    market as market_mod,
    competition as competition_mod,
    moat as moat_mod,
    porters as porters_mod,
)
from app.deck.services.sections.industry_competitive_landscape.render import (
    render_to_slides,
)
from app.deck.services.sections.industry_competitive_landscape.schemas import (
    get_industry_competitive_json_schema,
    IndustryCompetitiveOutput,
    get_industry_competitive_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    market_mod,
    competition_mod,
    moat_mod,
    porters_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating an Industry &
Competitive Landscape analysis for a pitch deck. Respond with valid JSON
ONLY — no markdown, no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Market module: ONLY market definition, sizing, and growth drivers. NO moat claims, NO competitor ranking.
2. Competition module: ONLY competitive set + positioning. NO TAM numbers unless already provided.
3. Moat module: ONLY moat drivers with mechanism + evidence. NO valuation talk, NO hype language.
4. Porter's module: EXACTLY 5 forces. Pressures justified with 1–2 grounded bullets. NO invented metrics.
5. Never fabricate numbers (TAM, share, CAGR, competitor counts). Use disclosed metrics only or omit.
6. Moat drivers must be stated neutrally (mechanism + evidence), no hype language or superlatives.
7. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative.
8. Set low_confidence_flag = true if ANY module confidence == "low".
9. Use concise, institutional phrasing throughout. No marketing language.
10. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator.  Standard keys
        (``ticker``, ``company_name``, ``sector``) are accepted as
        top-level fallbacks.
    """
    # Build per-module contexts
    contexts = []
    for mod in _MODULES:
        ctx = mod.build_context(inputs)
        contexts.append((mod, ctx))

    # Compose prompt
    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_industry_competitive_json_schema_str(),
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

    # Inject user-provided filing excerpts if available
    data_blocks = inputs.get("data_blocks") or {}
    if data_blocks.get("filing_excerpts"):
        parts.append(
            "## USER-PROVIDED FILING EXCERPTS\n"
            + data_blocks["filing_excerpts"]
        )

    for mod, ctx in contexts:
        fragment = mod.build_prompt_fragment(ctx)
        parts.append(fragment)

    parts.append(
        "\nRespond with the JSON object only. No extra text before or after."
    )

    return "\n\n".join(parts)


# ── Postprocess ──────────────────────────────────────────────────────────────


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Transform the custom IndustryCompetitiveOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by ``_transform_section_response``.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = IndustryCompetitiveOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("IndustryCompetitiveOutput validation issue: %s", exc)
        # Fall through with raw dict so the pipeline can still produce slides
        output_dict = content if isinstance(content, dict) else {}

    # Strip fabricated values
    output_dict = strip_fabricated_values(output_dict)

    # Deterministically compute low_confidence_flag
    output_dict["low_confidence_flag"] = compute_low_confidence_flag(output_dict)

    # Convert to slides
    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited data available for one or more modules"
        )

    return {
        "section_id": "industry_competitive_landscape",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="industry_competitive_landscape",
    build_prompt=_build_prompt,
    schema=get_industry_competitive_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
