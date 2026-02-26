"""
SectionSpec definition for Company Snapshot.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.company_snapshot.fallbacks import (
    any_module_low_confidence,
)
from app.deck.services.sections.company_snapshot.modules import (
    header as header_mod,
    positioning as positioning_mod,
    segments as segments_mod,
    money_model as money_model_mod,
    customers as customers_mod,
    footprint as footprint_mod,
    proof_points as proof_points_mod,
    quick_stats as quick_stats_mod,
)
from app.deck.services.sections.company_snapshot.render import render_to_slides
from app.deck.services.sections.company_snapshot.schemas import (
    CompanySnapshotOutput,
    get_company_snapshot_json_schema,
    get_company_snapshot_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    header_mod,
    quick_stats_mod,
    positioning_mod,
    segments_mod,
    money_model_mod,
    customers_mod,
    footprint_mod,
    proof_points_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Company Snapshot
slide for a pitch deck. Respond with valid JSON ONLY — no markdown, no
commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Positioning module: ONLY positioning sentence + 3-6 qualitative bullets. NO metrics.
2. Segments module: ONLY segments and mix (or narrative). No customers, footprint, or KPIs.
3. Money model: ONLY pricing unit, contract structure, recurrence, cost drivers. No segment mix, no KPIs.
4. Customers: ONLY customer types, concentration, credit quality.
5. Footprint: ONLY geography and optional "why it matters" single bullet.
6. Proof points: ONLY operational KPIs. No margins, EPS, growth rates, valuation multiples.
7. Quick stats: max 6 items. Use the pre-computed values exactly — do NOT invent figures.
8. Confidence: set per module as instructed. "high" = sourced data, "medium" = reasonable inference, "low" = speculative.
9. Set header.low_confidence_flag = true if ANY module confidence == "low".
10. Use concise, institutional phrasing throughout. No marketing language.
11. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator.  For company_snapshot,
        the caller should include ``company``, ``financials``, ``segments``,
        ``customers``, ``footprint``, ``proof_points``, and optionally
        ``money_model`` and ``sources`` keys.  Standard keys (``ticker``,
        ``company_name``, ``sector``) are also accepted as top-level
        fallbacks.
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
        get_company_snapshot_json_schema_str(),
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
    Transform the custom CompanySnapshotOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by ``_transform_section_response``.

    This is called by the orchestrator *before* ``_transform_section_response``.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = CompanySnapshotOutput.model_validate(content)
        snapshot_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("CompanySnapshotOutput validation issue: %s", exc)
        # Fall through with raw dict so the pipeline can still produce slides
        snapshot_dict = content if isinstance(content, dict) else {}

    # Determine low_confidence_flag from module confidences
    modules = snapshot_dict.get("modules", {})
    if any_module_low_confidence(modules):
        snapshot_dict.setdefault("header", {})["low_confidence_flag"] = True

    # Convert to slides
    slides = render_to_slides(snapshot_dict)

    verification_notes: list[str] = []
    header = snapshot_dict.get("header", {})
    if header.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited data available for one or more modules"
        )

    return {
        "section_id": "company_snapshot",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="company_snapshot",
    build_prompt=_build_prompt,
    schema=get_company_snapshot_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
