"""
Render structured IndustryCompetitiveOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Slide 1 — "Industry Overview": market_definition, sizing, growth drivers.
Slide 2 — "Competitive Landscape": competitors, moat pillars, Porter's summary.
"""

from __future__ import annotations

import re
from typing import Any


_MAX_BULLETS_PER_SLIDE = 4
_PLACEHOLDER_RE = re.compile(r"^(?:null|none|n/?a|not[_\s]+provided|tbd|unknown)$", re.IGNORECASE)


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


# ── Slide 1: Industry Overview ───────────────────────────────────────────────

def _build_slide_1(output: dict[str, Any]) -> dict[str, Any]:
    """Market definition + sizing + growth drivers."""
    market = output.get("market", {})
    sizing = market.get("sizing", {})

    bullets: list[dict[str, Any]] = []

    # Market definition
    mdef = _clean_text(market.get("market_definition"))
    if mdef:
        bullets.append(_bullet(mdef))

    # Sizing: TAM if present, else proxy bullets
    tam = _clean_text(sizing.get("tam_value"))
    tam_basis = _clean_text(sizing.get("tam_basis"))
    if tam:
        sizing_text = f"TAM: {tam}"
        if tam_basis:
            sizing_text += f" ({tam_basis})"
        bullets.append(_bullet(sizing_text, source_needed=True))
    else:
        for proxy in sizing.get("proxy_sizing", [])[:2]:
            cleaned_proxy = _clean_text(proxy)
            if not cleaned_proxy:
                continue
            if len(bullets) < _MAX_BULLETS_PER_SLIDE:
                bullets.append(_bullet(cleaned_proxy))

    # Growth drivers (fill remaining bullet slots)
    for driver in market.get("growth_drivers", []):
        cleaned_driver = _clean_text(driver)
        if not cleaned_driver:
            continue
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(cleaned_driver))

    # Speaker notes: additional growth drivers + growth chart notes
    notes_parts: list[str] = []

    # Growth drivers that didn't fit in bullets
    all_drivers = [d for d in (_clean_text(v) for v in market.get("growth_drivers", [])) if d]
    extra_drivers = all_drivers[max(0, _MAX_BULLETS_PER_SLIDE - 2):]
    if extra_drivers:
        notes_parts.append(
            "Additional growth drivers:\n"
            + "\n".join(f"  • {d}" for d in extra_drivers)
        )

    # Growth chart notes
    gcn = [n for n in (_clean_text(v) for v in sizing.get("growth_chart_notes", [])) if n]
    if gcn:
        notes_parts.append(
            "Growth notes:\n" + "\n".join(f"  • {n}" for n in gcn)
        )

    # Confidence
    conf = market.get("confidence", "medium")
    notes_parts.append(f"Market confidence: {conf}")

    market_notes = _clean_text(market.get("notes"))
    if market_notes:
        notes_parts.append(f"Notes: {market_notes}")

    # Low confidence flag
    if output.get("low_confidence_flag"):
        notes_parts.append("⚠ Low confidence: limited disclosure")

    return {
        "slide_id": "industry_competitive_landscape_1",
        "title": "Industry Overview",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "market_sizing_chart",
        },
        "flags": {
            "needs_sources": bool(tam),
            "contains_numbers": bool(tam),
            "is_draft": False,
        },
    }


# ── Slide 2: Competitive Landscape ──────────────────────────────────────────

