"""
Tests for the Sector Invariants deck section.

Covers: schema validation, deterministic gating, fallbacks, rendering,
spec behaviour, and registry integration.
"""

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.sector_invariants.schemas import (
    KPIItem,
    ModuleOut,
    SectorInvariantsOutput,
    get_sector_invariants_json_schema,
    get_sector_invariants_json_schema_str,
)
from app.deck.services.sections.sector_invariants.gating import (
    classify_sector,
    module_is_supported,
    module_has_minimum_data,
    choose_included_modules,
)
from app.deck.services.sections.sector_invariants.fallbacks import (
    any_module_low_confidence,
    clamp_bullets,
)
from app.deck.services.sections.sector_invariants.render import render_to_slides
from app.deck.services.sections.sector_invariants.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# =============================================================================
# Fixtures
# =============================================================================

def _tech_company():
    return {"sector": "Technology", "industry": "Software—Application", "subindustry": "SaaS"}


def _non_tech_company():
    return {"sector": "Industrials", "industry": "Aerospace & Defense"}


def _full_tech_inputs():
    """Inputs with data for all three modules."""
    return {
        "company": _tech_company(),
        "company_name": "Acme Corp",
        "ticker": "ACME",
        "revenue_quality": {
            "recurring_pct": 85,
            "arr": "$1.2B",
            "nrr": "115%",
            "churn": "5%",
            "rpo": "$800M",
        },
        "gtm": {
            "customer_segments": ["Enterprise", "Mid-market"],
            "acv": "$120K",
            "cac_payback": "18 months",
            "magic_number": 0.8,
        },
        "platform_deps": {
            "cloud_provider_concentration": "AWS ~70%",
            "top_partners": ["AWS", "Salesforce"],
            "key_integrations": ["Slack", "JIRA"],
        },
        "security": {
            "soc2_iso": "SOC 2 Type II, ISO 27001",
            "uptime_sla": "99.95%",
            "breach_history": "None disclosed",
        },
    }


def _minimal_revenue_inputs():
    """Inputs with only revenue data (2 groups)."""
    return {
        "company": _tech_company(),
        "company_name": "MinCo",
        "ticker": "MIN",
        "revenue_quality": {
            "arr": "$500M",
            "nrr": "110%",
        },
        "gtm": {},
        "platform_deps": {},
        "security": {},
    }


def _no_data_inputs():
    """Tech company but no module data."""
    return {
        "company": _tech_company(),
        "company_name": "EmptyCo",
        "ticker": "EMP",
        "revenue_quality": {},
        "gtm": {},
        "platform_deps": {},
        "security": {},
    }


def _valid_module_out(mod_id="revenue_quality_gtm", confidence="high"):
    return {
        "id": mod_id,
        "title": "Test Module",
        "bullets": ["Bullet one.", "Bullet two."],
        "kpis": [{"label": "ARR", "value": "$1.2B", "as_of": "FY2025", "source_note": None}],
        "failure_modes": ["Churn acceleration"],
        "confidence": confidence,
        "notes": None,
    }


def _valid_output(included=None, modules=None, sector="tech_software"):
    if included is None:
        included = ["revenue_quality_gtm"]
    if modules is None:
        modules = [_valid_module_out("revenue_quality_gtm")]
    return {
        "sector_class": sector,
        "included_modules": included,
        "modules": modules,
        "low_confidence_flag": False,
        "notes": None,
    }


# =============================================================================
# Schema Validation
# =============================================================================

