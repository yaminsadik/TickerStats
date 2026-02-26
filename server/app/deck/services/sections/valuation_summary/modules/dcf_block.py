"""Build DcfResultOut from deterministic DCF calculator."""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.deck.services.sections.valuation_summary.gating import should_run_dcf
from app.deck.services.sections.valuation_summary.schemas import DcfResultOut

logger = logging.getLogger(__name__)


def build_dcf_block(inputs: dict[str, Any]) -> DcfResultOut:
    """
    Build the DCF result block.

    Uses pre-computed DCF from inputs if available, otherwise runs the
    deterministic calculator when gating allows.
    """
    if not should_run_dcf(inputs):
        return DcfResultOut(included=False)

    # Check for pre-computed DCF result in inputs
    dcf_valuation = inputs.get("dcf_valuation")
    if not dcf_valuation:
        computed = inputs.get("computed_inputs") or {}
        dcf_valuation = computed.get("dcf_valuation")

    if dcf_valuation and isinstance(dcf_valuation, dict):
        return _from_dcf_result(dcf_valuation)

    # Run deterministic calculator
    return _run_calculator(inputs)


def _from_dcf_result(dcf_result: dict[str, Any]) -> DcfResultOut:
    """Extract DcfResultOut from a pre-computed DCF result dict."""
    if dcf_result.get("error"):
        return DcfResultOut(
            included=False,
            notes=f"DCF error: {dcf_result['error']}",
        )

    valuation = dcf_result.get("valuation", {})
    assumptions = dcf_result.get("assumptions", {})

    target_price = valuation.get("targetPrice")
    upside_pct = valuation.get("upsidePct")

    value_per_share = f"${target_price:.2f}" if target_price is not None else None
    upside_downside = _format_upside(upside_pct) if upside_pct is not None else None

    key_assumptions = _extract_assumptions(assumptions)

    source_parts = ["Deterministic DCF"]
    meta = dcf_result.get("meta", {})
    if meta.get("provider"):
        source_parts.append(f"({meta['provider']})")
    sources = dcf_result.get("sources", {})
    has_overrides = any(
        v == "manual_override" for v in sources.values() if isinstance(v, str)
    )
    if has_overrides:
        source_parts.append("+ overrides")

    return DcfResultOut(
        included=True,
        value_per_share=value_per_share,
        upside_downside=upside_downside,
        key_assumptions=key_assumptions,
        source_note=" ".join(source_parts),
    )


def _run_calculator(inputs: dict[str, Any]) -> DcfResultOut:
    """Run the deterministic DCF calculator."""
    try:
        from app.deck.services.dcf_calculator import calculate_dcf
    except ImportError:
        logger.warning("dcf_calculator not available")
        return DcfResultOut(included=False, notes="DCF calculator unavailable")

    ticker = inputs.get("ticker", "")

    assumptions = _build_assumptions(inputs)
    overrides = _build_overrides(inputs)

    try:
        result = calculate_dcf(ticker, assumptions=assumptions, overrides=overrides)
    except Exception as exc:
        logger.warning("DCF calculation failed for %s: %s", ticker, exc)
        return DcfResultOut(included=False, notes=f"DCF calculation failed: {exc}")

    return _from_dcf_result(result)


def _build_assumptions(inputs: dict[str, Any]) -> Optional[dict]:
    """Build DCF assumptions dict from structured inputs."""
    structured = inputs.get("dcf_assumptions_structured")
    if not structured or not isinstance(structured, dict):
        return None

    assumptions: dict[str, Any] = {}
    if "years" in structured:
        assumptions["forecastYears"] = structured["years"]
    if "growth" in structured:
        assumptions["fcfGrowthRate"] = structured["growth"]
    if "terminal_g" in structured:
        assumptions["terminalGrowthRate"] = structured["terminal_g"]
    if "wacc" in structured:
        assumptions["wacc"] = structured["wacc"]

    return assumptions if assumptions else None


def _build_overrides(inputs: dict[str, Any]) -> Optional[dict]:
    """Build DCF overrides dict from structured inputs."""
    structured = inputs.get("dcf_assumptions_structured")
    if not structured or not isinstance(structured, dict):
        return None

    overrides_data = structured.get("overrides")
    if not overrides_data or not isinstance(overrides_data, dict):
        return None

    return overrides_data


def _format_upside(pct: float) -> str:
    """Format upside/downside percentage."""
    sign = "+" if pct >= 0 else ""
    return f"{sign}{pct * 100:.1f}%"


def _extract_assumptions(assumptions: dict[str, Any]) -> list[str]:
    """Extract 2-5 key assumption strings from DCF assumptions dict."""
    items: list[str] = []

    if "forecastYears" in assumptions:
        items.append(f"Forecast period: {assumptions['forecastYears']} years")
    if "fcfGrowthRate" in assumptions:
        rate = assumptions["fcfGrowthRate"]
        items.append(f"FCF growth: {rate * 100:.1f}%")
    if "terminalGrowthRate" in assumptions:
        rate = assumptions["terminalGrowthRate"]
        items.append(f"Terminal growth: {rate * 100:.1f}%")
    if "wacc" in assumptions:
        rate = assumptions["wacc"]
        items.append(f"WACC: {rate * 100:.1f}%")

    return items[:5]
