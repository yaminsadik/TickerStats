"""
Footprint module — geographic presence + optional "why it matters".

HARD RULE: ONLY geography and optional single "why it matters" bullet.
"""

from __future__ import annotations

from typing import Any


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute footprint context."""
    raw_fp = inputs.get("footprint") or {}
    if isinstance(raw_fp, dict):
        regions = raw_fp.get("regions")
        why = raw_fp.get("why_it_matters")
    else:
        regions = None
        why = None

    # Determine confidence
    if regions:
        confidence = "high"
    else:
        confidence = "low"

    return {
        "regions": regions,
        "why_it_matters": why,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the footprint module."""
    if ctx["regions"]:
        regions_hint = f"Known regions: {', '.join(ctx['regions'])}"
    else:
        regions_hint = "No regions provided — infer 1-2 plausible regions from context."

    why_hint = ""
    if ctx["why_it_matters"]:
        why_hint = f"\nWhy it matters: {ctx['why_it_matters']}"

    return f"""## MODULE: footprint
{regions_hint}{why_hint}

INSTRUCTIONS:
- regions: list 1 to 5 geographic regions. Use provided values if available.
- why_it_matters: optional single bullet (max 20 words) explaining geographic relevance. Set null if not meaningful.
- Set confidence to "{ctx["confidence"]}". If regions are inferred, use "low".

HARD RULES:
- ONLY geography and optional "why it matters" bullet.
- No revenue, no customers, no segment data, no KPIs.
"""
