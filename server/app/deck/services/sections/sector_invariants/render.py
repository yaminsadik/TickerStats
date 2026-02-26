"""
Render structured SectorInvariantsOutput → slide-ready blocks.

Converts the rich JSON into 0-2 slides that conform to the pipeline's
standard SLIDE_JSON_SCHEMA (slide_id, title, bullets, speaker_notes,
layout_hints, flags).

Layout strategy:
  0 modules → 1 minimal slide (insufficient data) or [] if pipeline supports it
  1 module  → 1 slide: title = module.title, bullets from module
  2 modules → 1 slide: combined with sub-section headers in bullets
"""

from __future__ import annotations

from typing import Any


_MAX_BULLETS_PER_SLIDE = 4


def _bullet(text: str, source_needed: bool = False) -> dict[str, Any]:
    """Create a bullet dict matching SLIDE_JSON_SCHEMA."""
    return {"text": text, "source_needed": source_needed}


def _format_kpi(kpi: dict[str, Any]) -> str:
    """Format a KPI item for speaker notes."""
    label = kpi.get("label", "KPI")
    value = kpi.get("value") or "N/A"
    as_of = kpi.get("as_of")
    s = f"{label}: {value}"
    if as_of:
        s += f" ({as_of})"
    return s


def render_to_slides(out: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Convert a SectorInvariantsOutput dict to a list of slide dicts.

    Returns 0-2 slides depending on included modules.
    """
    included = out.get("included_modules", [])
    modules = out.get("modules", [])
    low_flag = out.get("low_confidence_flag", False)
    notes_text = out.get("notes") or ""

    if not included or not modules:
        return _render_empty(low_flag, notes_text)

    # Build a map from module id -> module dict
    mod_map: dict[str, dict[str, Any]] = {}
    for m in modules:
        mod_map[m.get("id", "")] = m

    # Only render modules that are in included list
    ordered = [mod_map[mid] for mid in included if mid in mod_map]

    if not ordered:
        return _render_empty(low_flag, notes_text)

    if len(ordered) == 1:
        return [_render_single_module(ordered[0], low_flag, notes_text)]

    # 2 modules → single combined slide
    return [_render_combined(ordered, low_flag, notes_text)]


def _render_empty(low_flag: bool, notes_text: str) -> list[dict[str, Any]]:
    """
    Return a single minimal slide indicating insufficient data.

    The pipeline requires min 1 slide, so we always return one.
    """
    speaker_notes_parts: list[str] = []
    if notes_text:
        speaker_notes_parts.append(notes_text)
    speaker_notes_parts.append("Low confidence: limited disclosure.")

    return [
        {
            "slide_id": "sector_invariants_1",
            "title": "Sector Invariants",
            "bullets": [
                _bullet("Insufficient sector KPI disclosure in provided inputs."),
            ],
            "speaker_notes": "\n".join(speaker_notes_parts),
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
    ]


def _render_single_module(
    mod: dict[str, Any],
    low_flag: bool,
    notes_text: str,
) -> dict[str, Any]:
    """Render a single module into one slide."""
    title = mod.get("title", "Sector Invariants")
    bullets_raw = mod.get("bullets", [])[:_MAX_BULLETS_PER_SLIDE]
    bullets = [_bullet(b) for b in bullets_raw]

    # Speaker notes: KPIs + failure modes
    notes_parts: list[str] = []

    kpis = mod.get("kpis", [])
    if kpis:
        kpi_lines = [_format_kpi(k) for k in kpis]
        notes_parts.append("KPIs:\n" + "\n".join(f"  • {l}" for l in kpi_lines))

    failure_modes = mod.get("failure_modes", [])
    if failure_modes:
        notes_parts.append(
            "Failure modes:\n"
            + "\n".join(f"  • {f}" for f in failure_modes)
        )

    if mod.get("notes"):
        notes_parts.append(f"Notes: {mod['notes']}")

    if notes_text:
        notes_parts.append(notes_text)

    if low_flag:
        notes_parts.append("Low confidence: limited disclosure.")

    return {
        "slide_id": "sector_invariants_1",
        "title": title,
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "bullets",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": bool(kpis),
            "is_draft": False,
        },
    }


def _render_combined(
    modules: list[dict[str, Any]],
    low_flag: bool,
    notes_text: str,
) -> dict[str, Any]:
    """Render 2 modules into a single combined slide with sub-section headers."""
    bullets: list[dict[str, Any]] = []
    notes_parts: list[str] = []

    # Module display titles for sub-section headers
    _SECTION_LABELS = {
        "revenue_quality_gtm": "Revenue Quality & GTM",
        "platform_dependencies_risk": "Dependencies & Risk",
        "security_reliability": "Security & Reliability",
    }

    for mod in modules:
        mod_id = mod.get("id", "")
        label = _SECTION_LABELS.get(mod_id, mod.get("title", "Module"))
        mod_bullets = mod.get("bullets", [])

        # Add sub-section header + 2-3 bullets (fit within 4 total)
        remaining = _MAX_BULLETS_PER_SLIDE - len(bullets)
        if remaining <= 0:
            break

        # Take up to 2 bullets per module when combined, to leave room
        take = min(2, len(mod_bullets), remaining)
        if take > 0:
            # First bullet includes the section label as prefix
            first_text = f"{label}: {mod_bullets[0]}"
            bullets.append(_bullet(first_text))
            for b in mod_bullets[1:take]:
                bullets.append(_bullet(b))

        # Speaker notes: KPIs for this module
        kpis = mod.get("kpis", [])
        if kpis:
            kpi_lines = [_format_kpi(k) for k in kpis]
            notes_parts.append(
                f"{label} KPIs:\n" + "\n".join(f"  • {l}" for l in kpi_lines)
            )

        failure_modes = mod.get("failure_modes", [])
        if failure_modes:
            notes_parts.append(
                f"{label} failure modes:\n"
                + "\n".join(f"  • {f}" for f in failure_modes)
            )

        if mod.get("notes"):
            notes_parts.append(f"[{mod_id}] {mod['notes']}")

    if notes_text:
        notes_parts.append(notes_text)

    if low_flag:
        notes_parts.append("Low confidence: limited disclosure.")

    return {
        "slide_id": "sector_invariants_1",
        "title": "Sector Invariants",
        "bullets": bullets,
        "speaker_notes": "\n".join(notes_parts),
        "layout_hints": {
            "style": "two_column",
            "max_bullets": _MAX_BULLETS_PER_SLIDE,
            "suggested_visual": None,
        },
        "flags": {
            "needs_sources": False,
            "contains_numbers": any(
                bool(m.get("kpis")) for m in modules
            ),
            "is_draft": False,
        },
    }
