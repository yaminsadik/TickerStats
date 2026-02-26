"""
Deterministic fallback helpers for Investment Thesis Variant View.

All functions are pure — no LLM calls, no side effects.
"""

from __future__ import annotations

import re
from typing import Literal, Optional

Position = Literal["long", "short", "not_specified"]
Confidence = Literal["high", "medium", "low"]

_PLACEHOLDER_PATTERNS = re.compile(
    r"\bTBD\b|\$X\b|XX%|lorem|placeholder|insert here|fill in",
    re.IGNORECASE,
)


def normalize_position(raw: Optional[str]) -> Position:
    """Normalize a raw position string to a valid Position literal."""
    if not raw:
        return "not_specified"
    cleaned = raw.strip().lower()
    if cleaned in ("long", "short"):
        return cleaned  # type: ignore[return-value]
    return "not_specified"


def build_variant_deltas(
    market_believes: Optional[str],
    we_believe: Optional[str],
) -> list[dict[str, str]]:
    """
    Split user-provided market/we beliefs into up to 3 paired deltas.

    Splitting strategy:
    - Prefer newline-separated bullets
    - Else split on semicolons
    - If neither, treat as a single delta
    """
    if not market_believes or not we_believe:
        return []

    def _split(text: str) -> list[str]:
        # Try newline-separated bullets first
        lines = [ln.strip().lstrip("-•*").strip() for ln in text.strip().splitlines()]
        lines = [ln for ln in lines if ln]
        if len(lines) > 1:
            return lines[:3]
        # Try semicolons
        parts = [p.strip() for p in text.split(";")]
        parts = [p for p in parts if p]
        if len(parts) > 1:
            return parts[:3]
        return [text.strip()]

    market_parts = _split(market_believes)
    we_parts = _split(we_believe)

    # Pair up: zip to shorter list length, cap at 3
    count = min(len(market_parts), len(we_parts), 3)
    deltas = []
    for i in range(count):
        deltas.append({
            "market_believes": market_parts[i],
            "we_believe": we_parts[i],
        })

    # If lengths differ and we only have 1 pair, still return it
    if not deltas and market_believes.strip() and we_believe.strip():
        deltas.append({
            "market_believes": market_believes.strip(),
            "we_believe": we_believe.strip(),
        })

    return deltas


def select_pillars(pillars: Optional[list[str]]) -> list[str]:
    """Trim empty entries and cap at 5."""
    if not pillars:
        return []
    cleaned = [p.strip() for p in pillars if p and p.strip()]
    return cleaned[:5]


def select_flip_conditions(items: Optional[list[str]]) -> list[str]:
    """Trim empty entries and cap at 2."""
    if not items:
        return []
    cleaned = [i.strip() for i in items if i and i.strip()]
    return cleaned[:2]


def compute_confidence(
    thesis_sentence: Optional[str],
    pillars: list[str],
    variant_deltas: list[dict],
) -> Confidence:
    """
    Deterministic confidence computation.

    - high: sentence present AND >=3 pillars AND >=1 variant delta
    - medium: sentence present AND >=2 pillars
    - low: otherwise
    """
    has_sentence = bool(thesis_sentence and thesis_sentence.strip())
    pillar_count = len(pillars)
    delta_count = len(variant_deltas)

    if has_sentence and pillar_count >= 3 and delta_count >= 1:
        return "high"
    if has_sentence and pillar_count >= 2:
        return "medium"
    return "low"


def compute_low_confidence_flag(
    confidence: Confidence,
    thesis_sentence: Optional[str],
    pillars: list[str],
) -> bool:
    """
    True if confidence is low, pillars < 2, or thesis_sentence is missing.
    """
    if confidence == "low":
        return True
    if len(pillars) < 2:
        return True
    if not thesis_sentence or not thesis_sentence.strip():
        return True
    return False


def reject_placeholder(text: Optional[str]) -> bool:
    """Return True if text contains placeholder patterns like TBD, $X, XX%, lorem, etc."""
    if not text:
        return False
    return bool(_PLACEHOLDER_PATTERNS.search(text))


def sanitize_list(items: list[str]) -> list[str]:
    """Remove items that contain placeholder text."""
    return [item for item in items if not reject_placeholder(item)]
