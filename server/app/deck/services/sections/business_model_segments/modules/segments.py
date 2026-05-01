"""
Segments module — segment items, mix, and drivers.

HARD RULE: Only segments, mix %, and drivers. No pricing flow, no customer
types, no unit economics.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.business_model_segments.fallbacks import (
    resolve_segments_tier,
    strip_profit_mix_if_missing,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute segments context with tiered fallbacks."""
    raw_segments = inputs.get("segments") or []
    if not isinstance(raw_segments, list):
        raw_segments = []

    mode, confidence = resolve_segments_tier(raw_segments or None)
    cleaned = strip_profit_mix_if_missing(raw_segments)

    return {
        "segments": cleaned,
        "mode": mode,
        "confidence": confidence,
        "company_name": inputs.get("company_name", ""),
        "sector": inputs.get("sector", ""),
        "industry": inputs.get("industry", ""),
        "description": (
            inputs.get("company_description")
            or inputs.get("business_description")
            or ""
        ),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the segments module."""
    mode = ctx["mode"]
    confidence = ctx["confidence"]

    parts: list[str] = ["## SEGMENTS MODULE"]
    parts.append(
        "BOUNDARY: Only segments, revenue/profit mix %, one-liner per segment, "
        "and 2-4 drivers per segment. No pricing flow, no customer types, no unit econ."
    )

    if mode == "tier_a":
        seg_list = "\n".join(
            f'  - {s.get("name", "Unknown")}: Rev mix {s.get("revenue_mix_pct") or s.get("mix_pct", "?")}%'
            + (f', Profit mix {s["profit_mix_pct"]}%' if s.get("profit_mix_pct") is not None else "")
            for s in ctx["segments"]
            if isinstance(s, dict)
        )
        parts.append(f"Segments with % mix available (Tier A):\n{seg_list}")
        parts.append(
            f'INSTRUCTIONS:\n'
            f'- Include revenue_mix_pct for each segment.\n'
            f'- If profit_mix_pct is provided, include it and set profit_basis. '
            f'If NOT provided, set profit_mix_pct and profit_basis to null.\n'
            f'- Write a one_liner for each segment (max 15 words).\n'
            f'- Provide 2-4 drivers per segment.\n'
            f'- Set mode to "tier_a", confidence to "{confidence}".'
        )

    elif mode == "tier_b":
        seg_list = "\n".join(
            f'  - {s.get("name", "Unknown")}'
            for s in ctx["segments"]
            if isinstance(s, dict)
        )
        parts.append(f"Segments known but without % mix (Tier B):\n{seg_list}")
        parts.append(
            f'INSTRUCTIONS:\n'
            f'- Set revenue_mix_pct to null, profit_mix_pct to null, profit_basis to null.\n'
            f'- Write a one_liner for each segment (max 15 words).\n'
            f'- Provide 2-4 drivers per segment.\n'
            f'- Set mode to "tier_b", confidence to "{confidence}".'
        )

    else:  # tier_c
        parts.append("No segment data provided (Tier C).")
        desc = ctx.get("description", "")
        if desc:
            parts.append(f"Company description for inference: {desc}")
        if ctx.get("industry"):
            parts.append(f"Industry for inference: {ctx['industry']}")
        parts.append(
            'INSTRUCTIONS:\n'
            '- Infer 2-4 plausible primary segments ONLY from the company description, sector, and industry.\n'
            '- If description is missing, keep segments broad and sector-level; do NOT invent unrelated categories.\n'
            '- Set revenue_mix_pct to null, profit_mix_pct to null, profit_basis to null.\n'
            '- Write a one_liner for each (max 15 words).\n'
            '- Provide 2-4 drivers per segment.\n'
            '- Set mode to "tier_c", confidence to "low".\n'
            '- Add notes: "inferred segments".'
        )

    return "\n".join(parts)
