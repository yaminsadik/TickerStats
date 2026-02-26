"""
SectionSpec definition for Investment Thesis Variant View.

Composes module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.

This section is user-controlled: the LLM may polish phrasing and structure,
but must not invent the thesis, recommendation, or factual claims.
"""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.investment_thesis_variant_view.fallbacks import (
    compute_confidence,
    compute_low_confidence_flag,
    normalize_position,
    reject_placeholder,
    sanitize_list,
    select_flip_conditions,
    select_pillars,
)
from app.deck.services.sections.investment_thesis_variant_view.modules import (
    thesis_core,
    variant_view,
    debates_flip_conditions,
)
from app.deck.services.sections.investment_thesis_variant_view.render import (
    render_to_slides,
)
from app.deck.services.sections.investment_thesis_variant_view.schemas import (
    InvestmentThesisVariantViewOutput,
    get_investment_thesis_variant_view_json_schema,
    get_investment_thesis_variant_view_json_schema_str,
)
from app.deck.services.prompts import get_data_trust_instructions, get_position_framing

logger = logging.getLogger(__name__)


# ── Module registry ──────────────────────────────────────────────────────────

_MODULES = [
    thesis_core,
    variant_view,
    debates_flip_conditions,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst structuring an Investment Thesis
slide for a pitch deck. Respond with valid JSON ONLY — no markdown, no
commentary, no code fences.

The JSON must conform exactly to the schema provided below.

CRITICAL: This is a USER-CONTROLLED section. You may lightly rewrite for
clarity and institutional phrasing, but you MUST preserve meaning. Do not
introduce new facts, numbers, or claims not present in the user inputs."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. NEVER fabricate a recommendation, price target, valuation numbers, catalysts,
   or any factual claims not present in the user inputs.
2. thesis_sentence: polish for clarity only. Do NOT change the meaning.
3. thesis_pillars: return user's pillars only. Do NOT add pillars.
4. variant_deltas: structure from user's market_believes / we_believe only.
5. key_debates: derive ONLY from user-provided thesis, variant view, and flip conditions.
6. flip_conditions: return user's conditions only. Do NOT add new ones.
7. Do NOT introduce any numeric claims not present in user inputs.
8. Use concise, neutral, institutional phrasing. No hype or marketing language.
9. If a field was not provided by the user, set it to null or empty list.
10. Confidence field will be recomputed deterministically — set your best estimate.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """Compose the full LLM prompt from all module fragments."""
    # Build per-module contexts
    contexts = []
    for mod in _MODULES:
        ctx = mod.build_context(inputs)
        contexts.append((mod, ctx))

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_investment_thesis_variant_view_json_schema_str(),
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

    parts.append("\nRespond with the JSON object only. No extra text before or after.")

    return "\n\n".join(parts)


# ── Postprocess ──────────────────────────────────────────────────────────────


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Transform InvestmentThesisVariantViewOutput into the standard
    ``{section_id, slides[]}`` structure.

    Deterministically recomputes confidence and low_confidence_flag —
    does not trust the model's values.
    """
    # Validate with Pydantic
    try:
        parsed = InvestmentThesisVariantViewOutput.model_validate(content)
        out = parsed.model_dump()
    except Exception as exc:
        logger.warning("InvestmentThesisVariantViewOutput validation issue: %s", exc)
        out = content if isinstance(content, dict) else {}

    # Sanitize: remove placeholder bullets
    pillars = sanitize_list(out.get("thesis_pillars") or [])
    out["thesis_pillars"] = select_pillars(pillars)

    flip_conditions = sanitize_list(out.get("flip_conditions") or [])
    out["flip_conditions"] = select_flip_conditions(flip_conditions)

    key_debates = sanitize_list(out.get("key_debates") or [])
    out["key_debates"] = key_debates[:3]

    # Sanitize thesis sentence
    if reject_placeholder(out.get("thesis_sentence")):
        out["thesis_sentence"] = None

    # Cap variant_deltas at 3
    variant_deltas = out.get("variant_deltas") or []
    out["variant_deltas"] = variant_deltas[:3]

    # Deterministic confidence recomputation (do not trust model)
    confidence = compute_confidence(
        out.get("thesis_sentence"),
        out.get("thesis_pillars", []),
        out.get("variant_deltas", []),
    )
    out["confidence"] = confidence

    low_flag = compute_low_confidence_flag(
        confidence,
        out.get("thesis_sentence"),
        out.get("thesis_pillars", []),
    )
    out["low_confidence_flag"] = low_flag

    # Build notes for missing inputs
    missing = []
    if not out.get("thesis_sentence"):
        missing.append("thesis_sentence")
    if len(out.get("thesis_pillars", [])) < 2:
        missing.append("thesis_pillars (<2)")
    if not out.get("variant_deltas"):
        missing.append("variant_deltas")
    if missing:
        out["notes"] = f"Missing inputs: {', '.join(missing)}"

    # Render to slides
    deck_length = inputs.get("deck_length", "standard")
    slides = render_to_slides(out, deck_length=deck_length)

    verification_notes: list[str] = []
    if low_flag:
        verification_notes.append(
            "Low confidence — missing user thesis inputs (sentence/pillars/variant view)"
        )

    return {
        "section_id": "investment_thesis_variant_view",
        "slides": slides,
        "needs_verification": low_flag,
        "verification_notes": verification_notes,
    }


# ── Export ────────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="investment_thesis_variant_view",
    build_prompt=_build_prompt,
    schema=get_investment_thesis_variant_view_json_schema(),
    required_context={"ticker"},
    postprocess=_postprocess,
)
