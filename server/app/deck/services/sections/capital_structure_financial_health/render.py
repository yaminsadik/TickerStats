"""
Render structured CapitalStructureFinancialHealthOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Layout strategy:
  Slide 1 — Capital Structure: leverage takeaways + maturity takeaways
             (2–6 bullets total), speaker notes with compact ladder listing
             and interest metrics.
  Slide 2 — Liquidity & Share Count (optional): liquidity takeaways +
             share count takeaways (2–6 bullets total), speaker notes with
             share series and any buyback/SBC facts.
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


# ── Slide 1: Capital Structure ───────────────────────────────────────────────


def _build_slide_1(out: dict[str, Any]) -> dict[str, Any]:
    """Capital Structure slide — leverage + maturities takeaways."""
    leverage = out.get("leverage_interest", {})
    maturities = out.get("maturities", {})
    low_flag = out.get("low_confidence_flag", False)

    lev_takeaways = leverage.get("takeaways", [])
    mat_takeaways = maturities.get("takeaways", [])

    bullets: list[dict[str, Any]] = []

    # Leverage takeaways first
    for t in lev_takeaways:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if isinstance(t, str) and t.strip():
            bullets.append(_bullet(t))

    # Then maturity takeaways
    for t in mat_takeaways:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if isinstance(t, str) and t.strip():
            bullets.append(_bullet(t))

    if not bullets:
        bullets.append(_bullet("Capital structure data not available"))

    # Speaker notes: compact ladder + interest metrics
    notes_parts: list[str] = []

    # Interest metrics
    interest_metrics = leverage.get("interest_metrics", [])
    if interest_metrics:
        for m in interest_metrics:
            if isinstance(m, dict):
                as_of = f" (as of {m['as_of']})" if m.get("as_of") else ""
                notes_parts.append(f"{m.get('label', '')}: {m.get('value', '')}{as_of}")

    # Ladder listing
    ladder = maturities.get("ladder", [])
    if ladder:
        notes_parts.append("Maturity ladder:")
        for item in ladder:
            if isinstance(item, dict):
                amt = item.get("amount") or "N/A"
                inst = item.get("instrument") or ""
                inst_str = f" ({inst})" if inst else ""
                notes_parts.append(f"  {item.get('year_bucket', '?')}: {amt}{inst_str}")

    # Covenants
    covenants = maturities.get("covenants", [])
    if covenants:
        notes_parts.append("Covenants:")
        for cov in covenants:
            if isinstance(cov, dict):
                headroom = f" — headroom: {cov['headroom']}" if cov.get("headroom") else ""
                notes_parts.append(f"  [{cov.get('type', 'other')}] {cov.get('description', '')}{headroom}")

    # Current leverage
    current_lev = leverage.get("current_net_debt_to_ebitda")
    if current_lev is not None:
        notes_parts.insert(0, f"Current Net Debt/EBITDA: {current_lev}x")

    lev_conf = leverage.get("confidence", "medium")
    mat_conf = maturities.get("confidence", "medium")
    if lev_conf == "low" or mat_conf == "low":
        notes_parts.append(f"Leverage confidence: {lev_conf}; Maturities confidence: {mat_conf}")

    lev_notes = leverage.get("notes")
    mat_notes = maturities.get("notes")
    if lev_notes:
        notes_parts.append(f"Notes: {lev_notes}")
    if mat_notes:
        notes_parts.append(f"Notes: {mat_notes}")

    if low_flag:
        notes_parts.append("Low confidence: limited disclosure")

    return {
        "slide_id": "capital_structure_financial_health_1",
        "title": "Capital Structure",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "bar_chart",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": bool(ladder or interest_metrics),
            "is_draft": False,
        },
    }


# ── Slide 2: Liquidity & Share Count ────────────────────────────────────────


def _build_slide_2(out: dict[str, Any]) -> dict[str, Any]:
    """Liquidity & Share Count slide."""
    liquidity = out.get("liquidity", {})
    share_count = out.get("share_count", {})
    low_flag = out.get("low_confidence_flag", False)

    liq_takeaways = liquidity.get("takeaways", [])
    sc_takeaways = share_count.get("takeaways", [])

    bullets: list[dict[str, Any]] = []

    # Liquidity takeaways first
    for t in liq_takeaways:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if isinstance(t, str) and t.strip():
            bullets.append(_bullet(t))

    # Then share count takeaways
    for t in sc_takeaways:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if isinstance(t, str) and t.strip():
            bullets.append(_bullet(t))

    if not bullets:
        bullets.append(_bullet("Liquidity and share count data not available"))

    # Speaker notes: share series + buyback/SBC facts
    notes_parts: list[str] = []

    # Liquidity metrics
    liq_metrics = liquidity.get("metrics", [])
    if liq_metrics:
        for m in liq_metrics:
            if isinstance(m, dict):
                as_of = f" (as of {m['as_of']})" if m.get("as_of") else ""
                notes_parts.append(f"{m.get('label', '')}: {m.get('value', '')}{as_of}")

    # Runway
    runway = liquidity.get("runway")
    if isinstance(runway, dict) and runway.get("estimate"):
        notes_parts.append(f"Runway: {runway.get('basis', '')} → {runway['estimate']}")

    # Share series
    share_series = share_count.get("share_series", [])
    if share_series:
        points_str = []
        for pt in share_series:
            if isinstance(pt, dict):
                val = pt.get("diluted_shares")
                val_str = f"{val}M" if val is not None else "N/A"
                points_str.append(f"{pt.get('period', '?')}: {val_str}")
        if points_str:
            notes_parts.append(f"Diluted shares: {' | '.join(points_str)}")

    # Buyback/SBC facts
    buybacks = share_count.get("buybacks", [])
    for b in buybacks:
        if isinstance(b, str) and b.strip():
            notes_parts.append(f"Buyback: {b}")

    sbc = share_count.get("sbc_dilution", [])
    for s in sbc:
        if isinstance(s, str) and s.strip():
            notes_parts.append(f"SBC: {s}")

    dividends = share_count.get("dividends", [])
    for d in dividends:
        if isinstance(d, str) and d.strip():
            notes_parts.append(f"Dividend: {d}")

    liq_conf = liquidity.get("confidence", "medium")
    sc_conf = share_count.get("confidence", "medium")
    if liq_conf == "low" or sc_conf == "low":
        notes_parts.append(f"Liquidity confidence: {liq_conf}; Share count confidence: {sc_conf}")

    liq_notes = liquidity.get("notes")
    sc_notes = share_count.get("notes")
    if liq_notes:
        notes_parts.append(f"Notes: {liq_notes}")
    if sc_notes:
        notes_parts.append(f"Notes: {sc_notes}")

    if low_flag:
        notes_parts.append("Low confidence: limited disclosure")

    return {
        "slide_id": "capital_structure_financial_health_2",
        "title": "Liquidity & Share Count",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": "line_chart",
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": bool(share_series or liq_metrics),
            "is_draft": False,
        },
    }


# ── Public API ───────────────────────────────────────────────────────────────


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a CapitalStructureFinancialHealthOutput dict to 1–2 standard slides.

    Always produces Slide 1 (Capital Structure).
    Produces Slide 2 (Liquidity & Share Count) if any liquidity or share data
    exists; otherwise still included to note the gap.
    """
    slides = [_build_slide_1(out)]

    # Check if slide 2 has meaningful content
    liquidity = out.get("liquidity", {})
    share_count = out.get("share_count", {})

    liq_takeaways = liquidity.get("takeaways", [])
    sc_takeaways = share_count.get("takeaways", [])

    has_slide2_content = bool(liq_takeaways) or bool(sc_takeaways)

    if has_slide2_content:
        slides.append(_build_slide_2(out))

    return slides
