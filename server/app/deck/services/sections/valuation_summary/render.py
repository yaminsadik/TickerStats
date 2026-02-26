"""Render ValuationSummaryOutput -> slide-ready blocks."""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    return {"text": text, "source_needed": source_needed}


def render_to_slides(
    out: dict[str, Any],
    deck_length: str = "standard",
) -> list[dict[str, Any]]:
    """Convert ValuationSummaryOutput dict to 1-2 standard slides."""
    slides: list[dict[str, Any]] = []
    trust_mode = out.get("trust_mode", "user_auto_fetch")
    narrative_only = trust_mode == "narrative_only"

    # --- Slide 1: Valuation Summary ---
    bullets_1: list[dict[str, Any]] = []
    notes_parts: list[str] = []

    # Methods line
    methods = out.get("methods") or []
    if methods:
        method_names = [m.get("method", "") for m in methods]
        bullets_1.append(_bullet(f"Methods: {' / '.join(method_names)}"))

    # DCF result
    dcf = out.get("dcf") or {}
    if dcf.get("included") and not narrative_only:
        vps = dcf.get("value_per_share")
        ud = dcf.get("upside_downside")
        if vps and ud:
            bullets_1.append(_bullet(
                f"DCF implies {vps} ({ud})",
                source_needed=True,
            ))
        elif vps:
            bullets_1.append(_bullet(
                f"DCF implies {vps}",
                source_needed=True,
            ))

    # User targets (skip in narrative_only — they contain numbers)
    if not narrative_only:
        for target in (out.get("user_targets") or []):
            if len(bullets_1) >= _MAX_BULLETS_PER_SLIDE:
                break
            bullets_1.append(_bullet(target, source_needed=False))

    # Peer set
    peers = out.get("peer_set") or []
    if peers and len(bullets_1) < _MAX_BULLETS_PER_SLIDE:
        bullets_1.append(_bullet(f"Peers: {', '.join(peers)}"))

    # Sensitivities as bullets (if space)
    sensitivities = out.get("sensitivities") or []
    if sensitivities and len(bullets_1) < _MAX_BULLETS_PER_SLIDE:
        bullets_1.append(_bullet(f"Key sensitivity: {sensitivities[0]}"))

    # Ensure at least one bullet
    if not bullets_1:
        methods_text = (
            ", ".join(m.get("method", "") for m in methods)
            if methods
            else "None selected"
        )
        bullets_1.append(_bullet(f"Valuation methods: {methods_text}"))

    # Speaker notes
    if dcf.get("included"):
        assumptions = dcf.get("key_assumptions") or []
        if assumptions:
            notes_parts.append("DCF Key Assumptions:")
            for a in assumptions:
                notes_parts.append(f"  - {a}")
        source = dcf.get("source_note")
        if source:
            notes_parts.append(f"Source: {source}")

    # Remaining sensitivities in notes
    remaining_sens = sensitivities[1:] if len(bullets_1) > 1 else sensitivities
    if remaining_sens:
        notes_parts.append("Key Sensitivities:")
        for s in remaining_sens:
            notes_parts.append(f"  - {s}")

    # Low confidence flag
    if out.get("low_confidence_flag"):
        missing: list[str] = []
        if not methods:
            missing.append("no methods selected")
        if not out.get("user_targets"):
            missing.append("no user targets")
        if not dcf.get("included"):
            missing.append("no DCF output")
        if missing:
            notes_parts.append(f"Missing inputs: {', '.join(missing)}")

    contains_numbers = bool(
        dcf.get("included") or out.get("user_targets")
    ) and not narrative_only

    slides.append({
        "slide_id": "valuation_summary_1",
        "title": "Valuation Summary",
        "bullets": bullets_1[:_MAX_BULLETS_PER_SLIDE],
        "speaker_notes": "\n".join(notes_parts) if notes_parts else "",
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": dcf.get("included", False),
            "contains_numbers": contains_numbers,
            "is_draft": False,
        },
    })

    # --- Optional Slide 2 (deep only) ---
    if deck_length == "deep":
        bullets_2: list[dict[str, Any]] = []

        # Extended peer list
        if peers and len(peers) > 3:
            bullets_2.append(_bullet(f"Peer set: {', '.join(peers)}"))

        # DCF assumptions text excerpt
        val = out.get("_valuation_input") or {}
        dcf_text = val.get("dcf_assumptions") or ""
        if dcf_text and not narrative_only:
            excerpt = dcf_text[:200] + ("..." if len(dcf_text) > 200 else "")
            bullets_2.append(_bullet(f"DCF assumptions: {excerpt}"))

        # All sensitivities as bullets
        for s in sensitivities:
            if len(bullets_2) >= _MAX_BULLETS_PER_SLIDE:
                break
            bullets_2.append(_bullet(s))

        if bullets_2:
            slides.append({
                "slide_id": "valuation_summary_2",
                "title": "Valuation Inputs",
                "bullets": bullets_2[:_MAX_BULLETS_PER_SLIDE],
                "speaker_notes": "",
                "layout_hints": {
                    "style": "bullets",
                    "max_bullets": _MAX_BULLETS_PER_SLIDE,
                    "suggested_visual": None,
                },
                "flags": {
                    "needs_sources": False,
                    "contains_numbers": not narrative_only,
                    "is_draft": False,
                },
            })

    return slides
