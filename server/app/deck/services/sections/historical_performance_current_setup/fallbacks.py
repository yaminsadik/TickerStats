"""
Deterministic fallback helpers for the Historical Performance & Current Setup
section.

Every helper is a pure function — no LLM calls.  These are invoked *before*
prompt construction so the prompt already contains resolved constraints.
"""

from __future__ import annotations

from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]
SetupMode = Literal["price_vs_benchmark", "valuation_rerating", "both"]

# Metric priority order for fundamentals
_METRIC_PRIORITY = [
    "revenue",
    "operating_margin",
    "ebitda_margin",
    "fcf",
    "fcf_conversion",
    "roic",
    "roe",
    "gross_margin",
    "sector_proxy",
]


# ── Fundamentals helpers ─────────────────────────────────────────────────────


def resolve_window_years(
    financials: dict[str, Any] | None,
) -> int:
    """Choose window_years based on available history (prefer 5, allow 3)."""
    if not financials or not isinstance(financials, dict):
        return 3

    # Check how many periods have data
    series_data = financials.get("series") or financials.get("annual") or []
    if isinstance(series_data, list):
        non_null_periods = len([
            d for d in series_data
            if isinstance(d, dict) and any(
                v is not None for k, v in d.items() if k != "period"
            )
        ])
        if non_null_periods >= 5:
            return 5
        if non_null_periods >= 4:
            return 4
    return 3


def filter_series_with_min_points(
    series: list[dict[str, Any]],
    min_points: int = 3,
) -> list[dict[str, Any]]:
    """Include only series with >= min_points non-null data points."""
    result: list[dict[str, Any]] = []
    for s in series:
        if not isinstance(s, dict):
            continue
        points = s.get("points", [])
        non_null = sum(
            1 for p in points
            if isinstance(p, dict) and p.get("value") is not None
        )
        if non_null >= min_points:
            result.append(s)
    return result


def select_priority_metrics(
    available: list[str],
) -> list[str]:
    """Select metrics based on priority ordering.

    Always includes revenue if present.
    Then picks one profitability metric and one cash metric.
    ROIC/ROE only if explicitly available.
    """
    selected: list[str] = []

    # Always include revenue
    if "revenue" in available:
        selected.append("revenue")

    # Profitability: prefer operating_margin > ebitda_margin > gross_margin
    for m in ["operating_margin", "ebitda_margin", "gross_margin"]:
        if m in available:
            selected.append(m)
            break

    # Cash: prefer fcf > fcf_conversion
    for m in ["fcf", "fcf_conversion"]:
        if m in available:
            selected.append(m)
            break

    # ROIC/ROE only if disclosed
    for m in ["roic", "roe"]:
        if m in available:
            selected.append(m)
            break

    # Sector proxy if present and we have room
    if "sector_proxy" in available and "sector_proxy" not in selected:
        selected.append("sector_proxy")

    return selected


def resolve_fundamentals_confidence(
    window_years: int,
    series_count: int,
) -> Confidence:
    """Determine fundamentals confidence."""
    if window_years >= 4 and series_count >= 3:
        return "high"
    if window_years >= 3 and series_count >= 2:
        return "medium"
    return "low"


# ── Setup mode selection ─────────────────────────────────────────────────────


def resolve_setup_mode(
    has_price_series: bool,
    has_rerating_data: bool,
) -> SetupMode:
    """
    Determine which setup mode to use.

    - if price series exists and rerating exists -> both
    - elif rerating exists -> valuation_rerating
    - elif price series exists -> price_vs_benchmark
    - else -> valuation_rerating with empty series and confidence low
    """
    if has_price_series and has_rerating_data:
        return "both"
    if has_rerating_data:
        return "valuation_rerating"
    if has_price_series:
        return "price_vs_benchmark"
    return "valuation_rerating"


def has_price_series_data(inputs: dict[str, Any]) -> bool:
    """Check if price series data is available in inputs."""
    price = inputs.get("price_history") or inputs.get("price_series") or {}
    if isinstance(price, dict):
        points = price.get("points") or price.get("prices") or []
        return isinstance(points, list) and len(points) >= 2
    if isinstance(price, list) and len(price) >= 2:
        return True
    return False


def has_rerating_data(inputs: dict[str, Any]) -> bool:
    """Check if valuation rerating data is available in inputs."""
    rerating = (
        inputs.get("rerating")
        or inputs.get("valuation_multiples")
        or inputs.get("multiples")
        or {}
    )
    if isinstance(rerating, dict):
        # Any of: current multiple, median, comps present
        has_current = rerating.get("current") is not None
        has_median = rerating.get("median") is not None or rerating.get("historical_median") is not None
        has_series = bool(rerating.get("series"))
        return has_current or has_median or has_series
    if isinstance(rerating, list) and len(rerating) >= 1:
        return True
    return False


# ── What changed fallback ────────────────────────────────────────────────────


def resolve_what_changed(
    inputs: dict[str, Any],
) -> tuple[list[dict[str, Any]], Confidence, str | None]:
    """
    Extract recent events from inputs.

    Returns (events_list, confidence, notes).
    If no events provided -> empty list, confidence low, notes explain gap.
    """
    events = (
        inputs.get("recent_events")
        or inputs.get("events")
        or inputs.get("catalysts")
        or []
    )
    if not isinstance(events, list):
        events = []

    valid_events: list[dict[str, Any]] = []
    for e in events:
        if isinstance(e, dict) and e.get("headline"):
            valid_events.append(e)

    if not valid_events:
        return [], "low", "No recent event data provided"

    # Cap at 6
    valid_events = valid_events[:6]

    if len(valid_events) >= 3:
        return valid_events, "high", None
    return valid_events, "medium", None


# ── Low-confidence flag ──────────────────────────────────────────────────────


def compute_low_confidence_flag(
    fundamentals_confidence: str,
    stock_confidence: str,
    rerating_confidence: str,
    what_changed_confidence: str,
    window_years: int,
    setup_mode: str,
    has_usable_series: bool,
    events_empty: bool,
) -> bool:
    """
    True if:
    - any module confidence == low
    - fundamentals window < 3
    - setup_mode has no usable series
    - events empty
    """
    confidences = [
        fundamentals_confidence,
        stock_confidence,
        rerating_confidence,
        what_changed_confidence,
    ]
    if "low" in confidences:
        return True
    if window_years < 3:
        return True
    if not has_usable_series:
        return True
    if events_empty:
        return True
    return False