class TestSchemaValidation:
    """Pydantic model validation tests."""

    def test_valid_single_module(self):
        data = _valid_output()
        out = SectorInvariantsOutput.model_validate(data)
        assert out.sector_class == "tech_software"
        assert len(out.modules) == 1
        assert out.modules[0].id == "revenue_quality_gtm"

    def test_valid_two_modules(self):
        data = _valid_output(
            included=["revenue_quality_gtm", "platform_dependencies_risk"],
            modules=[
                _valid_module_out("revenue_quality_gtm"),
                _valid_module_out("platform_dependencies_risk"),
            ],
        )
        out = SectorInvariantsOutput.model_validate(data)
        assert len(out.modules) == 2

    def test_empty_modules_allowed(self):
        data = _valid_output(included=[], modules=[])
        out = SectorInvariantsOutput.model_validate(data)
        assert len(out.modules) == 0
        assert len(out.included_modules) == 0

    def test_module_count_mismatch_raises(self):
        data = _valid_output(
            included=["revenue_quality_gtm", "platform_dependencies_risk"],
            modules=[_valid_module_out("revenue_quality_gtm")],
        )
        with pytest.raises(ValidationError, match="must match"):
            SectorInvariantsOutput.model_validate(data)

    def test_duplicate_module_ids_raises(self):
        data = _valid_output(
            included=["revenue_quality_gtm", "revenue_quality_gtm"],
            modules=[
                _valid_module_out("revenue_quality_gtm"),
                _valid_module_out("revenue_quality_gtm"),
            ],
        )
        with pytest.raises(ValidationError, match="Duplicate"):
            SectorInvariantsOutput.model_validate(data)

    def test_module_not_in_included_raises(self):
        data = _valid_output(
            included=["revenue_quality_gtm"],
            modules=[_valid_module_out("platform_dependencies_risk")],
        )
        with pytest.raises(ValidationError, match="not in included_modules"):
            SectorInvariantsOutput.model_validate(data)

    def test_bullets_too_few_raises(self):
        mod = _valid_module_out()
        mod["bullets"] = ["Only one"]
        data = _valid_output(modules=[mod])
        with pytest.raises(ValidationError):
            SectorInvariantsOutput.model_validate(data)

    def test_bullets_too_many_raises(self):
        mod = _valid_module_out()
        mod["bullets"] = [f"Bullet {i}" for i in range(7)]
        data = _valid_output(modules=[mod])
        with pytest.raises(ValidationError):
            SectorInvariantsOutput.model_validate(data)

    def test_kpi_item_null_value(self):
        kpi = KPIItem(label="NRR", value=None, as_of=None, source_note=None)
        assert kpi.value is None

    def test_json_schema_generation(self):
        schema = get_sector_invariants_json_schema()
        assert "properties" in schema
        assert "sector_class" in schema["properties"]

    def test_json_schema_str(self):
        s = get_sector_invariants_json_schema_str()
        assert "sector_class" in s
        assert "included_modules" in s


# =============================================================================
# Gating
# =============================================================================

class TestSectorClassification:
    """Tests for classify_sector."""

    def test_tech_software_from_sector(self):
        assert classify_sector({"sector": "Technology"}) == "tech_software"

    def test_tech_software_from_industry(self):
        assert classify_sector({"industry": "Software—Application"}) == "tech_software"

    def test_tech_software_from_subindustry(self):
        assert classify_sector({"subindustry": "Cloud Infrastructure"}) == "tech_software"

    def test_saas_keyword(self):
        assert classify_sector({"sector": "SaaS Platforms"}) == "tech_software"

    def test_internet_keyword(self):
        assert classify_sector({"sector": "Internet"}) == "tech_software"

    def test_cybersecurity_keyword(self):
        assert classify_sector({"industry": "Cybersecurity"}) == "tech_software"

    def test_fintech_keyword(self):
        assert classify_sector({"industry": "Fintech"}) == "tech_software"

    def test_ai_keyword(self):
        assert classify_sector({"industry": "AI"}) == "tech_software"

    def test_industrials_is_other(self):
        assert classify_sector({"sector": "Industrials"}) == "other"

    def test_healthcare_is_other(self):
        assert classify_sector({"sector": "Healthcare"}) == "other"

    def test_none_company(self):
        assert classify_sector(None) == "other"

    def test_empty_company(self):
        assert classify_sector({}) == "other"


class TestModuleSupport:
    """Tests for module_is_supported."""

    def test_all_tech_modules_supported(self):
        for mid in ("revenue_quality_gtm", "platform_dependencies_risk", "security_reliability"):
            assert module_is_supported(mid, "tech_software") is True

    def test_tech_modules_not_supported_for_other(self):
        for mid in ("revenue_quality_gtm", "platform_dependencies_risk", "security_reliability"):
            assert module_is_supported(mid, "other") is False


class TestModuleMinimumData:
    """Tests for module_has_minimum_data."""

    def test_revenue_quality_gtm_needs_2_groups(self):
        # Only 1 group → not enough
        inputs = {"revenue_quality": {"arr": "$1B"}, "gtm": {}}
        assert module_has_minimum_data("revenue_quality_gtm", inputs) is False

        # 2 groups → enough
        inputs2 = {"revenue_quality": {"arr": "$1B", "nrr": "112%"}, "gtm": {}}
        assert module_has_minimum_data("revenue_quality_gtm", inputs2) is True

    def test_revenue_quality_gtm_gtm_fields_count(self):
        inputs = {
            "revenue_quality": {},
            "gtm": {"cac_payback": "18mo", "customer_segments": ["Enterprise"]},
        }
        assert module_has_minimum_data("revenue_quality_gtm", inputs) is True

    def test_platform_deps_needs_1(self):
        assert module_has_minimum_data("platform_dependencies_risk", {}) is False
        assert module_has_minimum_data(
            "platform_dependencies_risk",
            {"platform_deps": {"top_partners": ["AWS"]}},
        ) is True

    def test_platform_deps_empty_list_not_counted(self):
        assert module_has_minimum_data(
            "platform_dependencies_risk",
            {"platform_deps": {"top_partners": []}},
        ) is False

    def test_security_needs_1(self):
        assert module_has_minimum_data("security_reliability", {}) is False
        assert module_has_minimum_data(
            "security_reliability",
            {"security": {"soc2_iso": "SOC 2 Type II"}},
        ) is True

    def test_security_empty_string_not_counted(self):
        assert module_has_minimum_data(
            "security_reliability",
            {"security": {"soc2_iso": ""}},
        ) is False


