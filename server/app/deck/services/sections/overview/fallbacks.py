"""
Deterministic fallback helpers for the Overview section.
"""

from __future__ import annotations

from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


def compute_low_confidence_flag(
    business_desc_conf: str,
    why_now_conf: str,
    catalysts_conf: str,
) -> bool:
    """True if any module has low confidence."""
    return "low" in (business_desc_conf, why_now_conf, catalysts_conf)
