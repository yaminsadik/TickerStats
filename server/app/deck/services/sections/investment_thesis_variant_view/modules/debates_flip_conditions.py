"""
Debates & Flip Conditions module — key debates and what would change my mind.

Boundary: Only debates and flip conditions derived from user text.
No external claims, no new facts.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.investment_thesis_variant_view.fallbacks import (
    select_flip_conditions,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute debates/flip-conditions context from inputs."""
    thesis = inputs.get("thesis") or {}

    return {
        "flip_conditions": select_flip_conditions(thesis.get("what_changes_mind")),
        "thesis_sentence": thesis.get("thesis_sentence"),
        "market_believes": thesis.get("market_believes"),
        "we_believe": thesis.get("we_believe"),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for debates and flip conditions."""
    parts = ["## MODULE: debates_flip_conditions"]

    if ctx["flip_conditions"]:
        parts.append("\nUser-provided flip conditions (what would change my mind):")
        for item in ctx["flip_conditions"]:
            parts.append(f"  - {item}")
    else:
        parts.append("\nFlip conditions: NOT PROVIDED")

    parts.extend([
        "",
        "INSTRUCTIONS:",
        "- flip_conditions: return user's conditions, polished. Max 2. Do NOT invent new ones.",
        "- key_debates: derive 0-3 key debates ONLY from the user-provided thesis sentence,",
        "  variant view, and flip conditions. These should highlight the core analytical tension.",
        "- If user inputs are sparse, return an empty key_debates list.",
        "",
        "HARD RULES:",
        "- Do NOT introduce external claims, catalysts, or factual statements not in user inputs.",
        "- key_debates must be derivable from the user's own text — reframe, do not fabricate.",
    ])

    return "\n".join(parts)
