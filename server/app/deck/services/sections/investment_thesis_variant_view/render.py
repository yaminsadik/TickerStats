"""
Render InvestmentThesisVariantViewOutput -> slide-ready blocks.

Converts the structured output into 1-2 slides conforming to
SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes, layout_hints, flags).

Slide 1: Thesis + pillars + variant view (always)
Slide 2: Debates + flip conditions (only for deep decks with content)
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def _build_slide_1(out: dict[str, Any]) -> dict[str, Any]:
    """
    Main thesis slide.

    Title: "{ticker} — Investment Thesis ({Long/Short}, {Horizon})"
    Bullets: thesis sentence, pillars, variant view (packed into 4 bullets max)
    Speaker notes: key_debates, flip_conditions, low-confidence note
    """
    header = out.get("header", {})
    ticker = header.get("ticker", "UNKNOWN")
    position = header.get("position", "not_specified")
    time_horizon = header.get("time_horizon")

    # Build title
    pos_label = position.capitalize() if position != "not_specified" else "N/A"
    horizon_label = time_horizon or "N/A"
    title = f"{ticker} — Investment Thesis ({pos_label}, {horizon_label})"

    bullets: list[dict[str, Any]] = []

    # Thesis sentence (1 bullet)
    thesis = out.get("thesis_sentence")
    if thesis:
        bullets.append(_bullet(thesis))

    # Pillars (up to remaining slots)
    pillars = out.get("thesis_pillars") or []
    remaining = _MAX_BULLETS_PER_SLIDE - len(bullets)
    if pillars and remaining > 0:
        # If we have room for a label + at least 1 pillar, use compact format
        if remaining >= 2:
            pillar_text = "; ".join(pillars[:remaining - 1])
            bullets.append(_bullet(f"Pillars: {pillar_text}"))
            # If more pillars left, add them individually
            for p in pillars[remaining - 1:]:
                if len(bullets) < _MAX_BULLETS_PER_SLIDE:
                    bullets.append(_bullet(p))
        else:
            # Only 1 slot: compact all pillars
            bullets.append(_bullet(f"Pillars: {'; '.join(pillars)}"))

    # Variant view (remaining slots)
    variant_deltas = out.get("variant_deltas") or []
    for delta in variant_deltas:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        market = delta.get("market_believes", "")
        us = delta.get("we_believe", "")
        bullets.append(_bullet(f"Market: {market} vs Us: {us}"))

    # Speaker notes
    notes_parts: list[str] = []

    # Overflow pillars to notes
    visible_pillar_count = min(len(pillars), _MAX_BULLETS_PER_SLIDE - 1) if pillars else 0
    overflow_pillars = pillars[visible_pillar_count:]
    if overflow_pillars:
        notes_parts.append("Additional pillars: " + "; ".join(overflow_pillars))

    # Overflow variant deltas to notes
    visible_delta_count = sum(1 for _ in variant_deltas if len(bullets) <= _MAX_BULLETS_PER_SLIDE)
    overflow_deltas = variant_deltas[min(len(variant_deltas), _MAX_BULLETS_PER_SLIDE - len(bullets) + len(variant_deltas)):]
    for delta in overflow_deltas:
        notes_parts.append(f"Market: {delta.get('market_believes', '')} vs Us: {delta.get('we_believe', '')}")

    # Key debates in notes
    key_debates = out.get("key_debates") or []
    if key_debates:
        notes_parts.append("Key debates: " + "; ".join(key_debates))

    # Flip conditions in notes
    flip_conditions = out.get("flip_conditions") or []
    if flip_conditions:
        notes_parts.append("What would change my mind: " + "; ".join(flip_conditions))

    # Low confidence note
    if out.get("low_confidence_flag"):
        notes_parts.append(
            "Low confidence: missing user thesis inputs (sentence/pillars/variant view)."
        )

    return {
        "slide_id": "investment_thesis_variant_view_1",
        "title": title,
        "bullets": bullets[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": out.get("low_confidence_flag", False),
        },
    }


def _build_slide_2(out: dict[str, Any]) -> dict[str, Any] | None:
    """
    Debates and Disconfirming Conditions slide (optional).

    Only produced if deck_length == "deep" AND there is content.
    """
    key_debates = out.get("key_debates") or []
    flip_conditions = out.get("flip_conditions") or []

    if not key_debates and not flip_conditions:
        return None

    bullets: list[dict[str, Any]] = []
    for debate in key_debates[:3]:
        if len(bullets) < _MAX_BULLETS_PER_SLIDE:
            bullets.append(_bullet(debate))
    for cond in flip_conditions[:2]:
        if len(bullets) < _MAX_BULLETS_PER_SLIDE:
            bullets.append(_bullet(f"Would change mind: {cond}"))

    if not bullets:
        return None

    notes_parts: list[str] = []
    if out.get("low_confidence_flag"):
        notes_parts.append(
            "Low confidence: missing user thesis inputs (sentence/pillars/variant view)."
        )

    return {
        "slide_id": "investment_thesis_variant_view_2",
        "title": "Debates and Disconfirming Conditions",
        "bullets": bullets[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": out.get("low_confidence_flag", False),
        },
    }


def render_to_slides(
    out: dict[str, Any],
    deck_length: str = "standard",
) -> list[dict[str, Any]]:
    """
    Convert InvestmentThesisVariantViewOutput dict to 1-2 slides.

    Slide 2 is only included when deck_length == "deep" AND there is content.
    """
    slides = [_build_slide_1(out)]

    if deck_length == "deep":
        slide2 = _build_slide_2(out)
        if slide2:
            slides.append(slide2)

    return slides
