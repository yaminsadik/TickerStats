"""
Render structured IndustryCompetitiveOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Slide 1 — "Industry Overview": market_definition, sizing, growth drivers.
Slide 2 — "Competitive Landscape": competitors, moat pillars, Porter's summary.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


# ── Slide 1: Industry Overview ───────────────────────────────────────────────

def _build_slide_1(output: dict[str, Any]) -> dict[str, Any]:
    """Market definition + sizing + growth drivers."""
    market = output.get("market", {})
    sizing = market.get("sizing", {})

    bullets: list[dict[str, Any]] = []

    # Market definition
    mdef = market.get("market_definition", "")
    if mdef:
        bullets.append(_bullet(mdef))

    # Sizing: TAM if present, else proxy bullets
    tam = sizing.get("tam_value")
    tam_basis = sizing.get("tam_basis")
    if tam:
        sizing_text = f"TAM: {tam}"
        if tam_basis:
            sizing_text += f" ({tam_basis})"
        bullets.append(_bullet(sizing_text, source_needed=True))
    else:
        for proxy in sizing.get("proxy_sizing", [])[:2]:
            if len(bullets) < _MAX_BULLETS_PER_SLIDE:
                bullets.append(_bullet(proxy))

    # Growth drivers (fill remaining bullet slots)
    for driver in market.get("growth_drivers", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(driver))

    # Speaker notes: additional growth drivers + growth chart notes
    notes_parts: list[str] = []

    # Growth drivers that didn't fit in bullets
    all_drivers = market.get("growth_drivers", [])
    extra_drivers = all_drivers[max(0, _MAX_BULLETS_PER_SLIDE - 2):]
    if extra_drivers:
        notes_parts.append(
            "Additional growth drivers:\n"
            + "\n".join(f"  • {d}" for d in extra_drivers)
        )

    # Growth chart notes
    gcn = sizing.get("growth_chart_notes", [])
    if gcn:
        notes_parts.append(
            "Growth notes:\n" + "\n".join(f"  • {n}" for n in gcn)
        )

    # Confidence
    conf = market.get("confidence", "medium")
    notes_parts.append(f"Market confidence: {conf}")

    if market.get("notes"):
        notes_parts.append(f"Notes: {market['notes']}")

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
        comp_names = [c.get("name", "") for c in competitors[:4]]
        comp_text = f"Key competitors: {', '.join(comp_names)}"
        diff = positioning.get("key_differentiator", "")
        if diff:
            comp_text += f" — differentiator: {diff}"
        # Truncate if too long
        if len(comp_text) > 500:
            comp_text = comp_text[:497] + "..."
        bullets.append(_bullet(comp_text))

    # Moat pillars summary
    pillars = moat.get("pillars", [])
    if pillars:
        pillar_names = [p.get("pillar", "") for p in pillars[:4]]
        moat_text = f"Moat drivers: {', '.join(pillar_names)}"
        if len(moat_text) > 500:
            moat_text = moat_text[:497] + "..."
        bullets.append(_bullet(moat_text))

    # Porter's Five Forces compact summary
    forces = porters.get("forces", [])
    if forces:
        force_summary_parts = []
        for f in forces[:5]:
            fname = f.get("force", "")
            fpressure = f.get("pressure", "")
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
        mech = top_pillar.get("mechanism", "")
        if mech:
            bullets.append(_bullet(f"{top_pillar.get('pillar', '')}: {mech}"))

    # Speaker notes: detailed competitor list + moat evidence + Porter's detail
    notes_parts: list[str] = []

    # Detailed competitor table
    if competitors:
        comp_lines = []
        for c in competitors:
            cname = c.get("name", "")
            ctype = c.get("type", "")
            cwhy = c.get("why_relevant", "")
            comp_lines.append(f"  • {cname} ({ctype}): {cwhy}")
        notes_parts.append("Competitors:\n" + "\n".join(comp_lines))

    # Positioning
    if positioning:
        pos_text = (
            f"Positioning: {positioning.get('x_label', '')} vs {positioning.get('y_label', '')}; "
            f"Company at {positioning.get('company_position', '')}"
        )
        notes_parts.append(pos_text)

    # Moat detail
    if pillars:
        moat_lines = []
        for p in pillars:
            line = f"  • {p.get('pillar', '')}: {p.get('mechanism', '')}"
            if p.get("evidence"):
                line += f" [evidence: {p['evidence']}]"
            moat_lines.append(line)
        notes_parts.append("Moat pillars:\n" + "\n".join(moat_lines))

    # Porter's detail
    if forces:
        porter_lines = []
        for f in forces:
            because = "; ".join(f.get("because", []))
            line = f"  • {f.get('force', '')} ({f.get('pressure', '')}): {because}"
            if f.get("evidence"):
                line += f" [evidence: {f['evidence']}]"
            porter_lines.append(line)
        notes_parts.append("Porter's Five Forces:\n" + "\n".join(porter_lines))

    # Confidence
    for mod_name, mod_data in [("competition", competition), ("moat", moat), ("porters", porters)]:
        conf = mod_data.get("confidence", "")
        if conf:
            notes_parts.append(f"{mod_name} confidence: {conf}")
        if mod_data.get("notes"):
            notes_parts.append(f"[{mod_name}] {mod_data['notes']}")

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
