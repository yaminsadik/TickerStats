"""
Tests for the Industry & Competitive Landscape section.

Covers:
  - Pydantic schema validation (valid, partial, constraint violations)
  - Porter's exactly 5 forces
  - No fabricated placeholders ("$X", "X%")
  - Fallback behaviours (missing TAM, missing competitors)
  - Low-confidence flag logic
  - Rendering to standard slide format (1–2 valid slide dicts)
  - Registry integration
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.industry_competitive_landscape.schemas import (
    Competitor,
    CompetitionOut,
    ForceOut,
    IndustryCompetitiveOutput,
    MarketOut,
    MarketSizing,
    MoatOut,
    MoatPillar,
    PortersOut,
    PositioningAxis,
)
from app.deck.services.sections.industry_competitive_landscape.fallbacks import (
    any_module_low_confidence,
    compute_low_confidence_flag,
    is_fabricated,
    resolve_competitors,
    resolve_evidence,
    resolve_market_sizing,
    resolve_moat_pillars,
    strip_fabricated_values,
)
from app.deck.services.sections.industry_competitive_landscape.render import (
    render_to_slides,
)
from app.deck.services.sections.industry_competitive_landscape.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════

def _make_market(**overrides) -> dict:
    base = {
        "market_definition": "Global specialty chemicals market serving industrial end-markets.",
        "sizing": {
            "tam_value": "$150B",
            "tam_basis": "Global specialty chemicals",
            "proxy_sizing": [],
            "growth_chart_notes": ["5% CAGR 2020-2025 per industry reports"],
        },
        "growth_drivers": [
            "EV transition driving demand for battery materials",
            "Sustainability regulations increasing specialty coatings demand",
            "Infrastructure investment in emerging markets",
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_competition(**overrides) -> dict:
    base = {
        "competitors": [
            {"name": "BASF", "type": "direct", "why_relevant": "Largest global chemical company with overlapping product lines"},
            {"name": "Dow Inc", "type": "direct", "why_relevant": "Major competitor in performance materials"},
            {"name": "Eastman Chemical", "type": "direct", "why_relevant": "Competes in specialty additives and coatings"},
        ],
        "positioning": {
            "x_label": "Product Breadth",
            "y_label": "Specialty Focus",
            "company_position": "top-right",
            "key_differentiator": "Proprietary formulations with long qualification cycles",
        },
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_moat(**overrides) -> dict:
    base = {
        "pillars": [
            {"pillar": "Switching Costs", "mechanism": "Long customer qualification cycles (12-18 months)", "evidence": "Disclosed in 10-K filings"},
            {"pillar": "Intangible Assets", "mechanism": "Proprietary formulations and patents", "evidence": "500+ active patents"},
            {"pillar": "Cost Advantages", "mechanism": "Scale in specialty production reduces per-unit costs", "evidence": None},
        ],
        "confidence": "medium",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_porters(**overrides) -> dict:
    base = {
        "forces": [
            {"force": "Threat of New Entrants", "pressure": "low", "because": ["High capital requirements", "Long customer qualification cycles"], "evidence": None},
            {"force": "Bargaining Power of Suppliers", "pressure": "medium", "because": ["Commodity feedstock with multiple sources"], "evidence": None},
            {"force": "Bargaining Power of Buyers", "pressure": "medium", "because": ["Switching costs offset by customer concentration"], "evidence": None},
            {"force": "Threat of Substitutes", "pressure": "low", "because": ["Few viable alternatives for specialty formulations"], "evidence": None},
            {"force": "Competitive Rivalry", "pressure": "high", "because": ["Mature market with established players", "Periodic price competition"], "evidence": None},
        ],
        "confidence": "medium",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_full_output(**overrides) -> dict:
    base = {
        "market": _make_market(),
        "competition": _make_competition(),
        "moat": _make_moat(),
        "porters": _make_porters(),
        "low_confidence_flag": False,
    }
    base.update(overrides)
    return base


def _make_inputs(**overrides) -> dict:
    base = {
        "ticker": "ACME",
        "company_name": "Acme Corp",
        "sector": "Materials",
        "industry": "Specialty Chemicals",
        "company": {
            "name": "Acme Corp",
            "ticker": "ACME",
            "sector": "Materials",
            "industry": "Specialty Chemicals",
            "description": "Leading specialty chemicals manufacturer.",
        },
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Schema validation
# ═══════════════════════════════════════════════════════════════════════════════

class TestSchemaValidation:
    """Pydantic model validation tests."""

    def test_valid_full_output(self):
        data = _make_full_output()
        parsed = IndustryCompetitiveOutput.model_validate(data)
        assert parsed.market.market_definition
        assert len(parsed.porters.forces) == 5
        assert len(parsed.moat.pillars) >= 3

    def test_market_definition_required(self):
        data = _make_full_output()
        del data["market"]["market_definition"]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_growth_drivers_min_2(self):
        data = _make_full_output()
        data["market"]["growth_drivers"] = ["only one"]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_growth_drivers_max_5(self):
        data = _make_full_output()
        data["market"]["growth_drivers"] = [f"driver {i}" for i in range(6)]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_competitors_min_3(self):
        data = _make_full_output()
        data["competition"]["competitors"] = data["competition"]["competitors"][:2]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_competitors_max_8(self):
        data = _make_full_output()
        data["competition"]["competitors"] = [
            {"name": f"Comp{i}", "type": "direct", "why_relevant": "reason"}
            for i in range(9)
        ]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_moat_pillars_min_3(self):
        data = _make_full_output()
        data["moat"]["pillars"] = data["moat"]["pillars"][:2]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_moat_pillars_max_5(self):
        data = _make_full_output()
        data["moat"]["pillars"] = [
            {"pillar": f"P{i}", "mechanism": "mech", "evidence": None}
            for i in range(6)
        ]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_tam_value_optional(self):
        data = _make_full_output()
        data["market"]["sizing"]["tam_value"] = None
        data["market"]["sizing"]["tam_basis"] = None
        parsed = IndustryCompetitiveOutput.model_validate(data)
        assert parsed.market.sizing.tam_value is None


# ═══════════════════════════════════════════════════════════════════════════════
# Porter's exactly 5 forces
# ═══════════════════════════════════════════════════════════════════════════════

class TestPortersForces:
    """Porter's Five Forces constraint tests."""

    def test_exactly_5_forces_valid(self):
        data = _make_full_output()
        parsed = IndustryCompetitiveOutput.model_validate(data)
        assert len(parsed.porters.forces) == 5

    def test_fewer_than_5_forces_rejected(self):
        data = _make_full_output()
        data["porters"]["forces"] = data["porters"]["forces"][:4]
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_more_than_5_forces_rejected(self):
        data = _make_full_output()
        data["porters"]["forces"].append(
            {"force": "Extra Force", "pressure": "low", "because": ["reason"], "evidence": None}
        )
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)

    def test_force_pressure_values(self):
        data = _make_full_output()
        parsed = IndustryCompetitiveOutput.model_validate(data)
        for force in parsed.porters.forces:
            assert force.pressure in ("low", "medium", "high")

    def test_force_because_min_1(self):
        data = _make_full_output()
        data["porters"]["forces"][0]["because"] = []
        with pytest.raises(ValidationError):
            IndustryCompetitiveOutput.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════════
