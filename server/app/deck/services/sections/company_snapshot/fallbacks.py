"""
Deterministic fallback helpers for the Company Snapshot section.

Every helper is a pure function that returns resolved values + confidence.
No LLM calls — these run *before* prompt construction.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

Confidence = Literal["high", "medium", "low"]

# ── Formatting helpers ───────────────────────────────────────────────────────

_CURRENCY_THRESHOLDS = [
    (1_000_000_000_000, "T"),
    (1_000_000_000, "B"),
    (1_000_000, "M"),
    (1_000, "K"),
]


def fmt_currency(value: float | int | None, prefix: str = "$") -> str | None:
    """Format a numeric value as a compact currency string (e.g. $12.3B)."""
    if value is None:
        return None
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    for threshold, suffix in _CURRENCY_THRESHOLDS:
        if abs_val >= threshold:
            return f"{sign}{prefix}{abs_val / threshold:.1f}{suffix}"
    return f"{sign}{prefix}{abs_val:,.0f}"


# ── Segments ─────────────────────────────────────────────────────────────────

def resolve_segments_tier(
    segments: list[dict[str, Any]] | None,
    has_mix: bool = False,
) -> tuple[Literal["tier_a", "tier_b", "tier_c"], Confidence]:
    """
    Determine segment display tier and confidence.

    Tier A: % mix exists -> include mix_pct per segment
    Tier B: segments exist but no % -> list with one_liner only
    Tier C: no segments -> infer from description, low confidence
    """
    if not segments:
        return "tier_c", "low"
    if has_mix:
        return "tier_a", "high"
    return "tier_b", "medium"


# ── Customers ────────────────────────────────────────────────────────────────

_UNDISCLOSED_CONCENTRATION = (
    "not disclosed; assess via end-market exposure"
)


def resolve_customer_concentration(
    concentration: str | None,
) -> tuple[str, Confidence]:
    """
    Return (concentration_text, max_confidence).

    If concentration is disclosed -> (fact, "high")
    Else -> (standard undisclosed text, "medium")
    """
    if concentration and concentration.strip():
        return concentration.strip(), "high"
    return _UNDISCLOSED_CONCENTRATION, "medium"


# ── Money model ──────────────────────────────────────────────────────────────

_VOLUME_KEYWORDS = {"commodity", "cyclical", "project", "transactional", "unit"}
_SUBSCRIPTION_KEYWORDS = {"saas", "subscription", "recurring", "contracted", "license"}


def resolve_money_model(
    pricing_unit: str | None,
    sector: str | None = None,
    industry: str | None = None,
) -> tuple[str, Confidence, str | None]:
    """
    Return (pricing_unit_text, confidence, notes).

    If pricing_unit is provided -> use it directly.
    Else -> infer from sector/industry keywords, confidence=low.
    """
    if pricing_unit and pricing_unit.strip():
        return pricing_unit.strip(), "high", None

    # Attempt inference from sector/industry
    context = " ".join(filter(None, [sector, industry])).lower()
    for kw in _SUBSCRIPTION_KEYWORDS:
        if kw in context:
            return (
                "primarily subscription/contracted",
                "low",
                "pricing unit inferred from sector/industry classification",
            )
    for kw in _VOLUME_KEYWORDS:
        if kw in context:
            return (
                "primarily volume-based",
                "low",
                "pricing unit inferred from sector/industry classification",
            )

    return (
        "not disclosed",
        "low",
        "pricing unit could not be determined from available data",
    )


# ── Quick stats ──────────────────────────────────────────────────────────────

# Ordered list of (input_key, display_label) — we keep the first 6 non-null.
_STAT_PRIORITY: list[tuple[str, str]] = [
    ("market_cap", "Market Cap"),
    ("ev", "EV"),
    ("revenue_ttm_or_fy0", "Revenue"),
    ("ebitda_ttm_or_fy0", "EBITDA"),
    ("fcf_ttm", "FCF"),
    ("net_debt", "Net Debt"),
    ("leverage", "Leverage"),
]

_MAX_QUICK_STATS = 6
_MIN_QUICK_STATS_FOR_CONFIDENCE = 2


def resolve_quick_stats(
    financials: dict[str, Any] | None,
    as_of: str | None = None,
) -> tuple[list[dict[str, Any]], bool]:
    """
    Build the quick-stats row from available financials.

    Returns:
        (stats_list, low_confidence_flag)
        - stats_list: up to 6 ``{label, value, as_of}`` dicts
        - low_confidence_flag: True when fewer than 2 stats are available
    """
    if not financials:
        return [], True

    stats: list[dict[str, Any]] = []
    for key, label in _STAT_PRIORITY:
        raw = financials.get(key)
        if raw is None:
            continue
        # Leverage is a ratio, not currency
        if key == "leverage":
            value_str = f"{raw:.1f}x" if isinstance(raw, (int, float)) else str(raw)
        else:
            formatted = fmt_currency(raw)
            value_str = formatted if formatted else str(raw)
        stats.append({"label": label, "value": value_str, "as_of": as_of})
        if len(stats) >= _MAX_QUICK_STATS:
            break

    low_flag = len(stats) < _MIN_QUICK_STATS_FOR_CONFIDENCE
    return stats, low_flag


# ── Proof points ─────────────────────────────────────────────────────────────

_MIN_KPIS_FOR_CONFIDENCE = 3


def resolve_proof_points_confidence(
    kpis: list[dict[str, Any]] | None,
) -> tuple[Confidence, str | None]:
    """
    Return (confidence, notes) based on KPI count.

    Fewer than 3 -> low + "limited disclosure" note.
    """
    count = len(kpis) if kpis else 0
    if count >= _MIN_KPIS_FOR_CONFIDENCE:
        return "high", None
    return "low", "limited disclosure of operational KPIs"


# ── Aggregate confidence ─────────────────────────────────────────────────────

def any_module_low_confidence(modules: dict[str, Any]) -> bool:
    """Return True if any module has confidence == 'low'."""
    for mod in modules.values():
        if isinstance(mod, dict) and mod.get("confidence") == "low":
            return True
    return False
