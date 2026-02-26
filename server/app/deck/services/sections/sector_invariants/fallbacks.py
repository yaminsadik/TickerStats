"""
Deterministic fallback helpers for the Sector Invariants section.

Pure functions — no LLM calls.  Used by spec.py postprocess to enforce
data-gating rules and set confidence flags.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.sector_invariants.schemas import Confidence


def any_module_low_confidence(modules: list[dict[str, Any]]) -> bool:
    """Return True if any module has confidence == 'low'."""
    for m in modules:
        if m.get("confidence") == "low":
            return True
    return False


def clamp_bullets(bullets: list[str], min_count: int = 2, max_count: int = 6) -> list[str]:
    """Ensure bullets list is within [min_count, max_count]. Pad or trim."""
    if len(bullets) < min_count:
        # Pad with a generic note rather than fabricating
        while len(bullets) < min_count:
            bullets.append("Additional detail not disclosed in provided inputs.")
    return bullets[:max_count]
