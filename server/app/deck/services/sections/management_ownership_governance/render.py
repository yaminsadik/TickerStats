"""
Render structured ManagementOwnershipGovernanceOutput → slide-ready blocks.

Converts the rich JSON into 1–2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Slide 1 — "Management & Incentives"
Slide 2 (optional) — "Ownership & Governance"
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


# ── Slide 1: Management & Incentives ─────────────────────────────────────────

def _build_slide_1(output: dict[str, Any]) -> dict[str, Any]:
    """Management track record + alignment + incentive summary."""
    mgmt = output.get("management", {})

    bullets: list[dict[str, Any]] = []

    # Track record bullets (2–5, take up to 4 for slide)
    for tr in mgmt.get("track_record", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(tr))

    # If room: alignment summary bullets
    for al in mgmt.get("alignment_summary", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(al))

    # If room and incentives present: summarize comp alignment
    incentives = mgmt.get("incentives", [])
    if incentives and len(bullets) < _MAX_BULLETS_PER_SLIDE:
        comps = [inc.get("component", "") for inc in incentives[:3] if isinstance(inc, dict)]
        if comps:
            inc_text = "Incentive structure: " + ", ".join(comps)
            if len(inc_text) > 500:
                inc_text = inc_text[:497] + "..."
            bullets.append(_bullet(inc_text))

    # Speaker notes: executives + incentive detail
    notes_parts: list[str] = []

    executives = mgmt.get("executives", [])
    if executives:
        exec_lines = []
        for ex in executives:
            if not isinstance(ex, dict):
                continue
            name = ex.get("name") or "Unknown"
            role = ex.get("role") or ""
            since = ex.get("since") or ""
            equity = ex.get("equity_ownership") or ""
            line = f"  • {name}"
            if role:
                line += f", {role}"
            if since:
                line += f" (since {since})"
            if equity:
                line += f" — equity: {equity}"
            exec_lines.append(line)
        notes_parts.append("Executives:\n" + "\n".join(exec_lines))

    if incentives:
        inc_lines = []
        for inc in incentives:
            if not isinstance(inc, dict):
                continue
            comp = inc.get("component", "")
            metric = inc.get("metric_link", "")
            weight = inc.get("weight", "")
            line = f"  • {comp}"
            if metric:
                line += f" (linked to: {metric})"
            if weight:
                line += f" [{weight}]"
            inc_lines.append(line)
        notes_parts.append("Incentive components:\n" + "\n".join(inc_lines))

    # Confidence and notes
    if mgmt.get("notes"):
        notes_parts.append(f"Notes: {mgmt['notes']}")
    notes_parts.append(f"Management confidence: {mgmt.get('confidence', 'medium')}")

    return {
        "slide_id": "management_ownership_governance_1",
        "title": "Management & Incentives",
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


# ── Slide 2: Ownership & Governance ─────────────────────────────────────────

def _should_include_slide_2(output: dict[str, Any]) -> bool:
    """Include slide 2 if any of: holders, flags, or activist_presence."""
    own = output.get("ownership", {})
    gov = output.get("governance", {})

    if own.get("top_holders"):
        return True
    if gov.get("flags"):
        return True
    if own.get("activist_presence"):
        return True
    return False


def _build_slide_2(output: dict[str, Any]) -> dict[str, Any]:
    """Ownership takeaways + governance flags summary."""
    own = output.get("ownership", {})
    gov = output.get("governance", {})

    bullets: list[dict[str, Any]] = []

    # Ownership takeaways (1–3)
    for tw in own.get("takeaways", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(tw))

    # Governance takeaways (1–3)
    for tw in gov.get("takeaways", []):
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        bullets.append(_bullet(tw))

    # Governance flags summary (up to 5, fit in remaining slots)
    for flag in gov.get("flags", [])[:5]:
        if len(bullets) >= _MAX_BULLETS_PER_SLIDE:
            break
        if not isinstance(flag, dict):
            continue
        ftype = flag.get("flag_type", "")
        fact = flag.get("fact", "")
        severity = flag.get("severity", "")
        flag_text = f"{ftype}: {fact} ({severity})"
        if len(flag_text) > 500:
            flag_text = flag_text[:497] + "..."
        bullets.append(_bullet(flag_text))

    # Speaker notes: full holder list + full flags
    notes_parts: list[str] = []

    holders = own.get("top_holders", [])
    if holders:
        holder_lines = []
        for h in holders:
            if not isinstance(h, dict):
                continue
            name = h.get("name", "Unknown")
            htype = h.get("holder_type", "")
            stake = h.get("stake", "")
            comment = h.get("comment", "")
            line = f"  • {name} ({htype})"
            if stake:
                line += f": {stake}"
            if comment:
                line += f" — {comment}"
            holder_lines.append(line)
        notes_parts.append("Top Holders:\n" + "\n".join(holder_lines))

    if own.get("insider_ownership_summary"):
        notes_parts.append(f"Insider ownership: {own['insider_ownership_summary']}")

    if own.get("activist_presence"):
        notes_parts.append(f"Activist presence: {own['activist_presence']}")

    flags = gov.get("flags", [])
    if flags:
        flag_lines = []
        for f in flags:
            if not isinstance(f, dict):
                continue
            ftype = f.get("flag_type", "")
            severity = f.get("severity", "")
            fact = f.get("fact", "")
            why = f.get("why_it_matters", "")
            line = f"  • {ftype} ({severity}): {fact}"
            if why:
                line += f" — {why}"
            flag_lines.append(line)
        notes_parts.append("Governance Flags:\n" + "\n".join(flag_lines))

    # Confidence and notes
    for mod_name, mod_data in [("ownership", own), ("governance", gov)]:
        if mod_data.get("notes"):
            notes_parts.append(f"[{mod_name}] {mod_data['notes']}")

    # Low confidence footnote
    if output.get("low_confidence_flag"):
        notes_parts.append("Low confidence: limited disclosure")

    return {
        "slide_id": "management_ownership_governance_2",
        "title": "Ownership & Governance",
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


# ── Public API ───────────────────────────────────────────────────────────────

def render_to_slides(output: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a ManagementOwnershipGovernanceOutput dict into 1–2 slide dicts.

    Returns a list suitable for the ``slides`` field in the standard
    section output schema.
    """
    slide1 = _build_slide_1(output)
    slides = [slide1]

    if _should_include_slide_2(output):
        slide2 = _build_slide_2(output)
        if slide2["bullets"]:
            slides.append(slide2)

    return slides
