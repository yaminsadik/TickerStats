"""Render CatalystsTimelineOutput -> slide-ready blocks."""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    return {"text": text, "source_needed": source_needed}


def _format_catalyst(cat: dict[str, Any]) -> str:
    """Format a single catalyst as a bullet string."""
    name = cat.get("name", "Unknown catalyst")
    timing = cat.get("timing")
    mechanism = cat.get("mechanism")
    impact = cat.get("impact_description")

    parts = []
    if timing:
        parts.append(f"[{timing}]")
    parts.append(name)
    detail = mechanism or impact
    if detail:
        parts.append(f"— {detail}")
    return " ".join(parts)


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert CatalystsTimelineOutput dict to 1-2 standard slides."""
    catalysts = out.get("catalysts") or []
    slides: list[dict[str, Any]] = []

    if not catalysts:
        return slides

    # Slide 1: first 4 catalysts
    bullets_1 = [_bullet(_format_catalyst(c)) for c in catalysts[:_MAX_BULLETS_PER_SLIDE]]

    notes_1: list[str] = []
    for cat in catalysts[:_MAX_BULLETS_PER_SLIDE]:
        mechanism = cat.get("mechanism")
        impact = cat.get("impact_description")
        if mechanism and impact:
            notes_1.append(f"{cat.get('name', '')}: {mechanism}. Impact: {impact}")
        elif mechanism:
            notes_1.append(f"{cat.get('name', '')}: {mechanism}")

    slides.append({
        "slide_id": "catalysts_timeline_1",
        "title": "Catalyst Timeline",
        "bullets": bullets_1,
        "speaker_notes": "\n".join(notes_1) if notes_1 else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "timeline",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    })

    # Slide 2: overflow catalysts (if >4)
    overflow = catalysts[_MAX_BULLETS_PER_SLIDE:]
    if overflow:
        bullets_2 = [_bullet(_format_catalyst(c)) for c in overflow[:_MAX_BULLETS_PER_SLIDE]]
        slides.append({
            "slide_id": "catalysts_timeline_2",
            "title": "Catalyst Timeline (cont.)",
            "bullets": bullets_2,
            "speaker_notes": "",
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

    return slides
