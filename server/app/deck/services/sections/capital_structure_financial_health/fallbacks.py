"""
Deterministic fallback helpers for the Capital Structure & Financial Health
section.

Every helper is a pure function — no LLM calls.  These are invoked *before*
prompt construction and during postprocess so the output has resolved
constraints.
"""

from __future__ import annotations

from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


# ── Leverage helpers ─────────────────────────────────────────────────────────


def resolve_leverage_confidence(
    series_length: int,
    has_current: bool,
) -> Confidence:
    """
    Determine leverage confidence.

    - high: >=2 series points AND current value present
    - medium: 1 point or current-only
    - low: no data
    """
    if series_length >= 2 and has_current:
        return "high"
    if series_length >= 1 or has_current:
        return "medium"
    return "low"


def has_leverage_data(inputs: dict[str, Any]) -> bool:
    """Check if leverage / debt data is available in inputs."""
    debt = (
        inputs.get("leverage")
        or inputs.get("debt")
        or inputs.get("capital_structure")
        or {}
    )
    if isinstance(debt, dict):
        has_series = bool(debt.get("leverage_series") or debt.get("series"))
        has_current = debt.get("net_debt_to_ebitda") is not None or debt.get("current_net_debt_to_ebitda") is not None
        has_interest = bool(debt.get("interest_metrics") or debt.get("interest_coverage"))
        return has_series or has_current or has_interest
    return False


# ── Maturities helpers ───────────────────────────────────────────────────────


def resolve_maturities_confidence(
    ladder_length: int,
    has_covenants: bool,
) -> Confidence:
    """
    Determine maturities confidence.

    - high: ladder >=3 buckets
    - medium: ladder >=1 bucket
    - low: no ladder data
    """
    if ladder_length >= 3:
        return "high"
    if ladder_length >= 1:
        return "medium"
    return "low"


def has_maturity_data(inputs: dict[str, Any]) -> bool:
    """Check if maturity ladder data is available."""
    mat = (
        inputs.get("maturities")
        or inputs.get("debt_maturities")
        or inputs.get("maturity_ladder")
        or {}
    )
    if isinstance(mat, dict):
        return bool(mat.get("ladder") or mat.get("maturities"))
    if isinstance(mat, list) and len(mat) >= 1:
        return True
    return False


def has_covenant_data(inputs: dict[str, Any]) -> bool:
    """Check if covenant data is explicitly provided."""
    cov = inputs.get("covenants") or inputs.get("debt_covenants") or []
    if isinstance(cov, list) and len(cov) >= 1:
        return True
    mat = inputs.get("maturities") or inputs.get("debt_maturities") or {}
    if isinstance(mat, dict) and mat.get("covenants"):
        return True
    return False


# ── Liquidity helpers ────────────────────────────────────────────────────────


def resolve_liquidity_confidence(
    metrics_count: int,
    has_runway: bool,
) -> Confidence:
    """
    Determine liquidity confidence.

    - high: >=2 metrics
    - medium: 1 metric or runway only
    - low: no data
    """
    if metrics_count >= 2:
        return "high"
    if metrics_count >= 1 or has_runway:
        return "medium"
    return "low"


def has_burn_rate(inputs: dict[str, Any]) -> bool:
    """
    Check if burn rate is provided as a numeric value.

    Only returns True if there is an explicit numeric cash burn or negative FCF.
    Never infer or compute.
    """
    liquidity = inputs.get("liquidity") or inputs.get("cash") or {}
    if isinstance(liquidity, dict):
        burn = liquidity.get("burn_rate") or liquidity.get("cash_burn")
        if burn is not None:
            try:
                float(burn)
                return True
            except (TypeError, ValueError):
                return False
        # Negative FCF counts as burn
        fcf = liquidity.get("fcf") or liquidity.get("free_cash_flow")
        if fcf is not None:
            try:
                return float(fcf) < 0
            except (TypeError, ValueError):
                return False
    return False


# ── Share count helpers ──────────────────────────────────────────────────────


def resolve_share_count_confidence(
    series_length: int,
    has_buybacks: bool,
    has_sbc: bool,
) -> Confidence:
    """
    Determine share count confidence.

    - high: series >=2 AND (buyback or SBC disclosure)
    - medium: series >=1 OR any disclosure
    - low: no data at all
    """
    if series_length >= 2 and (has_buybacks or has_sbc):
        return "high"
    if series_length >= 1 or has_buybacks or has_sbc:
        return "medium"
    return "low"


def has_share_data(inputs: dict[str, Any]) -> bool:
    """Check if share count data is available."""
    shares = (
        inputs.get("shares")
        or inputs.get("share_count")
        or inputs.get("dilution")
        or {}
    )
    if isinstance(shares, dict):
        has_series = bool(shares.get("share_series") or shares.get("series"))
        has_buyback = bool(shares.get("buybacks"))
        has_sbc = bool(shares.get("sbc_dilution") or shares.get("sbc"))
        has_dividends = bool(shares.get("dividends"))
        return has_series or has_buyback or has_sbc or has_dividends
    return False


# ── Low-confidence flag ──────────────────────────────────────────────────────


def compute_low_confidence_flag(
    leverage_confidence: str,
    maturities_confidence: str,
    liquidity_confidence: str,
    share_count_confidence: str,
    maturities_ladder_empty: bool,
    leverage_series_empty: bool,
) -> bool:
    """
    True if:
    - any module confidence == low
    - OR (maturities ladder empty AND leverage series empty)
    """
    confidences = [
        leverage_confidence,
        maturities_confidence,
        liquidity_confidence,
        share_count_confidence,
    ]
    if "low" in confidences:
        return True
    if maturities_ladder_empty and leverage_series_empty:
        return True
    return False
