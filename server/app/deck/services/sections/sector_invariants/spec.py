"""
SectionSpec definition for Sector Invariants.

Composes module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.sector_invariants.fallbacks import (
    any_module_low_confidence,
)
from app.deck.services.sections.sector_invariants.gating import (
    choose_included_modules,
    classify_sector,
)
from app.deck.services.sections.sector_invariants.modules import (
    revenue_quality_gtm as rq_gtm_mod,
    platform_dependencies_risk as pd_risk_mod,
    security_reliability as sec_mod,
)
from app.deck.services.sections.sector_invariants.render import render_to_slides
from app.deck.services.sections.sector_invariants.schemas import (
    SectorInvariantsOutput,
    get_sector_invariants_json_schema,
    get_sector_invariants_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (keyed by ModuleId) ──────────────────────────────────────

_MODULE_MAP = {
    "revenue_quality_gtm": rq_gtm_mod,
    "platform_dependencies_risk": pd_risk_mod,
    "security_reliability": sec_mod,
}

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Sector Invariants
analysis. Respond with valid JSON ONLY — no markdown, no commentary, no code
fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. Output ONLY the modules listed in included_modules. Do NOT add extra modules.
2. Do NOT fabricate KPI values, partner dependencies, security posture, or any metrics.
3. If a KPI value is missing, set value to null and do NOT reference it numerically in bullets.
4. If an area is unknown, note "not disclosed in inputs" in the module notes field, NOT in bullets.
5. failure_modes: include ONLY risks supported by the provided data. Do NOT invent risk scenarios.
6. Each module must have 2–6 bullets, 0–8 KPIs, 0–4 failure_modes.
7. Set confidence per module: "high" = sourced data, "medium" = reasonable inference, "low" = speculative.
8. Set low_confidence_flag = true if ANY module confidence is "low".
9. Tone: neutral, factual, institutional. No hype, no marketing language.
10. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from gating results and module fragments.
    """
    company = inputs.get("company") or {}
    sector_class = classify_sector(company)
    included = choose_included_modules(inputs)

    # If no modules qualify, build a prompt for a minimal empty output
    if not included:
        return _build_empty_prompt(sector_class)

    # Build per-module contexts and fragments
    fragments: list[str] = []
    for mod_id in included:
        mod = _MODULE_MAP.get(mod_id)
        if mod:
            ctx = mod.build_context(inputs)
            fragments.append(mod.build_prompt_fragment(ctx))

    included_json = json.dumps(included)

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_sector_invariants_json_schema_str(),
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

    parts.extend([
        "",
        f"## SECTOR CLASS: {sector_class}",
        f"## INCLUDED MODULES (output ONLY these): {included_json}",
        "",
    ])
    parts.extend(fragments)
    parts.append(
        "\nRespond with the JSON object only. No extra text before or after."
    )

    return "\n\n".join(parts)


def _build_empty_prompt(sector_class: str) -> str:
    """Build a prompt that yields a minimal output when no modules qualify."""
    return f"""{_SYSTEM_PREAMBLE}

## OUTPUT JSON SCHEMA
{get_sector_invariants_json_schema_str()}

## SECTOR CLASS: {sector_class}
## INCLUDED MODULES: []

No modules have sufficient data. Return the following JSON exactly:
{{
  "sector_class": "{sector_class}",
  "included_modules": [],
  "modules": [],
  "low_confidence_flag": true,
  "notes": "Insufficient sector KPI disclosure in provided inputs."
}}

Respond with the JSON object only. No extra text before or after."""


# ── Postprocess ──────────────────────────────────────────────────────────────


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Transform the custom SectorInvariantsOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by the pipeline.
    """
    # Validate with Pydantic
    try:
        parsed = SectorInvariantsOutput.model_validate(content)
        out_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("SectorInvariantsOutput validation issue: %s", exc)
        out_dict = content if isinstance(content, dict) else {}

    # Recompute included_modules deterministically (trust gating, not model)
    gated_modules = choose_included_modules(inputs)
    model_modules = out_dict.get("included_modules", [])

    if set(model_modules) != set(gated_modules):
        logger.info(
            "Overriding model included_modules %s with gated %s",
            model_modules,
            gated_modules,
        )
        out_dict["included_modules"] = gated_modules
        # Drop modules not in gated set
        out_dict["modules"] = [
            m for m in out_dict.get("modules", [])
            if m.get("id") in gated_modules
        ]

    # Recompute sector_class deterministically
    company = inputs.get("company") or {}
    out_dict["sector_class"] = classify_sector(company)

    # Set low_confidence_flag
    modules_list = out_dict.get("modules", [])
    if not gated_modules or any_module_low_confidence(modules_list):
        out_dict["low_confidence_flag"] = True

    # Render to slides
    slides = render_to_slides(out_dict)

    verification_notes: list[str] = []
    if out_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited sector data available"
        )

    return {
        "section_id": "sector_invariants",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="sector_invariants",
    build_prompt=_build_prompt,
    schema=get_sector_invariants_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