class TestChooseIncludedModules:
    """Tests for choose_included_modules (deterministic selection)."""

    def test_full_data_returns_max_2(self):
        included = choose_included_modules(_full_tech_inputs())
        assert len(included) <= 2

    def test_full_data_priority_order(self):
        included = choose_included_modules(_full_tech_inputs())
        # revenue_quality_gtm should be first (highest priority)
        assert included[0] == "revenue_quality_gtm"
        assert included[1] == "platform_dependencies_risk"

    def test_only_revenue_data(self):
        included = choose_included_modules(_minimal_revenue_inputs())
        assert included == ["revenue_quality_gtm"]

    def test_no_data_returns_empty(self):
        included = choose_included_modules(_no_data_inputs())
        assert included == []

    def test_non_tech_returns_empty(self):
        inputs = _full_tech_inputs()
        inputs["company"] = _non_tech_company()
        included = choose_included_modules(inputs)
        assert included == []

    def test_deterministic(self):
        """Same inputs always produce same result."""
        inputs = _full_tech_inputs()
        r1 = choose_included_modules(inputs)
        r2 = choose_included_modules(inputs)
        assert r1 == r2


# =============================================================================
# Fallbacks
# =============================================================================

class TestFallbacks:
    """Tests for fallback helpers."""

    def test_any_module_low_confidence_true(self):
        modules = [{"confidence": "high"}, {"confidence": "low"}]
        assert any_module_low_confidence(modules) is True

    def test_any_module_low_confidence_false(self):
        modules = [{"confidence": "high"}, {"confidence": "medium"}]
        assert any_module_low_confidence(modules) is False

    def test_any_module_low_confidence_empty(self):
        assert any_module_low_confidence([]) is False

    def test_clamp_bullets_pads(self):
        result = clamp_bullets(["one"])
        assert len(result) == 2
        assert "not disclosed" in result[1].lower()

    def test_clamp_bullets_trims(self):
        result = clamp_bullets([f"b{i}" for i in range(8)])
        assert len(result) == 6

    def test_clamp_bullets_in_range(self):
        original = ["a", "b", "c"]
        result = clamp_bullets(original)
        assert result == ["a", "b", "c"]


# =============================================================================
# Rendering
# =============================================================================

class TestRendering:
    """Tests for render_to_slides."""

    def test_empty_modules_returns_minimal_slide(self):
        out = _valid_output(included=[], modules=[])
        slides = render_to_slides(out)
        assert len(slides) == 1
        assert slides[0]["title"] == "Sector Invariants"
        assert slides[0]["bullets"][0]["text"].startswith("Insufficient")
        assert "Low confidence" in slides[0]["speaker_notes"]

    def test_single_module_returns_1_slide(self):
        out = _valid_output()
        slides = render_to_slides(out)
        assert len(slides) == 1
        slide = slides[0]
        assert slide["slide_id"] == "sector_invariants_1"
        assert len(slide["bullets"]) >= 1
        assert "ARR" in slide["speaker_notes"]

    def test_two_modules_returns_1_combined_slide(self):
        out = _valid_output(
            included=["revenue_quality_gtm", "platform_dependencies_risk"],
            modules=[
                _valid_module_out("revenue_quality_gtm"),
                _valid_module_out("platform_dependencies_risk"),
            ],
        )
        slides = render_to_slides(out)
        assert len(slides) == 1
        slide = slides[0]
        assert slide["title"] == "Sector Invariants"
        # Should have sub-section labels
        bullet_texts = [b["text"] for b in slide["bullets"]]
        assert any("Revenue Quality" in t for t in bullet_texts)

    def test_slide_count_max_2(self):
        """Even with 2 modules, we get at most 1 slide (combined)."""
        out = _valid_output(
            included=["revenue_quality_gtm", "platform_dependencies_risk"],
            modules=[
                _valid_module_out("revenue_quality_gtm"),
                _valid_module_out("platform_dependencies_risk"),
            ],
        )
        slides = render_to_slides(out)
        assert len(slides) <= 2

    def test_low_confidence_in_speaker_notes(self):
        out = _valid_output()
        out["low_confidence_flag"] = True
        slides = render_to_slides(out)
        assert "Low confidence" in slides[0]["speaker_notes"]

    def test_failure_modes_in_speaker_notes(self):
        out = _valid_output()
        slides = render_to_slides(out)
        assert "Churn acceleration" in slides[0]["speaker_notes"]

    def test_slide_structure_conforms(self):
        """All slides have required keys."""
        out = _valid_output()
        slides = render_to_slides(out)
        for slide in slides:
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert "speaker_notes" in slide
            assert "layout_hints" in slide
            assert "flags" in slide

    def test_max_bullets_per_slide(self):
        mod = _valid_module_out()
        mod["bullets"] = ["B1", "B2", "B3", "B4", "B5", "B6"]
        out = _valid_output(modules=[mod])
        slides = render_to_slides(out)
        assert len(slides[0]["bullets"]) <= 4


