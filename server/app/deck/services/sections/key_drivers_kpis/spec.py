"""
SectionSpec definition for Key Drivers & KPIs.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.key_drivers_kpis.fallbacks import (
    compute_confidence,
    compute_low_confidence_flag,
)
from app.deck.services.sections.key_drivers_kpis.modules import (
    kpi_selection as kpi_selection_mod,
    kpi_definitions as kpi_definitions_mod,
    disclosure_locations as disclosure_locations_mod,
)
from app.deck.services.sections.key_drivers_kpis.render import render_to_slides
from app.deck.services.sections.key_drivers_kpis.schemas import (
    KeyDriversKpisOutput,
    get_key_drivers_kpis_json_schema,
    get_key_drivers_kpis_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    kpi_selection_mod,
    kpi_definitions_mod,
    disclosure_locations_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Key Drivers & KPIs
slide for a pitch deck. Respond with valid JSON ONLY — no markdown, no
commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Select 3-5 KPIs that actually drive value in this business. If fewer than 3 are available, use what exists.
2. Prefer operational drivers over accounting outcomes (ARPU, churn, utilization, same-store sales, backlog, NRR, units shipped, take-rate, AUM, NIM, LTV/CAC, etc.) — depends on sector.
3. Avoid "revenue" as a KPI unless the business is purely volume-driven and revenue is explicitly the primary driver.
4. NEVER fabricate KPIs, definitions, or filing locations. Only use data from the inputs.
5. If filing locations are not provided, set disclosure.source_type to "not_provided" and all other disclosure fields to null. Do NOT guess.
6. Each "why_it_moves_value" must be exactly 1 sentence: causal and specific.
7. Each "definition" must be 1-2 sentences: operational definition.
8. Set confidence to "high" if 3+ KPIs with disclosure, "medium" if 3+ without full disclosure, "low" if <3 KPIs.
9. Set low_confidence_flag to true if confidence == "low" OR any disclosure.source_type == "not_provided".
10. Provide 1-3 overall_takeaways: concise investor-relevant observations about the KPI set.
11. Use concise, institutional phrasing throughout. No marketing language.
12. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator. Should include
        ``ticker``, ``company_name``, ``sector``, and optionally ``kpis``,
        ``key_metrics``, ``business_model_segments``, ``disclosures``,
        ``filings``, etc.
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
        get_key_drivers_kpis_json_schema_str(),
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

    # Inject user-provided KPI data
    data_blocks = inputs.get("data_blocks") or {}
    if data_blocks.get("kpi_table"):
        parts.append(
            "## USER-PROVIDED KPI TABLE (use as primary data source)\n"
            + data_blocks["kpi_table"]
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
    Transform the custom KeyDriversKpisOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by ``_transform_section_response``.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = KeyDriversKpisOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("KeyDriversKpisOutput validation issue: %s", exc)
        # Fall through with raw dict so the pipeline can still produce slides
        output_dict = content if isinstance(content, dict) else {}

    # Recompute confidence and low_confidence_flag deterministically
    kpis = output_dict.get("kpis", [])
    any_missing = any(
        (kpi.get("disclosure") or {}).get("source_type") == "not_provided"
        for kpi in kpis
    )
    confidence = compute_confidence(len(kpis), any_missing)
    output_dict["confidence"] = confidence
    output_dict["low_confidence_flag"] = compute_low_confidence_flag(
        confidence, kpis
    )

    # Convert to slides
    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited KPI disclosure in inputs"
        )

    return {
        "section_id": "key_drivers_kpis",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="key_drivers_kpis",
    build_prompt=_build_prompt,
    schema=get_key_drivers_kpis_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
