"""
Render structured HistoryOutput → slide-ready blocks.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = True) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert HistoryOutput dict to 1-2 standard slides."""
    milestones = out.get("milestones", [])
    slides = []
    
    # Split milestones across 1-2 slides
    for slide_idx in range(2):
        start_idx = slide_idx * _MAX_BULLETS_PER_SLIDE
        end_idx = start_idx + _MAX_BULLETS_PER_SLIDE
        slide_milestones = milestones[start_idx:end_idx]
        
        if not slide_milestones:
            break
        
        bullets = []
        for m in slide_milestones:
            if not isinstance(m, dict):
                continue
            year = m.get("year", "TBD")
            event = m.get("event", "")
            text = f"{year}: {event}"
            bullets.append(_bullet(text, source_needed=m.get("needs_verification", True)))
        
        notes_parts = []
        for m in slide_milestones:
            if isinstance(m, dict) and m.get("why_it_matters"):
                notes_parts.append(f"{m.get('year', 'TBD')}: {m['why_it_matters']}")
        
        verification_items = out.get("verification_items", [])
        if slide_idx == 0 and verification_items:
            notes_parts.insert(0, "VERIFY: " + "; ".join(verification_items[:3]))
        
        slides.append({
            "slide_id": f"history_{slide_idx + 1}",
            "title": "Company Timeline" if slide_idx == 0 else "Company Timeline (cont.)",
            "bullets": bullets,
            "speaker_notes": "\n".join(notes_parts),
            "layout_hints": {
                "style": "timeline",
                "max_bullets": _MAX_BULLETS_PER_SLIDE,
                "suggested_visual": "timeline",
            },
            "flags": {
                "needs_sources": True,
                "contains_numbers": True,
                "is_draft": True,
            },
        })
    
    return slides
