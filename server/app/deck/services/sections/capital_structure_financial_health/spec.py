"""
SectionSpec definition for Capital Structure & Financial Health.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    compute_low_confidence_flag,
)
from app.deck.services.sections.capital_structure_financial_health.modules import (
    leverage_interest as leverage_interest_mod,
    maturities as maturities_mod,
    liquidity as liquidity_mod,
    share_count as share_count_mod,
)
from app.deck.services.sections.capital_structure_financial_health.render import (
    render_to_slides,
)
from app.deck.services.sections.capital_structure_financial_health.schemas import (
    CapitalStructureFinancialHealthOutput,
    get_csfh_json_schema,
    get_csfh_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    leverage_interest_mod,
    maturities_mod,
    liquidity_mod,
    share_count_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Capital
Structure & Financial Health analysis for a pitch deck. Respond with valid
JSON ONLY — no markdown, no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Leverage & Interest module: ONLY leverage + interest burden. NO maturities, NO liquidity, NO share count.
2. Maturities module: ONLY maturity ladder + covenants. NO leverage, NO liquidity, NO share count.
3. Liquidity module: ONLY cash/liquidity/runway. NO leverage, NO maturities, NO share count.
4. Share Count module: ONLY dilution/buybacks/dividends/SBC. NO leverage, NO maturities, NO liquidity.
5. NEVER fabricate numbers, maturities, covenant levels, or runway — use null when not provided.
6. Do NOT compute runway unless burn rate (FCF or cash burn) is provided as a number.
7. Covenants: ONLY include if explicitly provided. NEVER infer covenant thresholds.
8. If data is missing, follow the fallback instructions per module.
9. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative or data missing.
10. Use concise, institutional phrasing throughout. No marketing language.
11. Do NOT include URLs or citations in any field.
12. Series points must use only provided input values — never interpolate or extrapolate.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator.  Expected keys include
        ``ticker``, ``company_name``, ``leverage``, ``maturities``,
        ``liquidity``, ``shares``, etc.
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
        get_csfh_json_schema_str(),
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

    # Inject user-provided debt/constraint data
    data_blocks = inputs.get("data_blocks") or {}
    if data_blocks.get("debt_maturities"):
        parts.append(
            "## USER-PROVIDED DEBT MATURITIES (use as primary data source)\n"
            + data_blocks["debt_maturities"]
        )
    if data_blocks.get("filing_excerpts"):
        parts.append(
            "## USER-PROVIDED FILING EXCERPTS\n"
            + data_blocks["filing_excerpts"]
        )
    user_constraints = inputs.get("user_constraints") or {}
    constraint_lines = []
    if user_constraints.get("liquidity_floor"):
        constraint_lines.append(f"Liquidity floor: {user_constraints['liquidity_floor']}")
    if user_constraints.get("leverage_ceiling"):
        constraint_lines.append(f"Leverage ceiling: {user_constraints['leverage_ceiling']}")
    if constraint_lines:
        parts.append(
            "## PORTFOLIO CONSTRAINTS (flag if company breaches)\n"
            + "\n".join(constraint_lines)
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
    Transform the custom CapitalStructureFinancialHealthOutput into the
    standard ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by the pipeline.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = CapitalStructureFinancialHealthOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("CapitalStructureFinancialHealthOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    # Recompute low_confidence_flag deterministically
    lev_conf = output_dict.get("leverage_interest", {}).get("confidence", "low")
    mat_conf = output_dict.get("maturities", {}).get("confidence", "low")
    liq_conf = output_dict.get("liquidity", {}).get("confidence", "low")
    sc_conf = output_dict.get("share_count", {}).get("confidence", "low")

    ladder = output_dict.get("maturities", {}).get("ladder", [])
    lev_series = output_dict.get("leverage_interest", {}).get("leverage_series", [])

    output_dict["low_confidence_flag"] = compute_low_confidence_flag(
        leverage_confidence=lev_conf,
        maturities_confidence=mat_conf,
        liquidity_confidence=liq_conf,
        share_count_confidence=sc_conf,
        maturities_ladder_empty=len(ladder) == 0,
        leverage_series_empty=len(lev_series) == 0,
    )

    # Convert to slides
    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited data available for one or more modules"
        )

    return {
        "section_id": "capital_structure_financial_health",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="capital_structure_financial_health",
    build_prompt=_build_prompt,
    schema=get_csfh_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
