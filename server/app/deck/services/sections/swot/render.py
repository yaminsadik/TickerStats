"""
Render structured SWOTOutput → slide-ready blocks.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert SWOTOutput dict to 2 standard slides."""
    slides = []
    
    # Slide 1: Strengths & Weaknesses (Internal Factors)
    strengths = out.get("strengths", [])
    weaknesses = out.get("weaknesses", [])
    
    bullets_1 = []
    for s in strengths[:2]:
        if isinstance(s, dict):
            point = s.get("point", "")
            bullets_1.append(_bullet(f"S: {point}"))
    
    for w in weaknesses[:2]:
        if isinstance(w, dict):
            point = w.get("point", "")
            bullets_1.append(_bullet(f"W: {point}"))
    
    notes_1 = []
    for s in strengths:
        if isinstance(s, dict) and s.get("justification"):
            notes_1.append(f"S - {s['point']}: {s['justification']}")
    for w in weaknesses:
        if isinstance(w, dict) and w.get("justification"):
            notes_1.append(f"W - {w['point']}: {w['justification']}")
    
    slides.append({
        "slide_id": "swot_1",
        "title": "Strengths & Weaknesses",
        "bullets": bullets_1[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_1),
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
    
    # Slide 2: Opportunities & Threats (External Factors)
    opportunities = out.get("opportunities", [])
    threats = out.get("threats", [])
    
    bullets_2 = []
    for o in opportunities[:2]:
        if isinstance(o, dict):
            point = o.get("point", "")
            bullets_2.append(_bullet(f"O: {point}"))
    
    for t in threats[:2]:
        if isinstance(t, dict):
            point = t.get("point", "")
            bullets_2.append(_bullet(f"T: {point}"))
    
    notes_2 = []
    for o in opportunities:
        if isinstance(o, dict) and o.get("justification"):
            notes_2.append(f"O - {o['point']}: {o['justification']}")
    for t in threats:
        if isinstance(t, dict) and t.get("justification"):
            notes_2.append(f"T - {t['point']}: {t['justification']}")
    
    notes = out.get("notes")
    if notes:
        notes_2.append(f"Notes: {notes}")
    
    slides.append({
        "slide_id": "swot_2",
        "title": "Opportunities & Threats",
        "bullets": bullets_2[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_2),
        "layout_hints": {
            "style": "two_column",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    })
    
    return slides
