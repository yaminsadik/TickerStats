"""
What Changed module — discrete recent events + sentiment explanation.

HARD RULE: Only discrete events + sentiment, no invented numbers.
"""

from __future__ import annotations

from typing import Any

from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    resolve_what_changed,
)


def build_context(inputs: dict[str, Any]) -> dict[str, Any]:
    """Pre-compute what-changed context."""
    events, confidence, notes = resolve_what_changed(inputs)

    return {
        "events": events,
        "confidence": confidence,
        "notes": notes,
        "company_name": inputs.get("company_name", ""),
        "ticker": inputs.get("ticker", ""),
    }


def build_prompt_fragment(ctx: dict[str, Any]) -> str:
    """Return the prompt fragment for the what-changed module."""
    parts: list[str] = ["## WHAT CHANGED MODULE"]
    parts.append(
        "BOUNDARY: Only discrete recent events + sentiment explanation. "
        "NO invented numbers, NO fabricated dates, NO operating metric discussion."
    )

    if ctx["events"]:
        parts.append(f"Provided events ({len(ctx['events'])}):")
        for i, e in enumerate(ctx["events"], 1):
            if isinstance(e, dict):
                headline = e.get("headline", "Unknown")
                date = e.get("date", "")
                etype = e.get("type", "other")
                date_str = f" ({date})" if date else ""
                parts.append(f"  {i}. [{etype}]{date_str} {headline}")
    else:
        parts.append(
            "No recent event data provided. Set events to empty list [], "
            "confidence to 'low', and notes to 'No recent event data provided'. "
            "Provide a generic current_sentiment_summary noting data limitations."
        )

    parts.append(f'Set confidence to "{ctx["confidence"]}".')
    parts.append(
        "\nINSTRUCTIONS:\n"
        "- events: 0-6 items. Each must have type, headline, why_it_matters, sentiment_effect.\n"
        "- current_sentiment_summary: 1-2 grounded sentences summarising current investor sentiment.\n"
        "- NEVER fabricate dates or event details. Use only provided data.\n"
        "- For each event, evidence field should reference the data source if available."
    )

    return "\n\n".join(parts)