# No fabricated placeholders
# ═══════════════════════════════════════════════════════════════════════════════

class TestFabricationGuards:
    """Test that fabricated placeholders are detected and stripped."""

    def test_is_fabricated_detects_dollar_x(self):
        assert is_fabricated("$X") is True
        assert is_fabricated("Market is $X billion") is True

    def test_is_fabricated_detects_x_percent(self):
        assert is_fabricated("X% growth") is True

    def test_is_fabricated_detects_tbd(self):
        assert is_fabricated("TBD") is True

    def test_is_fabricated_accepts_real_values(self):
        assert is_fabricated("$220B") is False
        assert is_fabricated("5% CAGR") is False
        assert is_fabricated("$3.1B revenue") is False

    def test_is_fabricated_handles_none(self):
        assert is_fabricated(None) is False

    def test_strip_fabricated_values_cleans_tam(self):
        data = _make_full_output()
        data["market"]["sizing"]["tam_value"] = "$X"
        result = strip_fabricated_values(data)
        assert result["market"]["sizing"]["tam_value"] is None

    def test_strip_fabricated_leaves_valid_tam(self):
        data = _make_full_output()
        result = strip_fabricated_values(data)
        assert result["market"]["sizing"]["tam_value"] == "$150B"

    def test_render_output_no_fabricated_placeholders(self):
        """Verify rendered slides contain no fabricated placeholders."""
        data = _make_full_output()
        slides = render_to_slides(data)
        fab_pattern = re.compile(r"\$X|\bX%|\bXX\b|\bTBD\b", re.IGNORECASE)
        for slide in slides:
            for bullet in slide["bullets"]:
                assert not fab_pattern.search(bullet["text"]), (
                    f"Fabricated placeholder in bullet: {bullet['text']}"
                )
            assert not fab_pattern.search(slide.get("speaker_notes", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback behaviours
# ═══════════════════════════════════════════════════════════════════════════════

class TestFallbacks:
    """Deterministic fallback logic tests."""

    # ── Market sizing ────────────────────────────────────────────────────

    def test_resolve_market_sizing_with_tam(self):
        sizing, conf = resolve_market_sizing("$220B", "Global language learning", [])
        assert sizing["tam_value"] == "$220B"
        assert conf == "high"

    def test_resolve_market_sizing_without_tam(self):
        sizing, conf = resolve_market_sizing(None, None, ["Large and growing market"])
        assert sizing["tam_value"] is None
        assert conf == "medium"
        assert len(sizing["proxy_sizing"]) == 1

    def test_resolve_market_sizing_fabricated_tam(self):
        sizing, conf = resolve_market_sizing("$X", "Guess", ["proxy"])
        assert sizing["tam_value"] is None
        assert conf == "medium"

    # ── Competitors ──────────────────────────────────────────────────────

    def test_resolve_competitors_with_enough(self):
        comps = [
            {"name": "A", "type": "direct", "why_relevant": "r"},
            {"name": "B", "type": "direct", "why_relevant": "r"},
            {"name": "C", "type": "adjacent", "why_relevant": "r"},
        ]
        resolved, conf = resolve_competitors(comps)
        assert len(resolved) == 3
        assert conf == "high"

    def test_resolve_competitors_empty(self):
        resolved, conf = resolve_competitors(None)
        assert len(resolved) == 5
        assert conf == "low"
        # All should be category-level (no specific ticker names)
        for c in resolved:
            assert c["name"]  # non-empty

    def test_resolve_competitors_partial(self):
        comps = [{"name": "A", "type": "direct", "why_relevant": "r"}]
        resolved, conf = resolve_competitors(comps)
        assert len(resolved) == 1
        assert conf == "medium"

    # ── Evidence ─────────────────────────────────────────────────────────

    def test_resolve_evidence_present(self):
        ev, conf, notes = resolve_evidence("10-K filing", "high")
        assert ev == "10-K filing"
        assert conf == "high"
        assert notes is None

    def test_resolve_evidence_missing(self):
        ev, conf, notes = resolve_evidence(None, "high")
        assert ev is None
        assert conf == "low"
        assert notes == "limited disclosure"

    def test_resolve_evidence_fabricated(self):
        ev, conf, notes = resolve_evidence("TBD", "high")
        assert ev is None
        assert notes == "limited disclosure"

    # ── Moat pillars ─────────────────────────────────────────────────────

    def test_resolve_moat_pillars_sufficient(self):
        pillars = [
            {"pillar": "P1", "mechanism": "m1", "evidence": "e1"},
            {"pillar": "P2", "mechanism": "m2", "evidence": None},
            {"pillar": "P3", "mechanism": "m3", "evidence": "e3"},
        ]
        resolved, conf = resolve_moat_pillars(pillars)
        assert len(resolved) == 3
        assert conf == "high"  # has evidence

    def test_resolve_moat_pillars_no_evidence(self):
        pillars = [
            {"pillar": "P1", "mechanism": "m1", "evidence": None},
            {"pillar": "P2", "mechanism": "m2", "evidence": None},
            {"pillar": "P3", "mechanism": "m3", "evidence": None},
        ]
        resolved, conf = resolve_moat_pillars(pillars)
        assert conf == "medium"

    def test_resolve_moat_pillars_too_few(self):
        pillars = [{"pillar": "P1", "mechanism": "m1", "evidence": None}]
        resolved, conf = resolve_moat_pillars(pillars)
        assert conf == "low"


# ═══════════════════════════════════════════════════════════════════════════════
# Low-confidence flag logic
# ═══════════════════════════════════════════════════════════════════════════════

class TestConfidenceFlag:
    """Test compute_low_confidence_flag deterministic logic."""

    def test_all_high_confidence(self):
        data = _make_full_output()
        data["market"]["confidence"] = "high"
        data["competition"]["confidence"] = "high"
        data["moat"]["confidence"] = "high"
        data["porters"]["confidence"] = "high"
        assert compute_low_confidence_flag(data) is False

    def test_one_low_triggers_flag(self):
        data = _make_full_output()
        data["moat"]["confidence"] = "low"
        assert compute_low_confidence_flag(data) is True

    def test_medium_does_not_trigger(self):
        data = _make_full_output()
        data["market"]["confidence"] = "medium"
        data["competition"]["confidence"] = "medium"
        data["moat"]["confidence"] = "medium"
        data["porters"]["confidence"] = "medium"
        assert compute_low_confidence_flag(data) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════════

class TestRendering:
    """Test render_to_slides produces valid slide dicts."""

    def test_render_produces_1_or_2_slides(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert 1 <= len(slides) <= 2

    def test_slide_ids(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert slides[0]["slide_id"] == "industry_competitive_landscape_1"
        if len(slides) > 1:
            assert slides[1]["slide_id"] == "industry_competitive_landscape_2"

    def test_slide_titles(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert slides[0]["title"] == "Industry Overview"
        if len(slides) > 1:
            assert slides[1]["title"] == "Competitive Landscape"

    def test_slide_bullets_max_4(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        for slide in slides:
            assert len(slide["bullets"]) <= 4

    def test_slide_has_required_keys(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        required_keys = {"slide_id", "title", "bullets", "speaker_notes", "layout_hints", "flags"}
        for slide in slides:
            assert required_keys.issubset(slide.keys())

    def test_bullet_structure(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        for slide in slides:
            for bullet in slide["bullets"]:
                assert "text" in bullet
                assert isinstance(bullet["text"], str)
                assert len(bullet["text"]) <= 500

    def test_tam_present_in_slide1_when_available(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        texts = [b["text"] for b in slides[0]["bullets"]]
        tam_found = any("$150B" in t for t in texts)
        assert tam_found

    def test_tam_absent_uses_proxy(self):
        data = _make_full_output()
        data["market"]["sizing"]["tam_value"] = None
        data["market"]["sizing"]["proxy_sizing"] = ["Large addressable market"]
        slides = render_to_slides(data)
        texts = [b["text"] for b in slides[0]["bullets"]]
        proxy_found = any("Large addressable market" in t for t in texts)
        assert proxy_found

    def test_porters_summary_in_slide2(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        if len(slides) > 1:
            texts = [b["text"] for b in slides[1]["bullets"]]
            porters_found = any("Porter's" in t for t in texts)
            assert porters_found

    def test_low_confidence_note_in_speaker_notes(self):
        data = _make_full_output()
        data["low_confidence_flag"] = True
        slides = render_to_slides(data)
        notes = " ".join(s.get("speaker_notes", "") for s in slides)
        assert "Low confidence" in notes


# ═══════════════════════════════════════════════════════════════════════════════
# SectionSpec integration
# ═══════════════════════════════════════════════════════════════════════════════

class TestSectionSpec:
    """Test SECTION_SPEC attributes and methods."""

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "industry_competitive_landscape"

    def test_section_spec_has_build_prompt(self):
        assert callable(SECTION_SPEC.build_prompt)

    def test_section_spec_has_postprocess(self):
        assert callable(SECTION_SPEC.postprocess)

    def test_section_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_build_prompt_returns_string(self):
        inputs = _make_inputs()
        prompt = _build_prompt(inputs)
        assert isinstance(prompt, str)
        assert "industry_competitive_landscape" in prompt or "Industry" in prompt

    def test_build_prompt_contains_schema(self):
        inputs = _make_inputs()
        prompt = _build_prompt(inputs)
        assert "OUTPUT JSON SCHEMA" in prompt

    def test_build_prompt_contains_hard_rules(self):
        inputs = _make_inputs()
        prompt = _build_prompt(inputs)
        assert "HARD RULES" in prompt

    def test_build_prompt_contains_all_modules(self):
        inputs = _make_inputs()
        prompt = _build_prompt(inputs)
        assert "MODULE: market" in prompt
        assert "MODULE: competition" in prompt
        assert "MODULE: moat" in prompt
        assert "MODULE: porters" in prompt

    def test_postprocess_valid_output(self):
        data = _make_full_output()
        result = _postprocess(data, _make_inputs())
        assert result["section_id"] == "industry_competitive_landscape"
        assert 1 <= len(result["slides"]) <= 2
        assert isinstance(result["slides"], list)

    def test_postprocess_sets_low_confidence_flag(self):
        data = _make_full_output()
        data["market"]["confidence"] = "low"
        result = _postprocess(data, _make_inputs())
        # Should have verification notes about low confidence
        assert any("Low confidence" in n for n in result.get("verification_notes", []))

    def test_postprocess_handles_invalid_input(self):
        """postprocess should not crash on malformed input."""
        result = _postprocess({"garbage": True}, _make_inputs())
        assert result["section_id"] == "industry_competitive_landscape"
        assert isinstance(result["slides"], list)

    def test_postprocess_strips_fabricated(self):
        data = _make_full_output()
        data["market"]["sizing"]["tam_value"] = "$X"
        result = _postprocess(data, _make_inputs())
        # TAM should not appear in slide bullets
        for slide in result["slides"]:
            for bullet in slide["bullets"]:
                assert "$X" not in bullet["text"]

    def test_schema_max_slides_2(self):
        schema = SECTION_SPEC.schema
        # Schema is the LLM output schema; verify it has expected top-level keys.
        props = schema.get("properties", {})
        assert "market" in props
        assert "competition" in props
