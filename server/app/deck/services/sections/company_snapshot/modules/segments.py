"""
Segments module — business segment breakdown.

HARD RULE: ONLY segments and mix (or narrative). No customers, no footprint,
no KPI scale.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.company_snapshot.fallbacks import (
    resolve_segments_tier,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute segments context with tiered fallbacks."""
    raw_segments = inputs.get("segments") or []
    has_mix = False

    if isinstance(raw_segments, list):
        has_mix = any(
            seg.get("mix_pct") is not None or seg.get("mix") is not None
            for seg in raw_segments
            if isinstance(seg, dict)
        )

    mode, confidence = resolve_segments_tier(raw_segments or None, has_mix)

    return {
        "segments": raw_segments,
        "has_mix": has_mix,
        "mode": mode,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the segments module."""
    mode = ctx["mode"]
    confidence = ctx["confidence"]

    if mode == "tier_a":
        seg_list = "\n".join(
            f'  - {s.get("name", "Unknown")}: {s.get("mix_pct") or s.get("mix", "?")}%'
            for s in ctx["segments"]
            if isinstance(s, dict)
        )
        instruction = f"""Segments with % mix are available (Tier A):
{seg_list}

INSTRUCTIONS:
- Include mix_pct for each segment. Set mix_basis to "revenue" or "ebitda" based on context.
- Write a one_liner for each (max 15 words).
- Set mode to "tier_a", confidence to "{confidence}"."""

    elif mode == "tier_b":
        seg_list = "\n".join(
            f'  - {s.get("name", "Unknown")}'
            for s in ctx["segments"]
            if isinstance(s, dict)
        )
        instruction = f"""Segments are known but without % mix (Tier B):
{seg_list}

INSTRUCTIONS:
- Set mix_pct to null for each segment. Set mix_basis to null.
- Write a one_liner for each (max 15 words).
- Set mode to "tier_b", confidence to "{confidence}"."""

    else:  # tier_c
        instruction = f"""No segment data provided (Tier C).

INSTRUCTIONS:
- Infer 2-3 plausible primary segments from the company's sector/industry.
- Set mix_pct to null, mix_basis to null.
- Write a one_liner for each (max 15 words).
- Set mode to "tier_c", confidence to "low".
- Add notes: "segments inferred from business description"."""

    return f"""## MODULE: segments
{instruction}

HARD RULES:
- ONLY segments and mix. No customers, no footprint, no KPIs.
- No financial ratios or margins in one_liners.
"""
