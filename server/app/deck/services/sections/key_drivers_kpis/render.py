"""
Render structured KeyDriversKpisOutput → slide-ready blocks.

Converts the rich JSON into 1-2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Slide 1: "Key Drivers & KPIs" — KPI bullets + overall takeaways
Slide 2 (optional): KPI → unit → disclosure source summary table in notes
"""

from __future__ import annotations

import re
from typing import Any


_MAX_BULLETS_PER_SLIDE = 4
_PLACEHOLDER_RE = re.compile(r"^(?:null|none|n/?a|not[_\s]+provided|tbd|unknown)$", re.IGNORECASE)
_SAFE_UNIT_RE = re.compile(r"^[A-Za-z0-9$%#xX/\-+ .]{1,24}$")


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def _clean_text(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = " ".join(value.split())
    if not text or _PLACEHOLDER_RE.match(text):
        return ""
    return text


def _sanitize_unit(value: Any) -> str:
    """
    Accept only compact unit-like strings.

    This prevents prompt-leak chatter from appearing as KPI units.
    """
    unit = _clean_text(value)
    if not unit:
        return ""
    lowered = unit.lower()
    if any(token in lowered for token in ("let's", "wait", "actually", "formalize", "standard unit")):
        return ""
    if not _SAFE_UNIT_RE.match(unit):
        return ""
    return unit


def _format_kpi_bullet(kpi: dict[str, Any]) -> str:
    """Format a single KPI as a compact bullet line."""
    name = _clean_text(kpi.get("name")) or "KPI"
    definition = _clean_text(kpi.get("definition"))
    unit = _sanitize_unit(kpi.get("unit"))
    text = f"{name}: {definition}"
    if unit:
        text += f" ({unit})"
    return text


def _format_kpi_value_line(kpi: dict[str, Any]) -> str:
    """Format a KPI's 'why it matters' as a compact line."""
    name = _clean_text(kpi.get("name")) or "KPI"
    why = _clean_text(kpi.get("why_it_moves_value")) or "data unavailable"
    return f"Why {name} matters: {why}"


def _format_disclosure_line(kpi: dict[str, Any]) -> str:
    """Format a KPI's disclosure reference for speaker notes."""
    name = _clean_text(kpi.get("name")) or "KPI"
    disclosure = kpi.get("disclosure") or {}
    source_type = disclosure.get("source_type", "not_provided")
    desc = _clean_text(disclosure.get("description"))
    page = _clean_text(disclosure.get("page_or_section"))

    if source_type == "not_provided":
        return f"Disclosure ({name}): data unavailable"

    parts = [f"Disclosure ({name}): {source_type}"]
    if desc:
        parts.append(f"— {desc}")
    if page:
        parts.append(f"(section/page: {page})")
    return " ".join(parts)


def _build_slide_1(output: dict[str, Any]) -> dict[str, Any]:
    """Main KPI slide — definitions + value drivers."""
    kpis = output.get("kpis", [])
    takeaways = output.get("overall_takeaways", [])
    low_flag = output.get("low_confidence_flag", False)
    confidence = output.get("confidence", "medium")

    # Build bullets: compact KPI lines (up to 4, prioritise KPIs)
    bullets: list[dict[str, Any]] = []
    for kpi in kpis:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        text = _format_kpi_bullet(kpi)
        if not text.strip() or text.endswith(":"):
            continue
        bullets.append(_bullet(text))

    # If we have room and takeaways, add as a combined bullet
    if len(bullets) < _MAX_BULLETS_PER_SLIDE and takeaways:
        cleaned_takeaways = [t for t in (_clean_text(v) for v in takeaways[:2]) if t]
        if cleaned_takeaways:
            combined = "Takeaway: " + "; ".join(cleaned_takeaways)
            bullets.append(_bullet(combined))

    # Speaker notes: value linkage + disclosure refs + takeaways
    notes_parts: list[str] = []

    # Value linkage
    for kpi in kpis:
        notes_parts.append(_format_kpi_value_line(kpi))

    # Separation
    if kpis:
        notes_parts.append("")  # blank line

    # Disclosure references
    for kpi in kpis:
        notes_parts.append(_format_disclosure_line(kpi))

    # Overall takeaways
    if takeaways:
        cleaned_takeaways = [t for t in (_clean_text(v) for v in takeaways) if t]
        notes_parts.append("")
        notes_parts.append("Overall Takeaways:")
        for ta in cleaned_takeaways:
            notes_parts.append(f"  • {ta}")

    # Low confidence warning
    if low_flag:
        notes_parts.append("")
        notes_parts.append("Low confidence: limited KPI disclosure in inputs.")

    return {
        "slide_id": "key_drivers_kpis_1",
        "title": "Key Drivers & KPIs",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": any(
                kpi.get("unit") for kpi in kpis
            ),
            "is_draft": low_flag,
        },
    }


def _build_slide_2(output: dict[str, Any]) -> dict[str, Any] | None:
    """
    Optional summary slide — KPI table-like format.

    Only generated if there are >3 KPIs (to avoid redundancy with slide 1).
    """
    kpis = output.get("kpis", [])
    if len(kpis) <= 3:
        return None

    # Build compact table-like bullets: "KPI | Unit | Source"
    bullets: list[dict[str, Any]] = []
    for kpi in kpis:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        name = kpi.get("name", "KPI")
        unit = _sanitize_unit(kpi.get("unit")) or "—"
        disclosure = kpi.get("disclosure") or {}
        source = disclosure.get("source_type", "not_provided")
        if source == "not_provided":
            source = "data unavailable"
        text = f"{name} | {unit} | {source}"
        bullets.append(_bullet(text))

    # Speaker notes: remaining KPIs if any didn't fit in bullets
    notes_parts: list[str] = ["KPI Summary Table:"]
    for kpi in kpis:
        name = _clean_text(kpi.get("name")) or "KPI"
        unit = _sanitize_unit(kpi.get("unit")) or "—"
        direction = _clean_text(kpi.get("typical_direction")) or "—"
        disclosure = kpi.get("disclosure") or {}
        source = disclosure.get("source_type", "not_provided")
        if source == "not_provided":
            source = "data unavailable"
        notes_parts.append(f"  {name} | {unit} | {direction} | {source}")

    return {
        "slide_id": "key_drivers_kpis_2",
        "title": "Key Drivers & KPIs — Summary",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "table",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "table",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": True,
            "is_draft": False,
        },
    }


def render_to_slides(output: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a KeyDriversKpisOutput dict into 1-2 slide dicts.

    Returns a list suitable for the ``slides`` field in the standard
    section output schema.
    """
    slide1 = _build_slide_1(output)
    slides = [slide1]

    slide2 = _build_slide_2(output)
    if slide2 and slide2["bullets"]:
        slides.append(slide2)

    return slides
