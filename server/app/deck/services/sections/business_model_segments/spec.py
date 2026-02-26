"""
SectionSpec definition for Business Model & Segments.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.business_model_segments.fallbacks import (
    compute_low_confidence_flag,
)
from app.deck.services.sections.business_model_segments.modules import (
    business_model as business_model_mod,
    segments as segments_mod,
    unit_economics as unit_economics_mod,
)
from app.deck.services.sections.business_model_segments.render import (
    render_to_slides,
)
from app.deck.services.sections.business_model_segments.schemas import (
    BusinessModelSegmentsOutput,
    get_business_model_segments_json_schema,
    get_business_model_segments_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    business_model_mod,
    segments_mod,
    unit_economics_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Business Model &
Segments analysis for a pitch deck. Respond with valid JSON ONLY — no markdown,
no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Business model module: ONLY what they sell, who they sell to, revenue generation flow, and pricing/contract notes (if disclosed). NO segment mix %, NO unit economics metrics.
2. Segments module: ONLY segments, revenue/profit mix %, one-liner, and drivers. NO pricing flow, NO customer type lists, NO unit economics.
3. Unit economics module: ONLY disclosed metrics panel. NO narrative moat claims, NO invented values.
4. NEVER fabricate numbers — segment mix, margins, CAC, LTV, churn, ARPU, etc. Use null when a value is not provided.
5. If data is missing, follow the tier/fallback instructions per module.
6. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative or inferred.
7. Set low_confidence_flag = true if ANY module confidence == "low" OR segments.mode == "tier_c".
8. Use concise, institutional phrasing throughout. No marketing language.
9. Do NOT include URLs or citations in any field.
10. revenue_flow must have exactly 4-6 FlowStep items.
11. Each segment must have exactly 2-4 drivers.
12. pricing_contract_notes must be empty [] if not explicitly disclosed.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator.  Expected keys include
        ``ticker``, ``company_name``, ``sector``, ``business_model``,
        ``segments``, ``unit_economics``, and optionally
        ``company_description``.
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
        get_business_model_segments_json_schema_str(),
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

    # Inject user-provided segment mix data
    data_blocks = inputs.get("data_blocks") or {}
    if data_blocks.get("segment_mix"):
        parts.append(
            "## USER-PROVIDED SEGMENT MIX (use as primary data source)\n"
            + data_blocks["segment_mix"]
        )
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
    Transform the custom BusinessModelSegmentsOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by the pipeline.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = BusinessModelSegmentsOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("BusinessModelSegmentsOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    # Compute / confirm low_confidence_flag deterministically
    bm_conf = output_dict.get("business_model", {}).get("confidence", "medium")
    seg_conf = output_dict.get("segments", {}).get("confidence", "medium")
    ue_conf = output_dict.get("unit_economics", {}).get("confidence", "medium")
    seg_mode = output_dict.get("segments", {}).get("mode", "tier_c")

    output_dict["low_confidence_flag"] = compute_low_confidence_flag(
        bm_conf, seg_conf, ue_conf, seg_mode
    )

    # Convert to slides
    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited data available for one or more modules"
        )

    return {
        "section_id": "business_model_segments",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="business_model_segments",
    build_prompt=_build_prompt,
    schema=get_business_model_segments_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
