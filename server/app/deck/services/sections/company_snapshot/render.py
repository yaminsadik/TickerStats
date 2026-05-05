"""
Render structured CompanySnapshotOutput → slide-ready blocks.

Converts the rich JSON into 1-2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Layout strategy (2-column grid, mapped to 2 slides):
  Slide 1 — Header + Left column: positioning bullets, money model summary
  Slide 2 — Right column: segments, customers, footprint, proof points

If space is tight, proof points take priority over footprint.
"""

from __future__ import annotations

import json
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


def _format_kpi(kpi: dict[str, Any]) -> str:
    label = _clean_text(kpi.get("label")) or "KPI"
    value = _clean_text(kpi.get("value")) or "data unavailable"
    as_of = kpi.get("as_of")
    s = f"{label}: {value}"
    if as_of:
        s += f" ({as_of})"
    return s


def _format_quick_stat(stat: dict[str, Any]) -> str:
    label = _clean_text(stat.get("label"))
    value = _clean_text(stat.get("value"))
    if not label or not value:
        return ""
    return f"{label}: {value}"


def _build_slide_1(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Header + positioning + money model (left column)."""
    header = snapshot.get("header", {})
    modules = snapshot.get("modules", {})
    positioning = modules.get("positioning", {})
    money = modules.get("money_model", {})

    company_name = header.get("company_name", "Company")
    ticker = header.get("ticker", "")
    title = f"{company_name} ({ticker}) — Company Snapshot"

    # Bullets: positioning sentence first, then positioning bullets
    bullets: list[dict[str, Any]] = []
    pos_sentence = _clean_text(header.get("positioning_sentence"))
    if pos_sentence:
        bullets.append(_bullet(pos_sentence))

    for b in positioning.get("bullets", []):
        cleaned = _clean_text(b)
        if not cleaned:
            continue
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(cleaned))

    # Speaker notes: money model summary + quick stats
    notes_parts: list[str] = []

    # Money model
    pricing = _clean_text(money.get("pricing_unit"))
    contract = _clean_text(money.get("contract_structure"))
    recurrence = _clean_text(money.get("recurrence"))
    cost_drivers = [cd for cd in (_clean_text(v) for v in money.get("cost_drivers", [])) if cd]
    if pricing or contract or recurrence:
        money_line = "Money Model: "
        money_pieces = []
        if pricing:
            money_pieces.append(f"pricing={pricing}")
        if contract:
            money_pieces.append(f"contract={contract}")
        if recurrence:
            money_pieces.append(f"recurrence={recurrence}")
        money_line += ", ".join(money_pieces)
        if cost_drivers:
            money_line += f". Key costs: {', '.join(cost_drivers)}"
        notes_parts.append(money_line)

    # Quick stats for speaker notes
    quick_stats = header.get("quick_stats", [])
    if quick_stats:
        formatted_stats = [fs for fs in (_format_quick_stat(s) for s in quick_stats) if fs]
        if formatted_stats:
            stats_line = "Quick Stats: " + " | ".join(formatted_stats)
            notes_parts.append(stats_line)

    # Confidence notes
    conf_notes = []
    for mod_name in ("positioning", "money_model"):
        mod = modules.get(mod_name, {})
        if mod.get("notes"):
            conf_notes.append(f"[{mod_name}] {mod['notes']}")
    if conf_notes:
        notes_parts.append("Notes: " + "; ".join(conf_notes))

    return {
        "slide_id": "company_snapshot_1",
        "title": title,
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "snapshot_header",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    }


def _build_slide_2(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Segments + customers + footprint + proof points (right column)."""
    header = snapshot.get("header", {})
    modules = snapshot.get("modules", {})
    segments = modules.get("segments", {})
    customers = modules.get("customers", {})
    footprint = modules.get("footprint", {})
    proof_points = modules.get("proof_points", {})

    company_name = _clean_text(header.get("company_name")) or "Company"
    title = f"{company_name} — Business Profile"

    # Bullets: segments one-liners, customer types, footprint regions
    # Priority: segments > customers > proof_points > footprint
    bullets: list[dict[str, Any]] = []

    # Segments
    for seg in segments.get("items", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        name = _clean_text(seg.get("name"))
        liner = _clean_text(seg.get("one_liner"))
        if not name and not liner:
            continue
        mix = seg.get("mix_pct")
        text = name or "Segment"
        if isinstance(mix, (int, float)) and mix > 0:
            text += f" ({mix:.0f}%)"
        if liner:
            text += f" — {liner}"
        bullets.append(_bullet(text))

    # Customer types
    cust_types = [ct for ct in (_clean_text(t) for t in customers.get("types", [])) if ct]
    if cust_types and len(bullets) < _MAX_BULLETS_PER_SLIDE:
        conc = _clean_text(customers.get("concentration"))
        cust_text = f"Customers: {', '.join(cust_types)}"
        if conc:
            cust_text += f" (concentration: {conc})"
        bullets.append(_bullet(cust_text))

    # Footprint (lowest priority for bullets — proof points go to notes)
    regions = [r for r in (_clean_text(v) for v in footprint.get("regions", [])) if r]
    if regions and len(bullets) < _MAX_BULLETS_PER_SLIDE:
        fp_text = f"Footprint: {', '.join(regions)}"
        why = _clean_text(footprint.get("why_it_matters"))
        if why:
            fp_text += f" — {why}"
        bullets.append(_bullet(fp_text))

    # Speaker notes: proof points KPIs + additional module notes
    notes_parts: list[str] = []

    kpis = proof_points.get("kpis", [])
    if kpis:
        kpi_lines = [_format_kpi(k) for k in kpis]
        notes_parts.append("Proof Points:\n" + "\n".join(f"  • {l}" for l in kpi_lines))

    # Module confidence notes
    conf_notes = []
    for mod_name in ("segments", "customers", "footprint", "proof_points"):
        mod = modules.get(mod_name, {})
        if mod.get("notes"):
            conf_notes.append(f"[{mod_name}] {mod['notes']}")
    if conf_notes:
        notes_parts.append("Notes: " + "; ".join(conf_notes))

    # Low confidence footnote
    if header.get("low_confidence_flag"):
        notes_parts.append("⚠ Low confidence — limited data available")

    return {
        "slide_id": "company_snapshot_2",
        "title": title,
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "snapshot_detail",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": False,
            "is_draft": False,
        },
    }


def render_to_slides(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a CompanySnapshotOutput dict into 1-2 slide dicts.

    Returns a list suitable for the ``slides`` field in the standard
    section output schema.
    """
    slide1 = _build_slide_1(snapshot)
    slide2 = _build_slide_2(snapshot)

    # Only include slide 2 if it has bullets
    slides = [slide1]
    if slide2["bullets"]:
        slides.append(slide2)

    # Attach raw snapshot as metadata on slide 1 for rich rendering
    slide1["layout_hints"]["_raw_snapshot"] = json.dumps(snapshot)

    return slides