# =============================================================================
# No Placeholders
# =============================================================================

class TestNoPlaceholders:
    """Ensure no $X, X%, TBD placeholders leak into output."""

    _PLACEHOLDER_RE = re.compile(r"\$X|X%|TBD|\[TBD\]|\[TODO\]")

    def _check_slides(self, slides):
        for slide in slides:
            for bullet in slide.get("bullets", []):
                assert not self._PLACEHOLDER_RE.search(bullet["text"]), (
                    f"Placeholder found in bullet: {bullet['text']}"
                )
            assert not self._PLACEHOLDER_RE.search(slide.get("speaker_notes", ""))

    def test_single_module_no_placeholders(self):
        out = _valid_output()
        slides = render_to_slides(out)
        self._check_slides(slides)

    def test_empty_no_placeholders(self):
        out = _valid_output(included=[], modules=[])
        slides = render_to_slides(out)
        self._check_slides(slides)


# =============================================================================
# Spec
# =============================================================================

class TestSpec:
    """Tests for the SectionSpec definition and its callbacks."""

    def test_spec_id(self):
        assert SECTION_SPEC.id == "sector_invariants"

    def test_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_build_prompt_with_data(self):
        prompt = _build_prompt(_full_tech_inputs())
        assert "revenue_quality_gtm" in prompt
        assert "JSON" in prompt

    def test_build_prompt_no_data(self):
        prompt = _build_prompt(_no_data_inputs())
        assert "included_modules" in prompt
        assert "[]" in prompt

    def test_build_prompt_non_tech(self):
        inputs = _full_tech_inputs()
        inputs["company"] = _non_tech_company()
        prompt = _build_prompt(inputs)
        assert "[]" in prompt

    def test_postprocess_valid(self):
        content = _valid_output(
            included=["revenue_quality_gtm"],
            modules=[_valid_module_out("revenue_quality_gtm")],
        )
        inputs = _full_tech_inputs()
        result = _postprocess(content, inputs)
        assert result["section_id"] == "sector_invariants"
        assert "slides" in result
        assert isinstance(result["slides"], list)

    def test_postprocess_overrides_model_modules(self):
        """Gating result takes precedence over what the model returns."""
        content = _valid_output(
            included=["revenue_quality_gtm", "security_reliability"],
            modules=[
                _valid_module_out("revenue_quality_gtm"),
                _valid_module_out("security_reliability"),
            ],
        )
        # Inputs that only support revenue_quality_gtm + platform_deps
        inputs = _full_tech_inputs()
        result = _postprocess(content, inputs)
        assert result["section_id"] == "sector_invariants"

    def test_postprocess_empty_modules(self):
        content = _valid_output(included=[], modules=[])
        inputs = _no_data_inputs()
        result = _postprocess(content, inputs)
        assert result["section_id"] == "sector_invariants"
        assert len(result["slides"]) >= 1
        assert any("Low confidence" in n for n in result["verification_notes"])

    def test_postprocess_low_confidence_propagated(self):
        content = _valid_output(
            included=["revenue_quality_gtm"],
            modules=[_valid_module_out("revenue_quality_gtm", confidence="low")],
        )
        inputs = _full_tech_inputs()
        result = _postprocess(content, inputs)
        assert any("Low confidence" in n for n in result["verification_notes"])

    def test_postprocess_handles_invalid_content(self):
        """Gracefully handles non-dict content."""
        result = _postprocess("bad content", _full_tech_inputs())
        assert result["section_id"] == "sector_invariants"
        assert isinstance(result["slides"], list)


# =============================================================================
# Registry Integration
# =============================================================================

class TestRegistryIntegration:
    """Ensure the section is properly registered."""

    def test_in_all_sections(self):
        from app.deck.services.sections import ALL_SECTIONS
        assert "sector_invariants" in ALL_SECTIONS

    def test_get_section(self):
        from app.deck.services.sections import get_section
        spec = get_section("sector_invariants")
        assert spec.id == "sector_invariants"
