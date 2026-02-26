"""
SectionSpec definition for Management, Ownership & Governance.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.management_ownership_governance.fallbacks import (
    compute_low_confidence_flag,
    resolve_governance,
    resolve_management,
    resolve_ownership,
)
from app.deck.services.sections.management_ownership_governance.modules import (
    management as management_mod,
    ownership as ownership_mod,
    governance as governance_mod,
)
from app.deck.services.sections.management_ownership_governance.render import (
    render_to_slides,
)
from app.deck.services.sections.management_ownership_governance.schemas import (
    ManagementOwnershipGovernanceOutput,
    get_mog_json_schema,
    get_mog_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    management_mod,
    ownership_mod,
    governance_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Management,
Ownership & Governance analysis for a pitch deck. Respond with valid JSON
ONLY — no markdown, no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Management module: ONLY people + incentives + alignment. No ownership stakes from institutions, no governance flags.
2. Ownership module: ONLY holders + stakes + activist status. No management details, no governance flags.
3. Governance module: ONLY governance structure and flags. No management track record, no ownership data.
4. Never fabricate names, percentages, compensation numbers, or governance facts. Use ONLY provided inputs.
5. If data is missing: omit the field (set null) and downgrade confidence.
6. Governance flags must be stated neutrally: fact + why it matters. No accusations, no "fraud" language.
7. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative/missing.
8. Set low_confidence_flag = true if management.confidence == "low" OR ownership.confidence == "low" OR (governance.flags empty AND ownership.top_holders empty).
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
        get_mog_json_schema_str(),
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

    # Inject user-provided ownership/governance data
    data_blocks = inputs.get("data_blocks") or {}
    if data_blocks.get("ownership_notes"):
        parts.append(
            "## USER-PROVIDED OWNERSHIP NOTES (use as primary data source)\n"
            + data_blocks["ownership_notes"]
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
    Transform the custom ManagementOwnershipGovernanceOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by ``_transform_section_response``.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = ManagementOwnershipGovernanceOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning(
            "ManagementOwnershipGovernanceOutput validation issue: %s", exc
        )
        # Fall through with raw dict so the pipeline can still produce slides
        output_dict = content if isinstance(content, dict) else {}

    # Apply deterministic fallbacks
    if "management" in output_dict:
        output_dict["management"] = resolve_management(output_dict["management"])
    if "ownership" in output_dict:
        output_dict["ownership"] = resolve_ownership(output_dict["ownership"])
    if "governance" in output_dict:
        output_dict["governance"] = resolve_governance(output_dict["governance"])

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
        "section_id": "management_ownership_governance",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="management_ownership_governance",
    build_prompt=_build_prompt,
    schema=get_mog_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
