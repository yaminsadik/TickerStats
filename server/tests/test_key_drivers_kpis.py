"""
Tests for the Key Drivers & KPIs section.

Covers:
  - Pydantic schema validation (3..5 KPI count, constraints)
  - No placeholders ($X, X%, TBD)
  - Disclosure locations not guessed (must be not_provided when missing)
  - Fallback when <3 KPIs -> low_confidence true
  - Render produces 1-2 slide dicts in valid shape
  - Deterministic low_confidence_flag recomputation
  - Module prompt fragment generation
  - Registry integration
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.key_drivers_kpis.schemas import (
    Confidence,
    DisclosureRef,
    KPI,
    KeyDriversKpisOutput,
    SourceType,
    get_key_drivers_kpis_json_schema,
)
from app.deck.services.sections.key_drivers_kpis.fallbacks import (
    compute_confidence,
    compute_low_confidence_flag,
    resolve_disclosure,
    select_kpis_from_inputs,
)
from app.deck.services.sections.key_drivers_kpis.render import render_to_slides
from app.deck.services.sections.key_drivers_kpis.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_kpi(**overrides) -> dict:
    base = {
        "name": "Net Revenue Retention",
        "why_it_moves_value": "Higher NRR signals durable revenue expansion from existing customers without incremental acquisition cost.",
        "definition": "Annual recurring revenue retained from existing customers, including upsells and contractions, divided by beginning-period ARR.",
        "unit": "%",
        "typical_direction": "up_is_good",
        "disclosure": {
            "source_type": "10-K",
            "description": "MD&A, Key Business Metrics",
            "page_or_section": None,
            "link_label": None,
        },
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_kpi_no_disclosure(**overrides) -> dict:
    base = _make_kpi(
        disclosure={
            "source_type": "not_provided",
            "description": None,
            "page_or_section": None,
            "link_label": None,
        }
    )
    base.update(overrides)
    return base


def _make_full_output(**overrides) -> dict:
    base = {
        "kpis": [
            _make_kpi(name="Net Revenue Retention", unit="%"),
            _make_kpi(name="Annual Recurring Revenue", unit="$M", definition="Total annualized value of active subscription contracts.", why_it_moves_value="ARR growth reflects new customer acquisition and expansion success."),
            _make_kpi(name="Gross Dollar Churn", unit="%", typical_direction="down_is_good", definition="Percentage of ARR lost from cancellations and downgrades.", why_it_moves_value="Lower churn extends customer lifetime value and improves unit economics."),
        ],
        "overall_takeaways": [
            "SaaS business with strong NRR-driven organic growth flywheel",
            "Churn management is the primary value lever alongside expansion selling",
        ],
        "confidence": "high",
        "low_confidence_flag": False,
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_five_kpi_output(**overrides) -> dict:
    base = _make_full_output()
    base["kpis"] = [
        _make_kpi(name="Net Revenue Retention", unit="%"),
        _make_kpi(name="Annual Recurring Revenue", unit="$M"),
        _make_kpi(name="Gross Dollar Churn", unit="%", typical_direction="down_is_good"),
        _make_kpi(name="ARPU", unit="$/user/month"),
        _make_kpi(name="CAC Payback Period", unit="months", typical_direction="down_is_good"),
    ]
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Pydantic model validation tests."""

    def test_valid_3_kpi_output(self):
        data = _make_full_output()
        parsed = KeyDriversKpisOutput.model_validate(data)
        assert len(parsed.kpis) == 3
        assert parsed.confidence == "high"
        assert parsed.low_confidence_flag is False

    def test_valid_5_kpi_output(self):
        data = _make_five_kpi_output()
        parsed = KeyDriversKpisOutput.model_validate(data)
        assert len(parsed.kpis) == 5

    def test_too_many_kpis_rejected(self):
        data = _make_full_output()
        data["kpis"] = [_make_kpi(name=f"KPI_{i}") for i in range(6)]
        with pytest.raises(ValidationError):
            KeyDriversKpisOutput.model_validate(data)

    def test_zero_kpis_rejected(self):
        data = _make_full_output()
        data["kpis"] = []
        with pytest.raises(ValidationError):
            KeyDriversKpisOutput.model_validate(data)

    def test_1_kpi_accepted(self):
        """1-2 KPIs are acceptable (but should trigger low confidence in postprocess)."""
        data = _make_full_output()
        data["kpis"] = [_make_kpi()]
        parsed = KeyDriversKpisOutput.model_validate(data)
        assert len(parsed.kpis) == 1

    def test_2_kpis_accepted(self):
        data = _make_full_output()
        data["kpis"] = [_make_kpi(name="NRR"), _make_kpi(name="ARR")]
        parsed = KeyDriversKpisOutput.model_validate(data)
        assert len(parsed.kpis) == 2

    def test_disclosure_ref_defaults(self):
        kpi = KPI(
            name="Test",
            why_it_moves_value="Test reason.",
            definition="Test definition.",
        )
        assert kpi.disclosure.source_type == "not_provided"
        assert kpi.disclosure.description is None

    def test_valid_source_types(self):
        for st in ["10-K", "10-Q", "earnings_release", "earnings_deck",
                    "investor_presentation", "other", "not_provided"]:
            ref = DisclosureRef(source_type=st)
            assert ref.source_type == st

    def test_overall_takeaways_count(self):
        data = _make_full_output()
        data["overall_takeaways"] = []
        with pytest.raises(ValidationError):
            KeyDriversKpisOutput.model_validate(data)

    def test_overall_takeaways_max(self):
        data = _make_full_output()
        data["overall_takeaways"] = ["a", "b", "c", "d"]
        with pytest.raises(ValidationError):
            KeyDriversKpisOutput.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════════
