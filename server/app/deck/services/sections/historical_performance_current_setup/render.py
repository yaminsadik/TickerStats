"""
Render structured HistoricalPerfCurrentSetupOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Layout strategy:
  Slide 1 — Historical Performance: fundamentals highlights (3–6 bullets),
             speaker notes with compact table of series values.
  Slide 2 — Current Setup: takeaways from stock/rerating (2–4 bullets) +
             recent events, speaker notes with low-confidence annotation.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


# ── Slide 1: Historical Performance ──────────────────────────────────────────


def _build_slide_1(out: dict[str, Any]) -> dict[str, Any]:
    """Historical Performance slide."""
    fund = out.get("fundamentals", {})
    highlights = fund.get("highlights", [])

    bullets: list[dict[str, Any]] = []
    for h in highlights:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if isinstance(h, str) and h.strip():
            bullets.append(_bullet(h))

    # If we have fewer than 1 bullet, add a placeholder noting data limitation
    if not bullets:
        bullets.append(_bullet("Historical financial data not available"))

    # Speaker notes: compact table-like listing of series values by period
    notes_parts: list[str] = []
    series = fund.get("series", [])
    for s in series:
        if not isinstance(s, dict):
            continue
        label = s.get("label", s.get("metric", ""))
        unit = s.get("unit", "")
        points = s.get("points", [])
        point_strs = []
        for p in points:
            if isinstance(p, dict):
                period = p.get("period", "?")
                val = p.get("value")
                val_str = f"{val}" if val is not None else "N/A"
                point_strs.append(f"{period}: {val_str}")
        if point_strs:
            notes_parts.append(f"{label} ({unit}): {' | '.join(point_strs)}")

    window = fund.get("window_years", "N/A")
    notes_parts.insert(0, f"Window: {window} years")

    fund_conf = fund.get("confidence", "medium")
    fund_notes = fund.get("notes")
    if fund_conf == "low" or fund_notes:
        notes_parts.append(f"Fundamentals confidence: {fund_conf}")
        if fund_notes:
            notes_parts.append(f"Notes: {fund_notes}")

    return {
        "slide_id": "historical_performance_current_setup_1",
        "title": "Historical Performance",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "line_chart",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": bool(series),
            "is_draft": False,
        },
    }


# ── Slide 2: Current Setup ──────────────────────────────────────────────────


def _get_setup_takeaways(out: dict[str, Any]) -> list[str]:
    """Get takeaways based on setup_mode."""
    mode = out.get("setup_mode", "valuation_rerating")
    takeaways: list[str] = []

    if mode in ("price_vs_benchmark", "both"):
        stock = out.get("stock", {})
        for t in stock.get("takeaways", []):
            if isinstance(t, str) and t.strip():
                takeaways.append(t)

    if mode in ("valuation_rerating", "both"):
        rerating = out.get("rerating", {})
        # Include current_vs_median as takeaways
        for s in rerating.get("current_vs_median", []):
            if isinstance(s, str) and s.strip():
                takeaways.append(s)
        for t in rerating.get("takeaways", []):
            if isinstance(t, str) and t.strip():
                takeaways.append(t)

    return takeaways


def _build_slide_2(out: dict[str, Any]) -> dict[str, Any]:
    """Current Setup slide."""
    takeaways = _get_setup_takeaways(out)
    what_changed = out.get("what_changed", {})
    events = what_changed.get("events", [])
    low_flag = out.get("low_confidence_flag", False)

    bullets: list[dict[str, Any]] = []

    # Add setup takeaways (up to 2 to leave room for events)
    max_takeaway_bullets = min(2, _MAX_BULLETS_PER_SLIDE)
    if not events:
        max_takeaway_bullets = _MAX_BULLETS_PER_SLIDE

    for t in takeaways[:max_takeaway_bullets]:
        bullets.append(_bullet(t))

    # Add event bullets (remaining space)
    remaining = _MAX_BULLETS_PER_SLIDE - len(bullets)
    if events and remaining > 0:
        event_strs: list[str] = []
        for e in events[:remaining * 2]:  # gather more, we'll compact
            if isinstance(e, dict):
                headline = e.get("headline", "")
                date = e.get("date")
                date_prefix = f"[{date}] " if date else ""
                event_strs.append(f"{date_prefix}{headline}")

        # Compact events into remaining bullet slots
        for es in event_strs[:remaining]:
            bullets.append(_bullet(es))

    if not bullets:
        bullets.append(_bullet("Current setup data not available"))

    # Speaker notes
    notes_parts: list[str] = []
    mode = out.get("setup_mode", "valuation_rerating")
    notes_parts.append(f"Setup mode: {mode}")

    sentiment = what_changed.get("current_sentiment_summary", "")
    if sentiment:
        notes_parts.append(f"Sentiment: {sentiment}")

    # Extended takeaways that didn't fit
    for t in takeaways[max_takeaway_bullets:]:
        notes_parts.append(f"- {t}")

    # Events that didn't fit in bullets
    for e in events:
        if isinstance(e, dict):
            why = e.get("why_it_matters", "")
            if why:
                headline = e.get("headline", "")
                notes_parts.append(f"  {headline}: {why}")

    if low_flag:
        low_reasons: list[str] = []
        fund_conf = out.get("fundamentals", {}).get("confidence", "medium")
        stock_conf = out.get("stock", {}).get("confidence", "medium")
        rerate_conf = out.get("rerating", {}).get("confidence", "medium")
        wc_conf = what_changed.get("confidence", "medium")
        for label, conf in [
            ("fundamentals", fund_conf),
            ("stock", stock_conf),
            ("rerating", rerate_conf),
            ("events", wc_conf),
        ]:
            if conf == "low":
                low_reasons.append(label)

        reason_str = ", ".join(low_reasons) if low_reasons else "limited data"
        notes_parts.append(f"Low confidence: {reason_str}")

    wc_notes = what_changed.get("notes")
    if wc_notes:
        notes_parts.append(f"Notes: {wc_notes}")

    return {
        "slide_id": "historical_performance_current_setup_2",
        "title": "Current Setup",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
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
    }


# ── Public API ───────────────────────────────────────────────────────────────


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a HistoricalPerfCurrentSetupOutput dict to 1–2 standard slides.

    Always produces Slide 1 (Historical Performance).
    Produces Slide 2 (Current Setup) if any setup data exists.
    """
    slides = [_build_slide_1(out)]

    # Slide 2 is included unless entire setup is empty
    mode = out.get("setup_mode", "valuation_rerating")
    what_changed = out.get("what_changed", {})
    events = what_changed.get("events", [])
    takeaways = _get_setup_takeaways(out)

    has_setup_content = bool(takeaways) or bool(events)
    # Always produce slide 2 — even if low confidence, we note the gap
    slides.append(_build_slide_2(out))

    return slides
