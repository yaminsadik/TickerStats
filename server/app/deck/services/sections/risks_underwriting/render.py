"""
Render structured RisksUnderwritingOutput -> slide-ready blocks.

Converts the rich JSON into 1-2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA.

Slide 1: Risk register (5-8 risks)
Slide 2: Risk Monitoring (optional, deep only, overflow)
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def _format_risk_bullet(risk: dict[str, Any]) -> str:
    """
    Format a risk as one line:
      "{Impact}/{Prob} — {Risk}. Watch: {Leading indicator}. Mitigant: {Mitigant}"
    Rules:
      - If impact/prob missing, use "—" and omit tags.
      - If leading_indicator missing, render "Watch: not provided"
      - If mitigant missing, omit mitigant clause
    """
    impact = risk.get("impact", "not_provided")
    prob = risk.get("probability", "not_provided")

    if impact == "not_provided" and prob == "not_provided":
        prefix = "—"
    elif impact == "not_provided":
        prefix = f"—/{prob}"
    elif prob == "not_provided":
        prefix = f"{impact}/—"
    else:
        prefix = f"{impact}/{prob}"

    risk_text = risk.get("risk", "Unknown risk")
    indicator = risk.get("leading_indicator")
    mitigant = risk.get("mitigant")

    line = f"{prefix} — {risk_text}. Watch: {indicator if indicator else 'not provided'}"
    if mitigant:
        line += f". Mitigant: {mitigant}"

    return line


def _build_slide_1(data: dict[str, Any]) -> dict[str, Any]:
    """Main risk register slide."""
    ticker = data.get("ticker", "")
    risks = data.get("risks", [])
    break_line = data.get("break_thesis_line")
    low_flag = data.get("low_confidence_flag", False)

    title = f"{ticker} — Risks & Underwriting"

    # If no risks, minimal slide
    if not risks:
        bullets = [_bullet("No risks provided")]
        speaker_notes = "No user-provided risks available for this section."
        if low_flag:
            speaker_notes += "\nLow confidence: no risk data provided."
        return {
            "slide_id": "risks_underwriting_1",
            "title": title,
            "bullets": bullets,
            "speaker_notes": speaker_notes,
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
        }

    # Build risk bullets (up to max_bullets - 1 to leave room for break_thesis)
    max_risk_bullets = _MAX_BULLETS_PER_SLIDE
    if break_line:
        max_risk_bullets = _MAX_BULLETS_PER_SLIDE - 1

    bullets: list[dict[str, Any]] = []
    for r in risks[:max_risk_bullets]:
        bullets.append(_bullet(_format_risk_bullet(r)))

    # Break thesis as final bullet
    if break_line:
        bullets.append(_bullet(f"Breaks thesis if: {break_line}"))

    # Speaker notes: all risks that didn't fit + confidence
    notes_parts: list[str] = []
    overflow_risks = risks[max_risk_bullets:]
    if overflow_risks:
        overflow_lines = [_format_risk_bullet(r) for r in overflow_risks]
        notes_parts.append("Additional risks:\n" + "\n".join(f"  - {l}" for l in overflow_lines))

    if low_flag:
        notes_parts.append("Low confidence: missing risk indicators/rank inputs")

    # Per-item notes
    item_notes = [r.get("notes", "") for r in risks if r.get("notes")]
    if item_notes:
        notes_parts.append("Notes: " + "; ".join(item_notes))

    return {
        "slide_id": "risks_underwriting_1",
        "title": title,
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "risk_register",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    }


def _build_slide_2(data: dict[str, Any]) -> dict[str, Any] | None:
    """
    Optional Risk Monitoring slide (deep only, when crowded).
    Contains each risk + its leading indicator (no mitigants).
    Only built when there are more than 4 risks.
    """
    risks = data.get("risks", [])
    ticker = data.get("ticker", "")
    deck_length = data.get("deck_length", "standard")

    if deck_length != "deep" or len(risks) <= _MAX_BULLETS_PER_SLIDE:
        return None

    title = f"{ticker} — Risk Monitoring"

    bullets: list[dict[str, Any]] = []
    notes_parts: list[str] = []

    for r in risks:
        indicator = r.get("leading_indicator") or "not provided"
        text = f"{r.get('risk', 'Unknown')}: Watch {indicator}"
        if len(bullets) < _MAX_BULLETS_PER_SLIDE:
            bullets.append(_bullet(text))
        else:
            notes_parts.append(f"  - {text}")

    if not bullets:
        return None

    speaker_notes = ""
    if notes_parts:
        speaker_notes = "Additional monitoring items:\n" + "\n".join(notes_parts)

    return {
        "slide_id": "risks_underwriting_2",
        "title": title,
        "bullets": bullets,
        "speaker_notes": speaker_notes,
        "layout_hints": {
            "style": "risk_monitoring",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    }


def render_to_slides(
    data: dict[str, Any],
    deck_length: str = "standard",
) -> list[dict[str, Any]]:
    """
    Convert a RisksUnderwritingOutput dict into 1-2 slide dicts.
    """
    # Inject deck_length into data for slide 2 decision
    data_with_length = {**data, "deck_length": deck_length}

    slide1 = _build_slide_1(data_with_length)
    slides = [slide1]

    slide2 = _build_slide_2(data_with_length)
    if slide2:
        slides.append(slide2)

    return slides
