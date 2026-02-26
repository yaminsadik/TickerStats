"""
Deterministic fallback helpers for the Key Drivers & KPIs section.

Every helper is a pure function that returns resolved values + confidence.
No LLM calls — these run *before* prompt construction and again in
postprocess to recompute flags deterministically.
"""

from __future__ import annotations

from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


# ── Sector-safe driver map (used ONLY when inputs contain these metrics) ─────

SECTOR_DRIVER_SUGGESTIONS: dict[str, list[str]] = {
    "saas": ["ARR", "NRR", "churn", "ARPU"],
    "software": ["ARR", "NRR", "churn", "ARPU"],
    "retail": ["same-store sales", "traffic", "ticket size"],
    "consumer discretionary": ["same-store sales", "traffic", "ticket size"],
    "industrials": ["backlog", "utilization", "price/volume"],
    "banks": ["NIM", "NPLs", "CET1"],
    "financials": ["NIM", "NPLs", "CET1", "AUM", "net flows", "fee rate"],
    "asset management": ["AUM", "net flows", "fee rate"],
    "insurance": ["combined ratio", "loss ratio", "premium growth"],
    "healthcare": ["patient volume", "reimbursement rate", "utilization"],
    "telecom": ["ARPU", "churn", "subscriber adds"],
    "real estate": ["occupancy rate", "NOI", "same-property growth"],
}


def _normalize_sector(sector: str | None) -> str:
    """Lowercase + strip for matching."""
    if not sector:
        return ""
    return sector.strip().lower()


# ── KPI selection fallback ───────────────────────────────────────────────────

_MIN_KPIS = 3
_MAX_KPIS = 5


def select_kpis_from_inputs(
    inputs: dict[str, Any],
) -> tuple[list[dict[str, Any]], Confidence, str | None]:
    """
    Select KPIs from available inputs using a deterministic priority cascade.

    Returns (kpi_hints, confidence, notes).
    kpi_hints is a list of dicts with at minimum {"name": str}.
    """
    # 1. Explicit KPI list provided by caller
    explicit_kpis = inputs.get("kpis") or inputs.get("key_metrics") or []
    if isinstance(explicit_kpis, list) and len(explicit_kpis) > 0:
        selected = _normalize_kpi_list(explicit_kpis)[:_MAX_KPIS]
        if len(selected) >= _MIN_KPIS:
            return selected, "high", None
        if selected:
            return selected, "low", "insufficient KPI disclosure provided"
        # Fall through if normalisation produced nothing

    # 2. Extract from business_model_segments inputs (unit economics)
    bm_metrics = _extract_from_business_model(inputs)
    if len(bm_metrics) >= _MIN_KPIS:
        return bm_metrics[:_MAX_KPIS], "medium", None
    if bm_metrics:
        # supplement with sector suggestions if they appear in inputs
        combined = _dedupe_by_name(bm_metrics + _sector_suggestions_in_inputs(inputs))
        if len(combined) >= _MIN_KPIS:
            return combined[:_MAX_KPIS], "medium", None
        return combined[:_MAX_KPIS], "low", "insufficient KPI disclosure provided"

    # 3. Sector-safe suggestions only if they appear in inputs text
    sector_kpis = _sector_suggestions_in_inputs(inputs)
    if len(sector_kpis) >= _MIN_KPIS:
        return sector_kpis[:_MAX_KPIS], "medium", "KPIs inferred from sector-typical drivers present in inputs"
    if sector_kpis:
        return sector_kpis[:_MAX_KPIS], "low", "insufficient KPI disclosure provided"

    # 4. Nothing found
    return [], "low", "insufficient KPI disclosure provided"


def _normalize_kpi_list(raw: list) -> list[dict[str, Any]]:
    """Convert a mixed list of str / dict into [{name: ...}] dicts."""
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, str) and item.strip():
            out.append({"name": item.strip()})
        elif isinstance(item, dict) and item.get("name"):
            out.append(item)
    return out


def _extract_from_business_model(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """Pull unit-economics / operational metrics from business_model data."""
    bm = inputs.get("business_model_segments") or inputs.get("business_model") or {}
    metrics: list[dict[str, Any]] = []

    # Check for nested metrics list
    for key in ("unit_economics", "kpis", "key_metrics", "operational_metrics"):
        items = bm.get(key) if isinstance(bm, dict) else None
        if isinstance(items, list):
            metrics.extend(_normalize_kpi_list(items))

    return _dedupe_by_name(metrics)


def _sector_suggestions_in_inputs(inputs: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Return sector-typical driver names ONLY if they appear somewhere in the
    inputs text blob. Never invent KPIs that aren't grounded in the inputs.
    """
    sector = _normalize_sector(inputs.get("sector"))
    candidates: list[str] = []
    for key, drivers in SECTOR_DRIVER_SUGGESTIONS.items():
        if key in sector:
            candidates = drivers
            break

    if not candidates:
        return []

    # Build a searchable text blob from all string values in inputs
    text_blob = _inputs_text_blob(inputs).lower()
    found: list[dict[str, Any]] = []
    for driver in candidates:
        if driver.lower() in text_blob:
            found.append({"name": driver})

    return found


def _inputs_text_blob(inputs: dict[str, Any]) -> str:
    """Recursively extract all string values from inputs into one blob."""
    parts: list[str] = []
    _collect_strings(inputs, parts)
    return " ".join(parts)


def _collect_strings(obj: Any, acc: list[str]) -> None:
    if isinstance(obj, str):
        acc.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            _collect_strings(v, acc)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _collect_strings(v, acc)


def _dedupe_by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Deduplicate by lowercased name, keeping first occurrence."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = item.get("name", "").strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


# ── Disclosure location fallback ─────────────────────────────────────────────

def resolve_disclosure(
    kpi_name: str,
    disclosure_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Return a DisclosureRef dict for the given KPI.

    If no data is provided -> source_type="not_provided" with null fields.
    Never guesses page numbers or sections.
    """
    if not disclosure_data:
        return {
            "source_type": "not_provided",
            "description": None,
            "page_or_section": None,
            "link_label": None,
        }

    source_type = disclosure_data.get("source_type", "not_provided")
    valid_sources = {
        "10-K", "10-Q", "earnings_release", "earnings_deck",
        "investor_presentation", "other", "not_provided",
    }
    if source_type not in valid_sources:
        source_type = "other"

    return {
        "source_type": source_type,
        "description": disclosure_data.get("description"),
        "page_or_section": disclosure_data.get("page_or_section"),
        "link_label": disclosure_data.get("link_label"),
    }


# ── Confidence / low-confidence flag ─────────────────────────────────────────

def compute_low_confidence_flag(
    confidence: str,
    kpis: list[dict[str, Any]],
) -> bool:
    """
    Deterministically compute low_confidence_flag.

    True if:
      - confidence == "low", OR
      - any KPI has disclosure.source_type == "not_provided"
    """
    if confidence == "low":
        return True
    for kpi in kpis:
        disclosure = kpi.get("disclosure") or {}
        if isinstance(disclosure, dict) and disclosure.get("source_type") == "not_provided":
            return True
    return False


def compute_confidence(kpi_count: int, any_missing_disclosure: bool) -> Confidence:
    """Determine overall confidence from KPI count and disclosure completeness."""
    if kpi_count < _MIN_KPIS:
        return "low"
    if any_missing_disclosure:
        return "medium"
    return "high"
