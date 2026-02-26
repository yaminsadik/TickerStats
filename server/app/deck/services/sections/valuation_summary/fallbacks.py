"""Deterministic fallbacks for the Valuation Summary section."""

from __future__ import annotations

from typing import Optional

from app.deck.services.sections.valuation_summary.schemas import Confidence


def normalize_peer_set(peers: Optional[list[str]]) -> list[str]:
    """Deduplicate and cap peer set to 10."""
    if not peers:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for p in peers:
        p_upper = p.strip().upper()
        if p_upper and p_upper not in seen:
            seen.add(p_upper)
            result.append(p_upper)
        if len(result) >= 10:
            break
    return result


def build_user_targets(
    target_multiple_range: Optional[str],
    price_target: Optional[str],
) -> list[str]:
    """Build user target strings. Only include labels when input exists."""
    targets: list[str] = []
    if target_multiple_range and target_multiple_range.strip():
        targets.append(f"Target multiple: {target_multiple_range.strip()}")
    if price_target and price_target.strip():
        targets.append(f"Price target: {price_target.strip()}")
    return targets[:3]


# ── Sensitivity banks per method ─────────────────────────────────────────────

_DCF_SENSITIVITIES = [
    "WACC and terminal growth drive terminal value",
    "FCF margin/trajectory is primary driver",
    "Reinvestment intensity affects FCF conversion",
]

_RELATIVE_SENSITIVITIES = [
    "Multiple selection vs peer set drives PT",
    "Growth vs margin tradeoff impacts multiple",
    "Peer mix and cycle timing affect comps",
]

_NAV_SENSITIVITIES = [
    "Cap rates and NOI assumptions drive NAV",
    "Occupancy and lease terms affect cash flow stability",
    "Asset quality and replacement cost set floor",
]

_SOTP_SENSITIVITIES = [
    "Segment multiple assignment drives blended value",
    "Holding company discount assumptions vary",
    "Cross-segment synergies may not be captured",
]

_UNIT_ECON_SENSITIVITIES = [
    "Unit economics depend on stable cohort behavior",
    "CAC payback and LTV assumptions drive valuation",
    "Growth rate vs churn tradeoff is key",
]

_YIELD_SENSITIVITIES = [
    "Yield spread assumptions drive relative value",
    "Duration and credit quality affect risk premium",
    "Reinvestment rate assumptions impact total return",
]

_GENERIC_SENSITIVITIES = [
    "Input assumption changes materially affect implied value",
    "Method selection and weighting drive composite PT",
    "Market multiples are cyclical and sector-dependent",
]

_METHOD_SENSITIVITIES: dict[str, list[str]] = {
    "dcf": _DCF_SENSITIVITIES,
    "relative": _RELATIVE_SENSITIVITIES,
    "nav": _NAV_SENSITIVITIES,
    "sotp": _SOTP_SENSITIVITIES,
    "unit_econ": _UNIT_ECON_SENSITIVITIES,
    "yield": _YIELD_SENSITIVITIES,
}


def default_sensitivities(
    methods: list[str],
    trust_mode: str,
) -> list[str]:
    """
    Return 2-3 qualitative sensitivity strings.

    Sensitivities are always qualitative (no numbers).
    """
    result: list[str] = []

    for m in methods:
        m_lower = m.lower()
        sens = _METHOD_SENSITIVITIES.get(m_lower, [])
        for s in sens:
            if s not in result:
                result.append(s)
            if len(result) >= 3:
                break
        if len(result) >= 3:
            break

    # Fill with generic if not enough
    if len(result) < 2:
        for s in _GENERIC_SENSITIVITIES:
            if s not in result:
                result.append(s)
            if len(result) >= 3:
                break

    return result[:3]


def compute_confidence(
    dcf_included: bool,
    methods: list[str],
    peers: list[str],
    user_targets: list[str],
    has_relative_inputs: bool = False,
) -> Confidence:
    """
    Compute confidence level.

    - high: DCF included OR (relative inputs include peers + target range)
    - medium: methods selected but limited inputs
    - low: almost nothing provided
    """
    if dcf_included:
        return "high"

    if has_relative_inputs and peers and user_targets:
        return "high"

    if methods:
        return "medium"

    return "low"


def compute_low_confidence_flag(
    confidence: Confidence,
    methods: list[str],
    has_any_inputs: bool,
) -> bool:
    """Return True if confidence is low OR methods selected but no inputs."""
    if confidence == "low":
        return True
    if methods and not has_any_inputs:
        return True
    return False
