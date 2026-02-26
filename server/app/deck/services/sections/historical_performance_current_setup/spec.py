"""
SectionSpec definition for Historical Performance & Current Setup.

Composes all module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    compute_low_confidence_flag,
    has_price_series_data,
    has_rerating_data as _has_rerating,
    resolve_setup_mode,
)
from app.deck.services.sections.historical_performance_current_setup.modules import (
    fundamentals as fundamentals_mod,
    valuation_rerating as valuation_rerating_mod,
    stock_vs_benchmark as stock_vs_benchmark_mod,
    what_changed as what_changed_mod,
)
from app.deck.services.sections.historical_performance_current_setup.render import (
    render_to_slides,
)
from app.deck.services.sections.historical_performance_current_setup.schemas import (
    get_hpcs_json_schema,
    HistoricalPerfCurrentSetupOutput,
    get_hpcs_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    fundamentals_mod,
    stock_vs_benchmark_mod,
    valuation_rerating_mod,
    what_changed_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Historical
Performance & Current Setup analysis for a pitch deck. Respond with valid
JSON ONLY — no markdown, no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES (apply to ALL modules)
1. Fundamentals module: ONLY operating/financial trends. NO price talk, NO multiples.
2. Stock vs Benchmark module: ONLY price/benchmark comparison. NO fundamentals, NO multiples.
3. Valuation Rerating module: ONLY multiples/premium/median context. NO operating KPIs, NO price charts.
4. What Changed module: ONLY discrete events + sentiment. NO invented numbers, NO fabricated dates.
5. NEVER fabricate numbers or dates — revenue, margins, multiples, prices, etc. Use null when not provided.
6. If data is missing, follow the fallback instructions per module.
7. Confidence: "high" = sourced data, "medium" = reasonable inference, "low" = speculative or data missing.
8. Set low_confidence_flag = true if ANY module confidence == "low" OR fundamentals window_years < 3 OR setup has no usable series OR events empty.
9. Use concise, institutional phrasing throughout. No marketing language.
10. Do NOT include URLs or citations in any field.
11. setup_mode must reflect what data is actually available (price_vs_benchmark, valuation_rerating, or both).
12. Series points must use only provided input values — never interpolate or extrapolate.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Parameters
    ----------
    inputs : dict
        The inputs dict assembled by the orchestrator.  Expected keys include
        ``ticker``, ``company_name``, ``sector``, ``financials``,
        ``price_history``, ``rerating``, ``recent_events``, etc.
    """
    # Determine setup mode
    has_price = has_price_series_data(inputs)
    has_rerate = _has_rerating(inputs)
    setup_mode = resolve_setup_mode(has_price, has_rerate)

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
        get_hpcs_json_schema_str(),
        "",
        _HARD_RULES,
        f'\nset setup_mode to "{setup_mode}".',
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
    Transform the custom HistoricalPerfCurrentSetupOutput into the standard
    ``{section_id, slides[], needs_verification, verification_notes}``
    structure expected by the pipeline.
    """
    # Validate with Pydantic (lenient — log but don't crash on non-critical)
    try:
        parsed = HistoricalPerfCurrentSetupOutput.model_validate(content)
        output_dict = parsed.model_dump()
    except Exception as exc:
        logger.warning("HistoricalPerfCurrentSetupOutput validation issue: %s", exc)
        output_dict = content if isinstance(content, dict) else {}

    # Compute / confirm low_confidence_flag deterministically
    fund_conf = output_dict.get("fundamentals", {}).get("confidence", "low")
    stock_conf = output_dict.get("stock", {}).get("confidence", "low")
    rerate_conf = output_dict.get("rerating", {}).get("confidence", "low")
    wc_conf = output_dict.get("what_changed", {}).get("confidence", "low")
    window_years = output_dict.get("fundamentals", {}).get("window_years", 0)
    setup_mode = output_dict.get("setup_mode", "valuation_rerating")
    events = output_dict.get("what_changed", {}).get("events", [])

    # Determine if setup has usable series data
    has_usable_series = False
    if setup_mode in ("price_vs_benchmark", "both"):
        stock_series = output_dict.get("stock", {}).get("series", [])
        if stock_series:
            has_usable_series = True
    if setup_mode in ("valuation_rerating", "both"):
        rerate_series = output_dict.get("rerating", {}).get("series", [])
        rerate_cvs = output_dict.get("rerating", {}).get("current_vs_median", [])
        if rerate_series or rerate_cvs:
            has_usable_series = True

    output_dict["low_confidence_flag"] = compute_low_confidence_flag(
        fundamentals_confidence=fund_conf,
        stock_confidence=stock_conf,
        rerating_confidence=rerate_conf,
        what_changed_confidence=wc_conf,
        window_years=window_years,
        setup_mode=setup_mode,
        has_usable_series=has_usable_series,
        events_empty=len(events) == 0,
    )

    # Convert to slides
    slides = render_to_slides(output_dict)

    verification_notes: list[str] = []
    if output_dict.get("low_confidence_flag"):
        verification_notes.append(
            "Low confidence — limited data available for one or more modules"
        )

    return {
        "section_id": "historical_performance_current_setup",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="historical_performance_current_setup",
    build_prompt=_build_prompt,
    schema=get_hpcs_json_schema(),
    required_context={"ticker", "company_name"},
    postprocess=_postprocess,
)
