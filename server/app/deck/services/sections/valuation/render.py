"""Render ValuationOutput -> slide-ready blocks."""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    return {"text": text, "source_needed": source_needed}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        t = value.strip().lower()
        if not t or t in {"null", "none", "n/a", "undefined"}:
            return False
    return True


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert ValuationOutput dict to 1-2 standard slides."""
    slides: list[dict[str, Any]] = []

    # --- Slide 1: Valuation Framework ---
    bullets_1: list[dict[str, Any]] = []

    summary = out.get("methodology_summary")
    if summary:
        bullets_1.append(_bullet(summary))

    for vp in (out.get("valuation_points") or []):
        if len(bullets_1) >= _MAX_BULLETS_PER_SLIDE:
            break
        method = vp.get("method", "")
        desc = vp.get("description", "")
        implied = vp.get("implied_range")
        if not _present(method):
            continue
        parts = [f"{method}:"]
        if _present(desc):
            parts.append(str(desc))
        if _present(implied):
            parts.append(f"({implied})")
            bullets_1.append(_bullet(" ".join(parts), source_needed=True))
        elif len(parts) > 1:
            bullets_1.append(_bullet(" ".join(parts), source_needed=False))
        else:
            bullets_1.append(_bullet(method, source_needed=False))

    notes_1: list[str] = []
    # Put overflow valuation points in speaker notes
    overflow = (out.get("valuation_points") or [])[max(0, _MAX_BULLETS_PER_SLIDE - 1):]
    for vp in overflow:
        notes_1.append(f"{vp.get('method', '')}: {vp.get('description', '')}")

    slides.append({
        "slide_id": "valuation_1",
        "title": "Valuation Framework",
        "bullets": bullets_1[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_1) if notes_1 else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": any(b.get("source_needed") for b in bullets_1),
            "contains_numbers": True,
            "is_draft": False,
        },
    })

    # --- Slide 2: Price Target Bridge ---
    pt = out.get("price_target_summary")
    bullets_2: list[dict[str, Any]] = []
    if _present(pt):
        bullets_2.append(_bullet(str(pt), source_needed=True))

    for vp in (out.get("valuation_points") or []):
        if len(bullets_2) >= _MAX_BULLETS_PER_SLIDE:
            break
        method = vp.get("method", "")
        implied = vp.get("implied_range")
        if _present(implied) and _present(method):
            bullets_2.append(_bullet(
                f"{method}: {implied}",
                source_needed=True,
            ))

    if bullets_2:
        slides.append({
            "slide_id": "valuation_2",
            "title": "Price Target Bridge",
            "bullets": bullets_2[:_MAX_BULLETS_PER_SLIDE],
            "speaker_notes": "",
            "layout_hints": {
                "style": "bullets",
                "max_bullets": _MAX_BULLETS_PER_SLIDE,
                "suggested_visual": "waterfall",
            },
            "flags": {
                "needs_sources": True,
                "contains_numbers": True,
                "is_draft": False,
            },
        })

    return slides
