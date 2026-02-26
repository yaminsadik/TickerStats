"""
SectionSpec definition for Risks & Underwriting.

Composes module prompt fragments into a single LLM prompt and provides
a postprocess callback that converts the custom structured output into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.risks_underwriting.fallbacks import (
    apply_fallbacks,
    compute_rank_score,
    item_confidence,
    overall_confidence,
    sort_risks_by_score,
)
from app.deck.services.sections.risks_underwriting.modules import (
    risk_items as risk_items_mod,
    break_thesis as break_thesis_mod,
)
from app.deck.services.sections.risks_underwriting.render import render_to_slides
from app.deck.services.sections.risks_underwriting.schemas import (
    RisksUnderwritingOutput,
    get_risks_underwriting_json_schema,
    get_risks_underwriting_json_schema_str,
)

logger = logging.getLogger(__name__)


# ── Module registry (order matters for prompt composition) ───────────────────

_MODULES = [
    risk_items_mod,
    break_thesis_mod,
]

# ── Prompt builder ───────────────────────────────────────────────────────────

_SYSTEM_PREAMBLE = """\
You are an institutional equity research analyst generating a Risks &
Underwriting slide for a pitch deck.  Respond with valid JSON ONLY — no
markdown, no commentary, no code fences.

The JSON must conform exactly to the schema provided below."""

_HARD_RULES = """\
## GLOBAL HARD RULES
1. You may polish language, but you must not introduce any new risks, rankings, or indicators.
2. Every risk in the output must originate from the user-provided list below.
3. Do NOT invent leading indicators, mitigants, probability, or impact values.
4. If probability/impact is "not_provided", keep it as "not_provided" — do NOT guess.
5. Neutral tone. No accusations. No "fraud" or "illegal" claims unless user explicitly used that language.
6. Preserve rank_score values exactly as provided.
7. Preserve confidence values exactly as provided.
8. Set low_confidence_flag exactly as instructed.
9. break_thesis_line must be null unless flip conditions are provided.
10. Use concise, institutional phrasing throughout. No marketing language.
11. Do NOT include URLs or citations in any field.
"""


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Compose the full LLM prompt from all module fragments.

    Applies normalize + rank scoring BEFORE the LLM sees the data,
    providing the normalized risk list as the only source of truth.
    """
    # Build per-module contexts
    contexts = []
    for mod in _MODULES:
        ctx = mod.build_context(inputs)
        contexts.append((mod, ctx))

    # Extract pre-computed overall confidence from risk_items context
    risk_ctx = contexts[0][1]  # risk_items is first
    risks = risk_ctx["risks"]
    conf, low_flag = overall_confidence(risks)

    parts = [
        _SYSTEM_PREAMBLE,
        "",
        "## OUTPUT JSON SCHEMA",
        get_risks_underwriting_json_schema_str(),
        "",
        _HARD_RULES,
    ]

    # Ticker
    ticker = inputs.get("ticker", "UNKNOWN")
    parts.append(f"## CONTEXT\nTicker: {ticker}")

    # Overall confidence instruction
    parts.append(
        f"\n## PRE-COMPUTED VALUES (use exactly)\n"
        f"- confidence: \"{conf}\"\n"
        f"- low_confidence_flag: {str(low_flag).lower()}\n"
        f"- ticker: \"{ticker}\""
    )

    # Module fragments
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
    Transform the custom RisksUnderwritingOutput into the standard
    ``{section_id, slides[]}`` structure expected by the pipeline.

    Key: recompute rank_score, ordering, confidence deterministically
    to override any model drift.
    """
    # Validate with Pydantic (lenient — log but don't crash)
    try:
        parsed = RisksUnderwritingOutput.model_validate(content)
        data = parsed.model_dump()
    except Exception as exc:
        logger.warning("RisksUnderwritingOutput validation issue: %s", exc)
        data = content if isinstance(content, dict) else {}

    # Recompute rank_score and confidence deterministically
    risks = data.get("risks", [])
    for r in risks:
        r["rank_score"] = compute_rank_score(r.get("impact", "not_provided"), r.get("probability", "not_provided"))
        r["confidence"] = item_confidence(r)

    # Re-sort by rank_score (descending, stable)
    risks = sort_risks_by_score(risks)
    data["risks"] = risks

    # Recompute overall confidence
    conf, low_flag = overall_confidence(risks)
    data["confidence"] = conf
    data["low_confidence_flag"] = low_flag

    # Render to slides
    deck_length = inputs.get("deck_length", "standard")
    if hasattr(deck_length, "value"):
        deck_length = deck_length.value
    slides = render_to_slides(data, deck_length=deck_length)

    verification_notes: list[str] = []
    if low_flag:
        verification_notes.append(
            "Low confidence — missing risk indicators/rank inputs"
        )

    return {
        "section_id": "risks_underwriting",
        "slides": slides,
        "needs_verification": False,
        "verification_notes": verification_notes,
    }


# ── Export ───────────────────────────────────────────────────────────────────

SECTION_SPEC = SectionSpec(
    id="risks_underwriting",
    build_prompt=_build_prompt,
    schema=get_risks_underwriting_json_schema(),
    required_context={"ticker"},
    postprocess=_postprocess,
)
