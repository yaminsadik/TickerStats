"""
Deterministic fallback helpers for the Risks & Underwriting section.

Every helper is a pure function.  No LLM calls — these run *before* prompt
construction and again during postprocess to enforce determinism.
"""

from __future__ import annotations

import re
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]
QualRank = Literal["high", "medium", "low", "not_provided"]

# ── Placeholder patterns to scrub ────────────────────────────────────────────

_PLACEHOLDER_RE = re.compile(r"\bTBD\b|\?\?|\$X\b|XX%", re.IGNORECASE)


# ── A) normalize_risks ──────────────────────────────────────────────────────

def normalize_risks(raw_list: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    Drop empty rows, trim strings, cap at 8.
    If risk text is missing or empty, drop the row.
    """
    if not raw_list:
        return []

    cleaned: list[dict[str, Any]] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        risk_text = (item.get("risk") or "").strip()
        if not risk_text:
            continue
        cleaned.append({
            "risk": risk_text,
            "impact": normalize_rank(item.get("impact")),
            "probability": normalize_rank(item.get("probability")),
            "leading_indicator": _strip_or_none(item.get("leading_indicator")),
            "mitigant": _strip_or_none(item.get("mitigant")),
        })
        if len(cleaned) >= 8:
            break

    return cleaned


def _strip_or_none(val: Any) -> str | None:
    if val is None:
        return None
    s = str(val).strip()
    return s if s else None


# ── B) normalize_rank ────────────────────────────────────────────────────────

_VALID_RANKS = {"high", "medium", "low"}


def normalize_rank(val: Any) -> QualRank:
    """Map None/empty/invalid -> 'not_provided'; lowercase and validate."""
    if val is None:
        return "not_provided"
    s = str(val).strip().lower()
    if s in _VALID_RANKS:
        return s  # type: ignore[return-value]
    return "not_provided"


# ── C) compute_rank_score ────────────────────────────────────────────────────

_RANK_WEIGHTS: dict[QualRank, int] = {
    "high": 3,
    "medium": 2,
    "low": 1,
    "not_provided": 0,
}


def compute_rank_score(impact: QualRank, probability: QualRank) -> int:
    """
    Deterministic scoring: impact*10 + probability.
    """
    return _RANK_WEIGHTS[impact] * 10 + _RANK_WEIGHTS[probability]


def sort_risks_by_score(risks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Sort risks descending by rank_score.  Stable sort (preserves original
    order for ties).
    """
    return sorted(risks, key=lambda r: r.get("rank_score", 0), reverse=True)


# ── D) item_confidence ───────────────────────────────────────────────────────

def item_confidence(risk: dict[str, Any]) -> Confidence:
    """
    Per-item confidence:
      high   – leading_indicator present AND (impact or probability provided)
      medium – leading_indicator present OR (impact/probability provided)
      low    – otherwise
    """
    has_indicator = bool(risk.get("leading_indicator"))
    has_rank = (
        risk.get("impact", "not_provided") != "not_provided"
        or risk.get("probability", "not_provided") != "not_provided"
    )

    if has_indicator and has_rank:
        return "high"
    if has_indicator or has_rank:
        return "medium"
    return "low"


# ── E) overall_confidence + low_confidence_flag ──────────────────────────────

def overall_confidence(risks: list[dict[str, Any]]) -> tuple[Confidence, bool]:
    """
    Returns (confidence, low_confidence_flag).

    confidence:
      high   – >= 5 risks and none with low item confidence
      medium – >= 3 risks and not mostly low
      low    – otherwise

    low_confidence_flag:
      True if confidence is low OR any item is low OR risks < 3
    """
    n = len(risks)
    if n == 0:
        return "low", True

    item_confs = [r.get("confidence", "low") for r in risks]
    low_count = item_confs.count("low")
    any_low = low_count > 0

    if n >= 5 and not any_low:
        conf: Confidence = "high"
    elif n >= 3 and low_count <= n // 2:
        conf = "medium"
    else:
        conf = "low"

    flag = conf == "low" or any_low or n < 3
    return conf, flag


# ── F) placeholder_scrub ────────────────────────────────────────────────────

def placeholder_scrub(risks: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Remove items containing placeholder patterns (TBD, ??, $X, XX%).
    Returns (cleaned_risks, scrub_notes).
    """
    cleaned: list[dict[str, Any]] = []
    notes: list[str] = []

    for r in risks:
        fields_to_check = [
            r.get("risk", ""),
            r.get("leading_indicator", "") or "",
            r.get("mitigant", "") or "",
        ]
        combined = " ".join(fields_to_check)
        if _PLACEHOLDER_RE.search(combined):
            notes.append(f"Removed placeholder risk: '{r.get('risk', '')[:60]}'")
            continue
        cleaned.append(r)

    return cleaned, notes


# ── Compose full pipeline ────────────────────────────────────────────────────

def apply_fallbacks(raw_risks: list[dict[str, Any]] | None) -> tuple[list[dict[str, Any]], list[str]]:
    """
    Full deterministic pipeline: normalize -> scrub -> score -> sort -> confidence.
    Returns (processed_risks, notes).
    """
    notes: list[str] = []

    # Normalize
    risks = normalize_risks(raw_risks)

    # Placeholder scrub
    risks, scrub_notes = placeholder_scrub(risks)
    notes.extend(scrub_notes)

    # Compute rank_score and item confidence
    for r in risks:
        r["rank_score"] = compute_rank_score(r["impact"], r["probability"])
        r["confidence"] = item_confidence(r)

    # Sort by score (descending, stable)
    risks = sort_risks_by_score(risks)

    return risks, notes
