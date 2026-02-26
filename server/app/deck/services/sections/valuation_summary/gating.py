"""Deterministic gating for the Valuation Summary section."""

from __future__ import annotations

from typing import Any


def _get_valuation(inputs: dict[str, Any]) -> dict[str, Any]:
    """Extract valuation input dict from inputs."""
    return inputs.get("valuation") or inputs.get("valuation_input") or {}


def _get_trust_mode(inputs: dict[str, Any]) -> str:
    """Extract trust mode string from inputs."""
    mode = inputs.get("data_trust_mode", "user_auto_fetch")
    if hasattr(mode, "value"):
        mode = mode.value
    return mode


def should_include_section(inputs: dict[str, Any]) -> bool:
    """
    Return True if the section should be generated.

    True when any of:
    - valuation_methods non-empty
    - peer_tickers non-empty
    - target_multiple_range not empty
    - price_target not empty
    - dcf_assumptions not empty
    - include_dcf is True and trust_mode allows it
    """
    val = _get_valuation(inputs)

    if val.get("methods"):
        return True

    if val.get("peer_tickers"):
        return True

    if val.get("target_multiple_range"):
        return True

    if val.get("price_target"):
        return True

    if val.get("dcf_assumptions"):
        return True

    if inputs.get("dcf_assumptions_structured"):
        return True

    include_dcf = inputs.get("include_dcf") or inputs.get("include_dcf_output")
    if include_dcf:
        trust_mode = _get_trust_mode(inputs)
        if trust_mode not in ("user_only", "narrative_only"):
            return True

    return False


def should_run_dcf(inputs: dict[str, Any]) -> bool:
    """
    Return True if the deterministic DCF calculator should be run.

    True when:
    - trust_mode == "user_auto_fetch"
    - ("dcf" in valuation_methods OR include_dcf_output is True)
    - ticker is present
    """
    trust_mode = _get_trust_mode(inputs)
    if trust_mode != "user_auto_fetch":
        return False

    ticker = inputs.get("ticker")
    if not ticker:
        return False

    val = _get_valuation(inputs)
    methods = val.get("methods") or []

    include_dcf = inputs.get("include_dcf") or inputs.get("include_dcf_output")

    if "dcf" in methods or include_dcf:
        return True

    return False
