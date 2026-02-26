"""
Deterministic fallback helpers for the Management, Ownership & Governance
section.

Every helper is a pure function that returns resolved values + confidence.
No LLM calls — these run during postprocess to enforce the
"never fabricate" contract.
"""

from __future__ import annotations

import re
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]

# ── Fabrication detection ────────────────────────────────────────────────────

_FABRICATED_PATTERN = re.compile(
    r"\$X|\bX%|\bXX\b|\bN/A\b|\bTBD\b|\bunknown\b",
    re.IGNORECASE,
)

_SPECULATION_PATTERN = re.compile(
    r"\blikely\b|\bprobably\b|\bsuspected\b",
    re.IGNORECASE,
)


def is_fabricated(text: str | None) -> bool:
    """Return True if text looks like a fabricated placeholder."""
    if not text:
        return False
    return bool(_FABRICATED_PATTERN.search(text))


def has_speculation(text: str | None) -> bool:
    """Return True if text contains speculative language."""
    if not text:
        return False
    return bool(_SPECULATION_PATTERN.search(text))


# ── Management fallbacks ─────────────────────────────────────────────────────

def resolve_management(mgmt: dict[str, Any]) -> dict[str, Any]:
    """
    Apply deterministic fallback rules to management data.

    - If executives list missing -> executives=[]
    - If comp structure missing -> incentives=[] and add notes, confidence <= medium
    """
    mgmt = dict(mgmt)  # shallow copy

    # Executives
    if not mgmt.get("executives"):
        mgmt["executives"] = []

    # Track record: filter out fabricated entries
    track = mgmt.get("track_record", [])
    mgmt["track_record"] = [t for t in track if not is_fabricated(t)]

    # Incentives
    incentives = mgmt.get("incentives")
    if not incentives:
        mgmt["incentives"] = []
        existing_notes = mgmt.get("notes") or ""
        if "incentive" not in existing_notes.lower():
            mgmt["notes"] = (
                (existing_notes + "; " if existing_notes else "")
                + "incentive structure not provided"
            )
        # Cap confidence at medium
        if mgmt.get("confidence") == "high":
            mgmt["confidence"] = "medium"

    # Alignment summary: filter fabricated entries
    alignment = mgmt.get("alignment_summary", [])
    mgmt["alignment_summary"] = [a for a in alignment if not is_fabricated(a)]

    return mgmt


# ── Ownership fallbacks ──────────────────────────────────────────────────────

def resolve_ownership(own: dict[str, Any]) -> dict[str, Any]:
    """
    Apply deterministic fallback rules to ownership data.

    - If holders missing -> top_holders=[], confidence low, notes set
    - If activist not provided -> activist_presence=None (do not speculate)
    """
    own = dict(own)  # shallow copy

    holders = own.get("top_holders")
    if not holders:
        own["top_holders"] = []
        own["confidence"] = "low"
        existing_notes = own.get("notes") or ""
        if "holder data" not in existing_notes.lower():
            own["notes"] = (
                (existing_notes + "; " if existing_notes else "")
                + "holder data not provided"
            )

    # Never speculate on activist presence
    activist = own.get("activist_presence")
    if activist and has_speculation(activist):
        own["activist_presence"] = None

    return own


# ── Governance fallbacks ─────────────────────────────────────────────────────

# Deterministic severity floor by flag type
_SEVERITY_FLOORS: dict[str, str] = {
    "dual_class": "medium",
    "insider_control": "medium",
    "auditor_change": "medium",
    "related_party": "medium",
}

_SEVERITY_RANK = {"low": 0, "medium": 1, "high": 2}


def _apply_severity_floor(flag: dict[str, Any]) -> dict[str, Any]:
    """Ensure severity meets the deterministic floor for its flag_type."""
    flag = dict(flag)
    flag_type = flag.get("flag_type", "other")
    floor = _SEVERITY_FLOORS.get(flag_type)
    if floor:
        current = flag.get("severity", "low")
        if _SEVERITY_RANK.get(current, 0) < _SEVERITY_RANK.get(floor, 0):
            flag["severity"] = floor
    return flag


def resolve_governance(gov: dict[str, Any]) -> dict[str, Any]:
    """
    Apply deterministic fallback rules to governance data.

    - If no flags provided -> flags=[], confidence medium, notes set
    - Severity mapping is deterministic by flag_type
    """
    gov = dict(gov)  # shallow copy

    flags = gov.get("flags")
    if not flags:
        gov["flags"] = []
        # Not low — governance may simply not be disclosed
        if gov.get("confidence") != "medium":
            gov["confidence"] = "medium"
        existing_notes = gov.get("notes") or ""
        if "governance flags" not in existing_notes.lower():
            gov["notes"] = (
                (existing_notes + "; " if existing_notes else "")
                + "governance flags not provided in inputs"
            )
    else:
        # Apply severity floors
        gov["flags"] = [_apply_severity_floor(f) for f in flags]

        # Strip speculation from fact/why_it_matters
        cleaned_flags = []
        for f in gov["flags"]:
            f = dict(f)
            if has_speculation(f.get("fact")):
                # Remove speculative language
                f["fact"] = _SPECULATION_PATTERN.sub("", f["fact"]).strip()
            if has_speculation(f.get("why_it_matters")):
                f["why_it_matters"] = _SPECULATION_PATTERN.sub(
                    "", f["why_it_matters"]
                ).strip()
            cleaned_flags.append(f)
        gov["flags"] = cleaned_flags

    return gov


# ── Composite confidence ─────────────────────────────────────────────────────

def compute_low_confidence_flag(output: dict[str, Any]) -> bool:
    """
    Deterministically compute the low_confidence_flag.

    true if:
      - management.confidence == low OR
      - ownership.confidence == low OR
      - (governance.flags empty AND ownership.top_holders empty)
    """
    mgmt = output.get("management", {})
    own = output.get("ownership", {})
    gov = output.get("governance", {})

    if mgmt.get("confidence") == "low":
        return True
    if own.get("confidence") == "low":
        return True
    if not gov.get("flags") and not own.get("top_holders"):
        return True

    return False