# No-placeholder enforcement
# ═══════════════════════════════════════════════════════════════════════════════


_PLACEHOLDER_RE = re.compile(r"\$X|X%|TBD|TODO|PLACEHOLDER|INSERT|FILL_IN", re.IGNORECASE)


class TestNoPlaceholders:
    """Ensure test fixtures have no placeholder text."""

    def test_kpis_no_placeholders(self):
        data = _make_full_output()
        for kpi in data["kpis"]:
            for field_name in ("name", "why_it_moves_value", "definition"):
                assert not _PLACEHOLDER_RE.search(kpi[field_name]), (
                    f"Placeholder found in KPI.{field_name}: {kpi[field_name]}"
                )

    def test_takeaways_no_placeholders(self):
        data = _make_full_output()
        for ta in data["overall_takeaways"]:
            assert not _PLACEHOLDER_RE.search(ta), (
                f"Placeholder found in takeaway: {ta}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Disclosure location enforcement
# ═══════════════════════════════════════════════════════════════════════════════


class TestDisclosureLocations:
    """Disclosure locations must be not_provided when missing."""

    def test_missing_disclosure_marked_not_provided(self):
        ref = resolve_disclosure("NRR", None)
        assert ref["source_type"] == "not_provided"
        assert ref["description"] is None
        assert ref["page_or_section"] is None

    def test_empty_disclosure_marked_not_provided(self):
        ref = resolve_disclosure("NRR", {})
        assert ref["source_type"] == "not_provided"

    def test_valid_disclosure_preserved(self):
        ref = resolve_disclosure("NRR", {
            "source_type": "10-K",
            "description": "MD&A, Key Business Metrics",
            "page_or_section": "p. 42",
        })
        assert ref["source_type"] == "10-K"
        assert ref["description"] == "MD&A, Key Business Metrics"
        assert ref["page_or_section"] == "p. 42"

    def test_invalid_source_type_falls_back_to_other(self):
        ref = resolve_disclosure("NRR", {"source_type": "blog_post"})
        assert ref["source_type"] == "other"


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback / confidence tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbacks:
    """Deterministic fallback logic for KPI selection and confidence."""

    def test_explicit_kpis_selected(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Technology",
            "kpis": ["NRR", "ARR", "Churn"],
        }
        kpi_hints, conf, notes = select_kpis_from_inputs(inputs)
        assert len(kpi_hints) == 3
        assert conf == "high"
        assert notes is None

    def test_explicit_kpis_too_few_low_confidence(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Technology",
            "kpis": ["NRR"],
        }
        kpi_hints, conf, notes = select_kpis_from_inputs(inputs)
        assert len(kpi_hints) == 1
        assert conf == "low"
        assert "insufficient" in notes.lower()

    def test_no_kpis_returns_low_confidence(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Unknown Sector",
        }
        kpi_hints, conf, notes = select_kpis_from_inputs(inputs)
        assert conf == "low"
        assert "insufficient" in notes.lower()

    def test_business_model_metrics_extracted(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Technology",
            "business_model_segments": {
                "unit_economics": ["ARPU", "churn", "LTV/CAC"],
            },
        }
        kpi_hints, conf, notes = select_kpis_from_inputs(inputs)
        assert len(kpi_hints) == 3
        assert conf == "medium"

    def test_compute_confidence_high(self):
        assert compute_confidence(4, False) == "high"

    def test_compute_confidence_medium(self):
        assert compute_confidence(3, True) == "medium"

    def test_compute_confidence_low(self):
        assert compute_confidence(2, False) == "low"

    def test_low_confidence_flag_when_confidence_low(self):
        assert compute_low_confidence_flag("low", []) is True

    def test_low_confidence_flag_when_disclosure_missing(self):
        kpis = [
            {"disclosure": {"source_type": "10-K"}},
            {"disclosure": {"source_type": "not_provided"}},
        ]
        assert compute_low_confidence_flag("high", kpis) is True

    def test_no_low_confidence_flag_when_all_disclosed(self):
        kpis = [
            {"disclosure": {"source_type": "10-K"}},
            {"disclosure": {"source_type": "10-Q"}},
            {"disclosure": {"source_type": "earnings_release"}},
        ]
        assert compute_low_confidence_flag("high", kpis) is False

    def test_max_5_kpis_selected(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Technology",
            "kpis": ["A", "B", "C", "D", "E", "F", "G"],
        }
        kpi_hints, _, _ = select_kpis_from_inputs(inputs)
        assert len(kpi_hints) <= 5


# ═══════════════════════════════════════════════════════════════════════════════
# Render tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRender:
    """Rendering to standard slide format."""

    def test_render_produces_1_slide_for_3_kpis(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert len(slides) == 1
        slide = slides[0]
        assert slide["slide_id"] == "key_drivers_kpis_1"
        assert slide["title"] == "Key Drivers & KPIs"
        assert len(slide["bullets"]) >= 1
        assert len(slide["bullets"]) <= 4

    def test_render_produces_2_slides_for_5_kpis(self):
        data = _make_five_kpi_output()
        slides = render_to_slides(data)
        # With >3 KPIs, a second summary slide is generated
        assert len(slides) == 2
        assert slides[0]["slide_id"] == "key_drivers_kpis_1"
        assert slides[1]["slide_id"] == "key_drivers_kpis_2"

    def test_slide_has_valid_shape(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        slide = slides[0]
        # Required fields
        assert "slide_id" in slide
        assert "title" in slide
        assert "bullets" in slide
        assert "speaker_notes" in slide
        assert "layout_hints" in slide
        assert "flags" in slide
        # Bullets are dicts with "text"
        for b in slide["bullets"]:
            assert "text" in b
            assert isinstance(b["text"], str)
            assert len(b["text"]) > 0

    def test_speaker_notes_contain_disclosure_refs(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        notes = slides[0]["speaker_notes"]
        assert "Disclosure" in notes

    def test_low_confidence_shown_in_notes(self):
        data = _make_full_output(low_confidence_flag=True, confidence="low")
        slides = render_to_slides(data)
        notes = slides[0]["speaker_notes"]
        assert "Low confidence" in notes

    def test_render_handles_empty_kpis(self):
        """Edge case: should still produce a slide even if output is minimal."""
        data = {
            "kpis": [],
            "overall_takeaways": ["Limited data available"],
            "confidence": "low",
            "low_confidence_flag": True,
            "notes": None,
        }
        slides = render_to_slides(data)
        assert len(slides) >= 1
        assert slides[0]["slide_id"] == "key_drivers_kpis_1"

    def test_bullets_max_4(self):
        data = _make_five_kpi_output()
        slides = render_to_slides(data)
        for slide in slides:
            assert len(slide["bullets"]) <= 4


# ═══════════════════════════════════════════════════════════════════════════════
# Postprocess tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostprocess:
    """Postprocess produces standard {section_id, slides[]} output."""

    def test_postprocess_returns_section_id(self):
        data = _make_full_output()
        result = _postprocess(data, {})
        assert result["section_id"] == "key_drivers_kpis"

    def test_postprocess_returns_slides(self):
        data = _make_full_output()
        result = _postprocess(data, {})
        assert "slides" in result
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1

    def test_postprocess_recomputes_low_confidence(self):
        """Postprocess should deterministically set low_confidence_flag."""
        data = _make_full_output()
        # All disclosures are 10-K, so confidence should be high
        data["low_confidence_flag"] = True  # LLM set it wrong
        result = _postprocess(data, {})
        # After recomputation, since all 3 KPIs have 10-K disclosure,
        # low_confidence_flag should be False
        # (confidence = high, no not_provided disclosures)
        assert result["needs_verification"] is False

    def test_postprocess_flags_missing_disclosure(self):
        """If any KPI has not_provided disclosure, flag should be True."""
        data = _make_full_output()
        data["kpis"][1]["disclosure"]["source_type"] = "not_provided"
        result = _postprocess(data, {})
        assert "Low confidence" in " ".join(result.get("verification_notes", []))

    def test_postprocess_handles_invalid_content(self):
        """Should not crash on invalid content."""
        result = _postprocess({"invalid": "data"}, {})
        assert result["section_id"] == "key_drivers_kpis"
        assert "slides" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Prompt / Module tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPrompt:
    """Prompt builder produces reasonable output."""

    def test_build_prompt_contains_schema(self):
        inputs = {
            "company_name": "TestCo",
            "ticker": "TST",
            "sector": "Technology",
        }
        prompt = _build_prompt(inputs)
        assert "OUTPUT JSON SCHEMA" in prompt
        assert "kpi_selection" in prompt.lower()
        assert "kpi_definitions" in prompt.lower()
        assert "disclosure_locations" in prompt.lower()

    def test_build_prompt_includes_hard_rules(self):
        inputs = {"company_name": "TestCo", "ticker": "TST", "sector": "Tech"}
        prompt = _build_prompt(inputs)
        assert "NEVER fabricate" in prompt
        assert "not_provided" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# Registry integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryIntegration:
    """Ensure section is registered correctly."""

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "key_drivers_kpis"

    def test_section_spec_has_build_prompt(self):
        assert callable(SECTION_SPEC.build_prompt)

    def test_section_spec_has_postprocess(self):
        assert callable(SECTION_SPEC.postprocess)

    def test_section_spec_has_schema(self):
        assert isinstance(SECTION_SPEC.schema, dict)

    def test_section_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_section_in_all_sections(self):
        from app.deck.services.sections import ALL_SECTIONS
        assert "key_drivers_kpis" in ALL_SECTIONS

    def test_get_section_returns_spec(self):
        from app.deck.services.sections import get_section
        spec = get_section("key_drivers_kpis")
        assert spec.id == "key_drivers_kpis"


# ═══════════════════════════════════════════════════════════════════════════════
# JSON Schema
# ═══════════════════════════════════════════════════════════════════════════════


class TestJsonSchema:
    """JSON schema for LLM output."""

    def test_schema_is_dict(self):
        schema = get_key_drivers_kpis_json_schema()
        assert isinstance(schema, dict)

    def test_schema_has_kpis_property(self):
        schema = get_key_drivers_kpis_json_schema()
        assert "kpis" in schema.get("properties", {}) or "kpis" in str(schema)
