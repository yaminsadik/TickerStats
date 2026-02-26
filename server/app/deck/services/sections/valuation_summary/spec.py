"""SectionSpec definition for Valuation Summary."""

from __future__ import annotations

import logging
from typing import Any

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.valuation_summary.fallbacks import (
    build_user_targets,
    compute_confidence,
    compute_low_confidence_flag,
    normalize_peer_set,
)
from app.deck.services.sections.valuation_summary.modules.dcf_block import build_dcf_block
from app.deck.services.sections.valuation_summary.modules.methods_inputs import build_methods
from app.deck.services.sections.valuation_summary.modules.sensitivities import build_sensitivities
from app.deck.services.sections.valuation_summary.render import render_to_slides
from app.deck.services.sections.valuation_summary.schemas import (
    DcfResultOut,
    ValuationSummaryOutput,
    get_valuation_summary_json_schema,
)

logger = logging.getLogger(__name__)


def _build_prompt(inputs: dict[str, Any]) -> str:
    """
    Build a minimal LLM prompt.

    For Valuation Summary, the actual content is built deterministically in
    postprocess.  The prompt exists to satisfy the SectionSpec interface.
    """
    return (
        "This section is generated deterministically. "
        "Return exactly: {}\n"
        "Do not add any other content."
    )


def _get_valuation(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract valuation input from the inputs dict."""
    return inputs.get("valuation") or inputs.get("valuation_input") or {}


def _get_trust_mode(inputs: dict[str, Any]) -> str:
    """Extract trust mode string."""
    mode = inputs.get("data_trust_mode", "user_auto_fetch")
    if hasattr(mode, "value"):
        mode = mode.value
    return mode


def _postprocess(content: Any, inputs: dict[str, Any]) -> dict[str, Any]:
    """
    Build Valuation Summary deterministically from inputs.

    The LLM content is ignored; all output is computed from user inputs
    and the deterministic DCF calculator.
    """
    ticker = inputs.get("ticker", "UNKNOWN")
    trust_mode = _get_trust_mode(inputs)
    deck_length = inputs.get("deck_length", "standard")
    if hasattr(deck_length, "value"):
        deck_length = deck_length.value

    valuation = _get_valuation(inputs)

    # Build methods
    methods = build_methods(valuation)

    # Build peer set
    peer_set = normalize_peer_set(valuation.get("peer_tickers"))

    # Build user targets
    user_targets = build_user_targets(
        valuation.get("target_multiple_range"),
        valuation.get("price_target"),
    )

    # Build DCF block
    dcf = build_dcf_block(inputs)

    # Enforce trust mode on DCF
    if trust_mode == "user_only" and dcf.included:
        dcf = DcfResultOut(
            included=False,
            notes="DCF excluded (user_only mode)",
        )
    if trust_mode == "narrative_only":
        dcf = DcfResultOut(included=False)
        user_targets = []

    # Build sensitivities
    sensitivities = build_sensitivities(methods, trust_mode)

    # Compute confidence
    has_relative_inputs = bool(
        valuation.get("peer_tickers") and valuation.get("target_multiple_range")
    )
    has_any_inputs = bool(
        valuation.get("peer_tickers")
        or valuation.get("target_multiple_range")
        or valuation.get("price_target")
        or valuation.get("dcf_assumptions")
    )
    confidence = compute_confidence(
        dcf_included=dcf.included,
        methods=[m.method for m in methods],
        peers=peer_set,
        user_targets=user_targets,
        has_relative_inputs=has_relative_inputs,
    )
    low_flag = compute_low_confidence_flag(
        confidence=confidence,
        methods=[m.method for m in methods],
        has_any_inputs=has_any_inputs,
    )

    # Build output
    try:
        output = ValuationSummaryOutput(
            ticker=ticker,
            trust_mode=trust_mode,
            methods=methods,
            peer_set=peer_set,
            user_targets=user_targets,
            dcf=dcf,
            sensitivities=sensitivities,
            confidence=confidence,
            low_confidence_flag=low_flag,
        )
        output_dict = output.model_dump()
    except Exception as exc:
        logger.warning("ValuationSummaryOutput validation issue: %s", exc)
        output_dict = {
            "ticker": ticker,
            "trust_mode": trust_mode,
            "methods": [m.model_dump() for m in methods],
            "peer_set": peer_set,
            "user_targets": user_targets,
            "dcf": dcf.model_dump(),
            "sensitivities": sensitivities,
            "confidence": confidence,
            "low_confidence_flag": low_flag,
        }

    # Stash valuation input for slide 2 rendering
    output_dict["_valuation_input"] = valuation

    # Render to slides
    slides = render_to_slides(output_dict, deck_length=deck_length)

    verification_notes: list[str] = []
    if low_flag:
        verification_notes.append(
            "Low confidence — limited valuation inputs provided"
        )

    return {
        "section_id": "valuation_summary",
        "slides": slides,
        "needs_verification": dcf.included,
        "verification_notes": verification_notes,
    }


SECTION_SPEC = SectionSpec(
    id="valuation_summary",
    build_prompt=_build_prompt,
    schema=get_valuation_summary_json_schema(),
    required_context={"ticker"},
    postprocess=_postprocess,
)