def _build_slide_2(output: dict[str, Any]) -> dict[str, Any]:
    """Competitors + moat pillars + Porter's summary."""
    competition = output.get("competition", {})
    moat = output.get("moat", {})
    porters = output.get("porters", {})

    bullets: list[dict[str, Any]] = []

    # Competitor summary + positioning differentiator
    competitors = competition.get("competitors", [])
    positioning = competition.get("positioning", {})
    if competitors:
        comp_names = [name for name in (_clean_text(c.get("name")) for c in competitors[:4]) if name]
        if not comp_names:
            comp_names = ["Peers"]
        comp_text = f"Key competitors: {', '.join(comp_names)}"
        diff = _clean_text(positioning.get("key_differentiator"))
        if diff:
            comp_text += f" — differentiator: {diff}"
        # Truncate if too long
        if len(comp_text) > 500:
            comp_text = comp_text[:497] + "..."
        bullets.append(_bullet(comp_text))

    # Moat pillars summary
    pillars = moat.get("pillars", [])
    if pillars:
        pillar_names = [name for name in (_clean_text(p.get("pillar")) for p in pillars[:4]) if name]
        if not pillar_names:
            pillar_names = ["Moat strength"]
        moat_text = f"Moat drivers: {', '.join(pillar_names)}"
        if len(moat_text) > 500:
            moat_text = moat_text[:497] + "..."
        bullets.append(_bullet(moat_text))

    # Porter's Five Forces compact summary
    forces = porters.get("forces", [])
    if forces:
        force_summary_parts = []
        for f in forces[:5]:
            fname = _clean_text(f.get("force"))
            fpressure = _clean_text(f.get("pressure"))
            # Compact: abbreviate force names
            short = _abbreviate_force(fname)
            force_summary_parts.append(f"{short}: {fpressure}")
        porters_text = "Porter's: " + " | ".join(force_summary_parts)
        if len(porters_text) > 500:
            porters_text = porters_text[:497] + "..."
        bullets.append(_bullet(porters_text))

    # Fill remaining slot if room
    if len(bullets) < _MAX_BULLETS_PER_SLIDE and pillars:
        # Add top moat mechanism as extra detail
        top_pillar = pillars[0]
        mech = _clean_text(top_pillar.get("mechanism"))
        if mech:
            pillar_name = _clean_text(top_pillar.get("pillar")) or "Moat"
            bullets.append(_bullet(f"{pillar_name}: {mech}"))

    # Speaker notes: detailed competitor list + moat evidence + Porter's detail
    notes_parts: list[str] = []

    # Detailed competitor table
    if competitors:
        comp_lines = []
        for c in competitors:
            cname = _clean_text(c.get("name")) or "Competitor"
            ctype = _clean_text(c.get("type"))
            cwhy = _clean_text(c.get("why_relevant"))
            line = f"  • {cname}"
            if ctype:
                line += f" ({ctype})"
            if cwhy:
                line += f": {cwhy}"
            comp_lines.append(line)
        notes_parts.append("Competitors:\n" + "\n".join(comp_lines))

    # Positioning
    if positioning:
        pos_text = (
            f"Positioning: {_clean_text(positioning.get('x_label'))} vs {_clean_text(positioning.get('y_label'))}; "
            f"Company at {_clean_text(positioning.get('company_position'))}"
        )
        notes_parts.append(pos_text)

    # Moat detail
    if pillars:
        moat_lines = []
        for p in pillars:
            pillar_name = _clean_text(p.get("pillar")) or "Pillar"
            mechanism = _clean_text(p.get("mechanism")) or "data unavailable"
            line = f"  • {pillar_name}: {mechanism}"
            evidence = _clean_text(p.get("evidence"))
            if evidence:
                line += f" [evidence: {evidence}]"
            moat_lines.append(line)
        notes_parts.append("Moat pillars:\n" + "\n".join(moat_lines))

    # Porter's detail
    if forces:
        porter_lines = []
        for f in forces:
            because_items = [b for b in (_clean_text(v) for v in f.get("because", [])) if b]
            because = "; ".join(because_items)
            force = _clean_text(f.get("force")) or "Force"
            pressure = _clean_text(f.get("pressure")) or "unknown"
            line = f"  • {force} ({pressure}): {because}"
            evidence = _clean_text(f.get("evidence"))
            if evidence:
                line += f" [evidence: {evidence}]"
            porter_lines.append(line)
        notes_parts.append("Porter's Five Forces:\n" + "\n".join(porter_lines))

    # Confidence
    for mod_name, mod_data in [("competition", competition), ("moat", moat), ("porters", porters)]:
        conf = mod_data.get("confidence", "")
        if conf:
            notes_parts.append(f"{mod_name} confidence: {conf}")
        mod_notes = _clean_text(mod_data.get("notes"))
        if mod_notes:
            notes_parts.append(f"[{mod_name}] {mod_notes}")

    # Low confidence flag
    if output.get("low_confidence_flag"):
        notes_parts.append("⚠ Low confidence: limited disclosure")

    return {
        "slide_id": "industry_competitive_landscape_2",
        "title": "Competitive Landscape",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "two_column",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "positioning_map",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    }


def _abbreviate_force(force_name: str) -> str:
    """Abbreviate Porter's force names for compact display."""
    abbrevs = {
        "Threat of New Entrants": "New Entrants",
        "Bargaining Power of Suppliers": "Suppliers",
        "Bargaining Power of Buyers": "Buyers",
        "Threat of Substitutes": "Substitutes",
        "Competitive Rivalry": "Rivalry",
    }
    return abbrevs.get(force_name, force_name)


# ── Public API ───────────────────────────────────────────────────────────────

def render_to_slides(output: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert an IndustryCompetitiveOutput dict into 1–2 slide dicts.

    Returns a list suitable for the ``slides`` field in the standard
    section output schema.
    """
    slide1 = _build_slide_1(output)
    slide2 = _build_slide_2(output)

    slides = [slide1]
    if slide2["bullets"]:
        slides.append(slide2)

    return slides
