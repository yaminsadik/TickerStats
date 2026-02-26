"""
Render structured OverviewOutput → slide-ready blocks.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert OverviewOutput dict to 2-3 standard slides."""
    slides = []
    
    # Slide 1: Business Overview
    biz_desc = out.get("business_description", {})
    bullets_1 = []
    
    core = biz_desc.get("core_value_proposition", "")
    if core:
        bullets_1.append(_bullet(core))
    
    what_they_do = biz_desc.get("what_they_do", [])
    for item in what_they_do[:2]:  # max 2 to save space
        bullets_1.append(_bullet(f"What: {item}"))
    
    who_they_serve = biz_desc.get("who_they_serve", [])
    if who_they_serve and len(bullets_1) < _MAX_BULLETS_PER_SLIDE:
        bullets_1.append(_bullet(f"Who: {', '.join(who_they_serve)}"))
    
    notes_1 = []
    if biz_desc.get("notes"):
        notes_1.append(f"Notes: {biz_desc['notes']}")
    
    slides.append({
        "slide_id": "overview_1",
        "title": "Company Overview",
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
    
    # Slide 2: Why Now
    why_now = out.get("why_now", {})
    bullets_2 = []
    
    thesis = why_now.get("thesis_statement", "")
    if thesis:
        bullets_2.append(_bullet(f"Thesis: {thesis}"))
    
    timing = why_now.get("timing_factors", [])
    for factor in timing[:3]:
        if len(bullets_2) < _MAX_BULLETS_PER_SLIDE:
            bullets_2.append(_bullet(factor))
    
    notes_2 = []
    if why_now.get("notes"):
        notes_2.append(f"Notes: {why_now['notes']}")
    
    slides.append({
        "slide_id": "overview_2",
        "title": "Why Now",
        "bullets": bullets_2[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_2) if notes_2 else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    })
    
    # Slide 3: Catalysts
    catalysts = out.get("catalysts", {})
    bullets_3 = []
    
    near_term = catalysts.get("near_term", [])
    for cat in near_term:
        if len(bullets_3) < _MAX_BULLETS_PER_SLIDE:
            bullets_3.append(_bullet(f"Near-term: {cat}"))
    
    medium_term = catalysts.get("medium_term", [])
    for cat in medium_term:
        if len(bullets_3) < _MAX_BULLETS_PER_SLIDE:
            bullets_3.append(_bullet(f"Medium-term: {cat}"))
    
    notes_3 = []
    if catalysts.get("notes"):
        notes_3.append(f"Notes: {catalysts['notes']}")
    
    low_flag = out.get("low_confidence_flag", False)
    if low_flag:
        notes_3.append("Low confidence: limited data available")
    
    slides.append({
        "slide_id": "overview_3",
        "title": "Investment Catalysts",
        "bullets": bullets_3[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_3) if notes_3 else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    })
    
    return slides
