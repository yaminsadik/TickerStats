"""Build MethodSummary list from user inputs."""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.valuation_summary.schemas import MethodSummary


_METHOD_LABELS: dict[str, str] = {
    "dcf": "DCF",
    "relative": "Relative",
    "sotp": "Sum-of-the-Parts",
    "nav": "NAV",
    "unit_econ": "Unit Economics",
    "yield": "Yield-Based",
}


def build_methods(valuation: dict[str, Any]) -> list[MethodSummary]:
    """Build MethodSummary list from user valuation inputs."""
    methods_list = valuation.get("methods") or []
    result: list[MethodSummary] = []

    for method_key in methods_list:
        label = _METHOD_LABELS.get(method_key.lower(), method_key)
        provided = _get_provided_inputs(method_key.lower(), valuation)
        result.append(MethodSummary(
            method=label,
            provided_inputs=provided,
            notes=None,
        ))

    return result


def _get_provided_inputs(method: str, valuation: dict[str, Any]) -> list[str]:
    """Determine which inputs the user provided for this method."""
    provided: list[str] = []

    if method == "dcf":
        if valuation.get("dcf_assumptions"):
            provided.append("dcf_assumptions")
    elif method == "relative":
        if valuation.get("peer_tickers"):
            provided.append("peer_tickers")
        if valuation.get("target_multiple_range"):
            provided.append("target_multiple_range")
    else:
        # Generic: check for any relevant inputs
        if valuation.get("target_multiple_range"):
            provided.append("target_multiple_range")
        if valuation.get("price_target"):
            provided.append("price_target")

    return provided
