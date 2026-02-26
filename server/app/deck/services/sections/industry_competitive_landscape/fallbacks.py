"""
Deterministic fallback helpers for the Industry & Competitive Landscape section.

Every helper is a pure function that returns resolved values + confidence.
No LLM calls — these run *before* prompt construction or during postprocess
to enforce the "never fabricate" contract.
"""

from __future__ import annotations

import re
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


# ── Market sizing fallback ───────────────────────────────────────────────────

_FABRICATED_PATTERN = re.compile(
    r"\$X|\bX%|\bXX|\bN/A\b|\bTBD\b|\bunknown\b",
    re.IGNORECASE,
)


def is_fabricated(text: str | None) -> bool:
    """Return True if text looks like a fabricated placeholder."""
    if not text:
        return False
    return bool(_FABRICATED_PATTERN.search(text))


def resolve_market_sizing(
    tam_value: str | None,
    tam_basis: str | None,
    proxy_sizing: list[str] | None,
) -> tuple[dict[str, Any], Confidence]:
    """
    Resolve market sizing, capping confidence if TAM is missing or fabricated.

    Returns (sizing_dict, max_confidence).
    """
    proxies = [p for p in (proxy_sizing or []) if p and not is_fabricated(p)]

    if tam_value and not is_fabricated(tam_value):
        return {
            "tam_value": tam_value,
            "tam_basis": tam_basis,
            "proxy_sizing": proxies[:3],
            "growth_chart_notes": [],
        }, "high"

    # TAM missing — use proxies, cap at medium
    return {
        "tam_value": None,
        "tam_basis": None,
        "proxy_sizing": proxies[:3],
        "growth_chart_notes": [],
    }, "medium"


# ── Competitor fallback ──────────────────────────────────────────────────────

_GENERIC_CATEGORIES = [
    {"name": "Large incumbents", "type": "direct", "why_relevant": "Dominant market share holders in the core market"},
    {"name": "Specialty/niche players", "type": "direct", "why_relevant": "Focused competitors in specific sub-segments"},
    {"name": "Adjacent-market entrants", "type": "adjacent", "why_relevant": "Companies expanding from related markets"},
    {"name": "Technology disruptors", "type": "substitute", "why_relevant": "New entrants leveraging alternative approaches"},
    {"name": "Low-cost alternatives", "type": "substitute", "why_relevant": "Price-focused competitors targeting cost-sensitive segments"},
]


def resolve_competitors(
    competitors: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], Confidence]:
    """
    Resolve competitor set.

    If no real competitors provided, return 3–5 category-level placeholders
    with confidence=low.
    """
    if competitors and len(competitors) >= 3:
        return competitors[:8], "high"

    if competitors and len(competitors) >= 1:
        return competitors, "medium"

    # No competitors at all — use generic categories
    return _GENERIC_CATEGORIES[:5], "low"


# ── Evidence fallback ────────────────────────────────────────────────────────

def resolve_evidence(
    evidence: str | None,
    current_confidence: Confidence,
) -> tuple[str | None, Confidence, str | None]:
    """
    Resolve an evidence field.

    Returns (evidence_or_none, capped_confidence, notes_or_none).
    """
    if evidence and evidence.strip() and not is_fabricated(evidence):
        return evidence.strip(), current_confidence, None

    # No evidence — cap confidence, add note
    capped: Confidence = "low" if current_confidence == "high" else current_confidence
    if capped == "medium":
        capped = "medium"
    return None, capped, "limited disclosure"


# ── Moat fallbacks ───────────────────────────────────────────────────────────

def resolve_moat_pillars(
    pillars: list[dict[str, Any]] | None,
) -> tuple[list[dict[str, Any]], Confidence]:
    """
    Resolve moat pillars.

    Returns (pillars, confidence).
    """
    if not pillars or len(pillars) < 3:
        return pillars or [], "low"

    # Check if any pillar has evidence
    has_evidence = any(p.get("evidence") for p in pillars)
    confidence: Confidence = "high" if has_evidence else "medium"
    return pillars[:5], confidence


# ── Composite confidence ─────────────────────────────────────────────────────

_CONFIDENCE_RANK = {"high": 2, "medium": 1, "low": 0}


def any_module_low_confidence(output: dict[str, Any]) -> bool:
    """Return True if any top-level module has confidence == 'low'."""
    for key in ("market", "competition", "moat", "porters"):
        module = output.get(key, {})
        if module.get("confidence") == "low":
            return True
    return False


def compute_low_confidence_flag(output: dict[str, Any]) -> bool:
    """Deterministically compute the low_confidence_flag."""
    return any_module_low_confidence(output)


def strip_fabricated_values(output: dict[str, Any]) -> dict[str, Any]:
    """
    Walk the output and null-out any values that match fabricated patterns.

    Mutates and returns the dict.
    """
    market = output.get("market", {})
    sizing = market.get("sizing", {})

    if is_fabricated(sizing.get("tam_value")):
        sizing["tam_value"] = None
        sizing["tam_basis"] = None
        market.setdefault("notes", "TAM removed — appeared fabricated")
        if market.get("confidence") == "high":
            market["confidence"] = "medium"

    # Strip fabricated growth chart notes
    gcn = sizing.get("growth_chart_notes", [])
    sizing["growth_chart_notes"] = [n for n in gcn if not is_fabricated(n)]

    # Strip fabricated proxy sizing
    ps = sizing.get("proxy_sizing", [])
    sizing["proxy_sizing"] = [p for p in ps if not is_fabricated(p)]

    return output
