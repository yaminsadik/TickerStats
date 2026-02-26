"""Render InvestmentThesisOutput -> slide-ready blocks."""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    return {"text": text, "source_needed": source_needed}


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert InvestmentThesisOutput dict to 1-2 standard slides."""
    slides: list[dict[str, Any]] = []

    # --- Slide 1: Investment Thesis ---
    bullets_1: list[dict[str, Any]] = []
    thesis = out.get("thesis_sentence")
    if thesis:
        bullets_1.append(_bullet(thesis))

    for pillar in (out.get("pillars") or [])[:3]:  # leave room if thesis used a slot
        if len(bullets_1) < _MAX_BULLETS_PER_SLIDE:
            bullets_1.append(_bullet(pillar))

    notes_1: list[str] = []
    # Put extra pillars in speaker notes
    extra_pillars = (out.get("pillars") or [])[3:]
    if extra_pillars:
        notes_1.append("Additional pillars: " + "; ".join(extra_pillars))

    slides.append({
        "slide_id": "investment_thesis_1",
        "title": "Investment Thesis",
        "bullets": bullets_1[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_1) if notes_1 else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    })

    # --- Slide 2: Variant View ---
    market_view = out.get("market_view")
    variant_view = out.get("variant_view")
    what_changes = out.get("what_changes_mind") or []

    if market_view or variant_view or what_changes:
        bullets_2: list[dict[str, Any]] = []
        if market_view:
            bullets_2.append(_bullet(f"Market believes: {market_view}"))
        if variant_view:
            bullets_2.append(_bullet(f"We believe: {variant_view}"))
        for item in what_changes[:2]:
            if len(bullets_2) < _MAX_BULLETS_PER_SLIDE:
                bullets_2.append(_bullet(f"Would change mind: {item}"))

        slides.append({
            "slide_id": "investment_thesis_2",
            "title": "Variant View",
            "bullets": bullets_2[:_MAX_BULLETS_PER_SLIDE],
            "speaker_notes": "",
            "layout_hints": {
                "style": "two_column",
                "max_bullets": _MAX_BULLETS_PER_SLIDE,
                "suggested_visual": None,
            },
            "flags": {
                "needs_sources": False,
                "contains_numbers": False,
                "is_draft": False,
            },
        })

    return slides
