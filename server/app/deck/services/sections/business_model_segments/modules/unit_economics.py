"""
Unit Economics module — metrics panel when applicable.

HARD RULE: Only metrics panel. No narrative moat claims, no invented values.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.business_model_segments.fallbacks import (
    resolve_unit_economics,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute unit economics context."""
    applicable, metrics, confidence = resolve_unit_economics(inputs)
    return {
        "applicable": applicable,
        "metrics": metrics,
        "confidence": confidence,
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the unit_economics module."""
    parts: list[str] = ["## UNIT ECONOMICS MODULE"]
    parts.append(
        "BOUNDARY: Only metrics panel. No narrative moat claims, no invented values. "
        "Only use metrics that are explicitly provided in the data."
    )

    if ctx["applicable"]:
        metrics_str = "\n".join(
            f'  - {m["label"]}: {m["value"]}'
            + (f' (as of {m["as_of"]})' if m.get("as_of") else "")
            for m in ctx["metrics"]
        )
        parts.append(f"Provided unit economics metrics:\n{metrics_str}")
        parts.append(
            f'INSTRUCTIONS:\n'
            f'- Set applicable to true.\n'
            f'- Include the provided metrics (max 6). Use exact values — do NOT modify.\n'
            f'- Set confidence to "{ctx["confidence"]}".\n'
            f'- Do NOT add any metrics that are not in the provided data.'
        )
    else:
        parts.append("No unit economics metrics provided.")
        parts.append(
            'INSTRUCTIONS:\n'
            '- Set applicable to false.\n'
            '- Set metrics to empty list [].\n'
            '- Set confidence to "low".\n'
            '- Do NOT invent or estimate any metrics.'
        )

    return "\n".join(parts)
