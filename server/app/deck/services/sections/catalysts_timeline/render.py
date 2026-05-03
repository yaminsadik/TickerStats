"""Render CatalystsTimelineOutput -> slide-ready blocks."""

from __future__ import annotations

import re
from typing import Any


_MAX_BULLETS_PER_SLIDE = 4

# Match quarter / half-year / year fragments often comma-joined in LLM timing fields.
_TIMING_TOKEN = re.compile(r"Q[1-4]\s+\d{4}|H[12]\s+\d{4}|FY\s*\d{4}|\b20\d{2}\b", re.I)


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    return {"text": text, "source_needed": source_needed}


def _split_comma_timings(timing: str) -> list[str]:
    """Split a comma-separated timing string into separate windows when date-like."""
    parts = [p.strip() for p in timing.split(",") if p.strip()]
    if len(parts) <= 1:
        return parts
    dated = sum(1 for p in parts if _TIMING_TOKEN.search(p))
    if dated >= 2:
        return parts
    return [timing]


def _expand_catalyst_rows(catalysts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One bullet per timing window — avoids one bracket with comma-joined dates."""
    expanded: list[dict[str, Any]] = []
    for cat in catalysts:
        if not isinstance(cat, dict):
            continue
        timing = cat.get("timing")
        if isinstance(timing, str) and timing.strip():
            windows = _split_comma_timings(timing.strip())
            if len(windows) > 1:
                for window in windows:
                    fork = dict(cat)
                    fork["timing"] = window
                    expanded.append(fork)
                continue
        expanded.append(cat)
    return expanded


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
    raw = out.get("catalysts") or []
    catalysts = _expand_catalyst_rows([c for c in raw if isinstance(c, dict)])
    slides: list[dict[str, Any]] = []

    if not catalysts:
        return slides

    # Slide 1: first 4 catalysts
    slice_1 = catalysts[:_MAX_BULLETS_PER_SLIDE]
    bullets_1 = [_bullet(_format_catalyst(c)) for c in slice_1]

    notes_1: list[str] = []
    for cat in slice_1:
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
        slice_2 = overflow[:_MAX_BULLETS_PER_SLIDE]
        bullets_2 = [_bullet(_format_catalyst(c)) for c in slice_2]
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
