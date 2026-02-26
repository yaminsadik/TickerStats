"""
Render structured BusinessModelSegmentsOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Layout strategy:
  Slide 1 — Business Model: what they sell, who they sell to, revenue flow,
             pricing/contract notes.
  Slide 2 — Segments + Unit Economics (optional): segment breakdown with mix
             and drivers, plus unit economics metrics panel if applicable.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def _should_include_slide_2(out: dict[str, Any]) -> bool:
    """
    Include Slide 2 if segments has items AND either:
    - any mix_pct exists, or
    - unit_economics.applicable is true, or
    - segment items count > 3
    """
    segments = out.get("segments", {})
    items = segments.get("items", [])
    if not items:
        return False

    has_mix = any(
        seg.get("revenue_mix_pct") is not None
        for seg in items
        if isinstance(seg, dict)
    )
    ue = out.get("unit_economics", {})
    applicable = ue.get("applicable", False)

    return has_mix or applicable or len(items) > 3


def _build_slide_1(out: dict[str, Any]) -> dict[str, Any]:
    """Business Model slide."""
    bm = out.get("business_model", {})

    # Bullet 1: What they sell
    what_sell = bm.get("what_they_sell", [])
    sell_text = "Products/Services: " + ", ".join(what_sell) if what_sell else ""

    # Bullet 2: Who they sell to
    who_sell = bm.get("who_they_sell_to", [])
    who_text = "Customers: " + ", ".join(who_sell) if who_sell else ""

    # Bullet 3: Revenue flow as numbered steps (compact)
    flow = bm.get("revenue_flow", [])
    flow_steps: list[str] = []
    for i, step in enumerate(flow, 1):
        if isinstance(step, dict):
            flow_steps.append(f"{i}) {step.get('step', '')}")
        elif isinstance(step, str):
            flow_steps.append(f"{i}) {step}")
    flow_text = "Revenue Flow: " + " → ".join(flow_steps) if flow_steps else ""

    # Bullet 4: Pricing/contract notes (only if present)
    pricing_notes = bm.get("pricing_contract_notes", [])
    pricing_text = ""
    if pricing_notes:
        pricing_text = "Pricing: " + "; ".join(str(n) for n in pricing_notes)

    bullets: list[dict[str, Any]] = []
    for text in [sell_text, who_text, flow_text, pricing_text]:
        if text and len(bullets) < _MAX_BULLETS_PER_SLIDE:
            bullets.append(_bullet(text))

    # Speaker notes
    notes_parts: list[str] = []
    confidence = bm.get("confidence", "medium")
    bm_notes = bm.get("notes")
    if confidence == "low" or bm_notes:
        notes_parts.append(f"Business model confidence: {confidence}")
        if bm_notes:
            notes_parts.append(f"Notes: {bm_notes}")

    return {
        "slide_id": "business_model_segments_1",
        "title": "Business Model",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
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


def _build_slide_2(out: dict[str, Any]) -> dict[str, Any]:
    """Segments + Unit Economics slide."""
    segments = out.get("segments", {})
    ue = out.get("unit_economics", {})
    items = segments.get("items", [])
    low_flag = out.get("low_confidence_flag", False)

    bullets: list[dict[str, Any]] = []

    # Segment bullets — prioritize top segments, cap to leave room for unit econ
    max_seg_bullets = _MAX_BULLETS_PER_SLIDE
    if ue.get("applicable"):
        max_seg_bullets = 3  # reserve 1 bullet for unit economics

    for seg in items:
        if len(bullets) >= max_seg_bullets:
            break
        if not isinstance(seg, dict):
            continue
        name = seg.get("name", "")
        liner = seg.get("one_liner", "")
        mix = seg.get("revenue_mix_pct")

        text = f"{name}: {liner}" if liner else name
        if mix is not None:
            text += f" (Rev mix: {mix:.0f}%)"

        bullets.append(_bullet(text))

    # Unit economics compact line
    if ue.get("applicable") and ue.get("metrics"):
        metric_strs = []
        for m in ue["metrics"][:4]:  # cap display
            if isinstance(m, dict):
                metric_strs.append(f"{m.get('label', '')}: {m.get('value', '')}")
        if metric_strs and len(bullets) < _MAX_BULLETS_PER_SLIDE:
            bullets.append(_bullet("Unit Economics — " + " | ".join(metric_strs)))

    # Speaker notes
    notes_parts: list[str] = []
    seg_mode = segments.get("mode", "")
    seg_notes = segments.get("notes")
    seg_confidence = segments.get("confidence", "medium")

    if seg_mode == "tier_c" or seg_notes:
        notes_parts.append(
            f"Segments: {seg_mode} (confidence: {seg_confidence})"
        )
        if seg_notes:
            notes_parts.append(f"Segment notes: {seg_notes}")

    if low_flag:
        notes_parts.append("Low confidence: limited disclosure")

    ue_notes = ue.get("notes")
    if ue_notes:
        notes_parts.append(f"Unit economics notes: {ue_notes}")

    return {
        "slide_id": "business_model_segments_2",
        "title": "Segments & Unit Economics",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "segment_chart",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": any(
                seg.get("revenue_mix_pct") is not None
                for seg in items
                if isinstance(seg, dict)
            ),
            "is_draft": False,
        },
    }


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a BusinessModelSegmentsOutput dict to 1–2 standard slides.

    Always produces Slide 1 (Business Model).
    Produces Slide 2 (Segments + Unit Economics) only if warranted.
    """
    slides = [_build_slide_1(out)]

    if _should_include_slide_2(out):
        slides.append(_build_slide_2(out))

    return slides
