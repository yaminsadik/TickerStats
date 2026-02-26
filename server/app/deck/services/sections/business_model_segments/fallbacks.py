"""
Deterministic fallback helpers for the Business Model & Segments section.

Every helper is a pure function — no LLM calls.  These are invoked *before*
prompt construction so the prompt already contains resolved tiers and
constraints.
"""

from __future__ import annotations

from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


# ── Segments tier resolution ─────────────────────────────────────────────────


def resolve_segments_tier(
    segments: list[dict[str, Any]] | None,
) -> tuple[Literal["tier_a", "tier_b", "tier_c"], Confidence]:
    """
    Determine segment display tier and confidence.

    Tier A: revenue_mix_pct exists for ≥2 segments -> high confidence
    Tier B: segments list exists but no % mix -> medium confidence
    Tier C: no segments provided -> low confidence (will be inferred)
    """
    if not segments or not isinstance(segments, list):
        return "tier_c", "low"

    valid = [s for s in segments if isinstance(s, dict)]
    if len(valid) < 2:
        return "tier_c", "low"

    has_mix = sum(
        1
        for s in valid
        if s.get("revenue_mix_pct") is not None or s.get("mix_pct") is not None
    )
    if has_mix >= 2:
        return "tier_a", "high"

    return "tier_b", "medium"


# ── Profit mix rule ──────────────────────────────────────────────────────────


def strip_profit_mix_if_missing(
    segments: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    If profit mix data is absent for a segment, ensure profit_mix_pct and
    profit_basis are explicitly set to None.  Never infer profit mix.
    """
    if not segments:
        return []
    result: list[dict[str, Any]] = []
    for seg in segments:
        if not isinstance(seg, dict):
            continue
        out = dict(seg)
        if out.get("profit_mix_pct") is None:
            out["profit_mix_pct"] = None
            out["profit_basis"] = None
        result.append(out)
    return result


# ── Unit economics applicability ─────────────────────────────────────────────

_UNIT_ECON_KEYS = frozenset({
    "arpu",
    "churn",
    "cac",
    "ltv",
    "nrr",
    "grr",
    "utilization",
    "same_store_sales",
    "paid_subs",
    "dau",
    "mau",
    "dau_mau",
    "backlog",
    "net_revenue_retention",
    "gross_revenue_retention",
    "customer_acquisition_cost",
    "lifetime_value",
    "average_revenue_per_user",
})


def resolve_unit_economics(
    inputs: dict[str, Any],
) -> tuple[bool, list[dict[str, Any]], Confidence]:
    """
    Determine if unit economics are applicable and extract provided metrics.

    Returns (applicable, metrics_list, confidence).
    applicable = True only if at least one recognised metric key is provided.
    """
    unit_econ = inputs.get("unit_economics") or {}
    if not isinstance(unit_econ, dict):
        unit_econ = {}

    metrics: list[dict[str, Any]] = []

    # Check explicit metrics dict
    for key in _UNIT_ECON_KEYS:
        val = unit_econ.get(key) or inputs.get(key)
        if val is not None and str(val).strip():
            metrics.append({
                "label": _format_metric_label(key),
                "value": str(val),
                "as_of": unit_econ.get("as_of") or inputs.get("as_of"),
            })

    # Also check a pre-built metrics list
    raw_metrics = unit_econ.get("metrics") or inputs.get("unit_metrics") or []
    if isinstance(raw_metrics, list):
        for m in raw_metrics:
            if isinstance(m, dict) and m.get("label") and m.get("value"):
                metrics.append({
                    "label": str(m["label"]),
                    "value": str(m["value"]),
                    "as_of": m.get("as_of"),
                })

    # Cap at 6
    metrics = metrics[:6]

    if metrics:
        return True, metrics, "high"
    return False, [], "low"


def _format_metric_label(key: str) -> str:
    """Convert snake_case key to title-cased label."""
    return key.replace("_", " ").title()


# ── Business model confidence ────────────────────────────────────────────────


def resolve_business_model_confidence(
    inputs: dict[str, Any],
) -> tuple[Confidence, str | None]:
    """
    Determine business model confidence from available data.

    - If explicit revenue_flow or business model data is provided -> high
    - If only sector/industry/description -> medium (must infer flow)
    - Pricing/contract notes only included if explicitly present
    """
    bm = inputs.get("business_model") or {}
    has_flow = bool(bm.get("revenue_flow"))
    has_description = bool(
        inputs.get("company_description")
        or inputs.get("business_description")
        or bm.get("description")
    )

    if has_flow:
        return "high", None
    if has_description:
        return "medium", "Revenue flow inferred from business description"
    return "medium", "Revenue flow inferred from sector and limited context"


def has_pricing_notes(inputs: dict[str, Any]) -> bool:
    """Return True only if pricing/contract notes are explicitly provided."""
    bm = inputs.get("business_model") or {}
    notes = bm.get("pricing_contract_notes") or bm.get("pricing_notes") or []
    if isinstance(notes, list) and notes:
        return True
    if isinstance(notes, str) and notes.strip():
        return True
    return False


# ── Low-confidence flag ──────────────────────────────────────────────────────


def compute_low_confidence_flag(
    bm_confidence: str,
    seg_confidence: str,
    ue_confidence: str,
    seg_mode: str,
) -> bool:
    """
    True if any module has low confidence OR segments mode is tier_c.
    """
    if "low" in (bm_confidence, seg_confidence, ue_confidence):
        return True
    if seg_mode == "tier_c":
        return True
    return False
