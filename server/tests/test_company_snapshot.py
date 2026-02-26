"""
Tests for the Company Snapshot section.

Covers:
  - Pydantic schema validation (valid, partial, constraint violations)
  - Module boundary enforcement
  - Deterministic fallback tiers and confidence
  - Low-confidence footnote logic
  - Rendering to standard slide format
  - Registry integration
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.company_snapshot.schemas import (
    CompanySnapshotOutput,
    CustomersModule,
    FootprintModule,
    KpiItem,
    ModulesOutput,
    MoneyModelModule,
    PositioningModule,
    ProofPointsModule,
    QuickStat,
    SegmentItem,
    SegmentsModule,
    SnapshotHeader,
)
from app.deck.services.sections.company_snapshot.fallbacks import (
    any_module_low_confidence,
    fmt_currency,
    resolve_customer_concentration,
    resolve_money_model,
    resolve_proof_points_confidence,
    resolve_quick_stats,
    resolve_segments_tier,
)
from app.deck.services.sections.company_snapshot.render import render_to_slides
from app.deck.services.sections.company_snapshot.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_header(**overrides) -> dict:
    base = {
        "company_name": "Acme Corp",
        "ticker": "ACME",
        "sector": "Industrials",
        "industry": "Specialty Chemicals",
        "positioning_sentence": "Leading specialty chemicals manufacturer serving global industrial markets.",
        "quick_stats": [
            {"label": "Market Cap", "value": "$5.2B", "as_of": "2025-12"},
            {"label": "Revenue", "value": "$3.1B", "as_of": "2025-12"},
            {"label": "EBITDA", "value": "$620M", "as_of": "2025-12"},
        ],
        "low_confidence_flag": False,
    }
    base.update(overrides)
    return base


def _make_positioning(**overrides) -> dict:
    base = {
        "bullets": [
            "Global leader in specialty chemical additives",
            "Diversified end-market exposure across automotive, construction, and electronics",
            "Strong barriers to entry via proprietary formulations and long customer qualification cycles",
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_segments(**overrides) -> dict:
    base = {
        "mode": "tier_a",
        "mix_basis": "revenue",
        "items": [
            {"name": "Performance Additives", "mix_pct": 45.0, "one_liner": "Specialty additives for auto and industrial"},
            {"name": "Coatings", "mix_pct": 35.0, "one_liner": "Protective coatings for infrastructure"},
            {"name": "Catalysts", "mix_pct": 20.0, "one_liner": "Refinery catalysts and environmental solutions"},
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_money_model(**overrides) -> dict:
    base = {
        "pricing_unit": "per kg with cost pass-through",
        "contract_structure": "annual contracts with quarterly pricing adjustments",
        "recurrence": "mostly recurring",
        "cost_drivers": ["raw material feedstock", "energy costs", "logistics"],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_customers(**overrides) -> dict:
    base = {
        "types": ["industrial OEMs", "construction firms", "auto manufacturers"],
        "concentration": "top 10 customers ~30% of revenue",
        "credit_quality": "investment-grade counterparties",
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_footprint(**overrides) -> dict:
    base = {
        "regions": ["North America", "Europe", "Asia-Pacific"],
        "why_it_matters": "Geographic diversification reduces single-market risk",
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_proof_points(**overrides) -> dict:
    base = {
        "kpis": [
            {"label": "Production capacity", "value": "500K tonnes/year", "as_of": "2025"},
            {"label": "Manufacturing sites", "value": "18 globally", "as_of": None},
            {"label": "Customer retention", "value": "95%+", "as_of": "2024"},
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_full_snapshot(**overrides) -> dict:
    base = {
        "header": _make_header(),
        "modules": {
            "positioning": _make_positioning(),
            "segments": _make_segments(),
            "money_model": _make_money_model(),
            "customers": _make_customers(),
            "footprint": _make_footprint(),
            "proof_points": _make_proof_points(),
        },
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Pydantic model validation tests."""

    def test_valid_full_output_passes(self):
        data = _make_full_snapshot()
        parsed = CompanySnapshotOutput.model_validate(data)
        assert parsed.header.company_name == "Acme Corp"
        assert parsed.header.ticker == "ACME"
        assert len(parsed.modules.positioning.bullets) == 3
        assert parsed.modules.segments.mode == "tier_a"
        assert len(parsed.modules.money_model.cost_drivers) == 3

    def test_minimal_output_with_defaults(self):
        """Null/optional fields should still validate."""
        data = _make_full_snapshot()
        data["header"]["sector"] = None
        data["header"]["industry"] = None
        data["header"]["quick_stats"] = []
        data["modules"]["customers"]["credit_quality"] = None
        data["modules"]["footprint"]["why_it_matters"] = None
        data["modules"]["positioning"]["notes"] = None
        parsed = CompanySnapshotOutput.model_validate(data)
        assert parsed.header.sector is None
        assert parsed.header.quick_stats == []

    def test_bullet_count_too_few(self):
        data = _make_full_snapshot()
        data["modules"]["positioning"]["bullets"] = ["only one", "just two"]
        with pytest.raises(ValidationError, match="too_short"):
            CompanySnapshotOutput.model_validate(data)

    def test_bullet_count_too_many(self):
        data = _make_full_snapshot()
        data["modules"]["positioning"]["bullets"] = [f"bullet {i}" for i in range(7)]
        with pytest.raises(ValidationError, match="too_long"):
            CompanySnapshotOutput.model_validate(data)

    def test_bullet_count_valid_boundary(self):
        """3 and 6 bullets should pass."""
        for n in (3, 6):
            data = _make_full_snapshot()
            data["modules"]["positioning"]["bullets"] = [f"bullet {i}" for i in range(n)]
            parsed = CompanySnapshotOutput.model_validate(data)
            assert len(parsed.modules.positioning.bullets) == n

    def test_cost_drivers_too_few(self):
        data = _make_full_snapshot()
        data["modules"]["money_model"]["cost_drivers"] = ["only one"]
        with pytest.raises(ValidationError, match="too_short"):
            CompanySnapshotOutput.model_validate(data)

    def test_cost_drivers_too_many(self):
        data = _make_full_snapshot()
        data["modules"]["money_model"]["cost_drivers"] = [f"driver {i}" for i in range(5)]
        with pytest.raises(ValidationError, match="too_long"):
            CompanySnapshotOutput.model_validate(data)

    def test_customer_types_too_few(self):
        data = _make_full_snapshot()
        data["modules"]["customers"]["types"] = ["only one"]
        with pytest.raises(ValidationError, match="too_short"):
            CompanySnapshotOutput.model_validate(data)

    def test_customer_types_too_many(self):
        data = _make_full_snapshot()
        data["modules"]["customers"]["types"] = [f"type {i}" for i in range(6)]
        with pytest.raises(ValidationError, match="too_long"):
            CompanySnapshotOutput.model_validate(data)

    def test_regions_too_many(self):
        data = _make_full_snapshot()
        data["modules"]["footprint"]["regions"] = [f"region {i}" for i in range(6)]
        with pytest.raises(ValidationError, match="too_long"):
            CompanySnapshotOutput.model_validate(data)

    def test_kpis_too_few(self):
        data = _make_full_snapshot()
        data["modules"]["proof_points"]["kpis"] = [
            {"label": "KPI1", "value": "100", "as_of": None},
            {"label": "KPI2", "value": "200", "as_of": None},
        ]
        with pytest.raises(ValidationError, match="too_short"):
            CompanySnapshotOutput.model_validate(data)

    def test_kpis_too_many(self):
        data = _make_full_snapshot()
        data["modules"]["proof_points"]["kpis"] = [
            {"label": f"KPI{i}", "value": str(i * 100), "as_of": None}
            for i in range(7)
        ]
        with pytest.raises(ValidationError, match="too_long"):
            CompanySnapshotOutput.model_validate(data)


# ═══════════════════════════════════════════════════════════════════════════════
# Module Boundary Enforcement
# ═══════════════════════════════════════════════════════════════════════════════

# Patterns that should NOT appear in positioning bullets
_METRIC_PATTERNS = re.compile(r"\$[\d,.]+|\d+%|\d+\.\dx|EV/|P/E|EBITDA margin")

# Patterns that should NOT appear in proof_points KPI labels
_FINANCIAL_RATIO_PATTERNS = re.compile(
    r"margin|eps|earnings per share|growth rate|multiple|P/E|EV/EBITDA|price.to.earnings",
    re.IGNORECASE,
)


class TestModuleBoundaries:
    """Verify hard rules about content separation between modules."""

    def test_positioning_has_no_metrics(self):
        """Positioning bullets must not contain dollar values, percentages, or ratios."""
        data = _make_positioning()
        for bullet in data["bullets"]:
            assert not _METRIC_PATTERNS.search(bullet), (
                f"Positioning bullet contains metrics: {bullet}"
            )

    def test_proof_points_no_financial_ratios(self):
        """Proof point KPI labels must not be financial ratios."""
        data = _make_proof_points()
        for kpi in data["kpis"]:
            assert not _FINANCIAL_RATIO_PATTERNS.search(kpi["label"]), (
                f"Proof point KPI is a financial ratio: {kpi['label']}"
            )

    def test_positioning_bullets_boundary_enforcement(self):
        """Bullets with metrics should be detectable."""
        bad_bullets = [
            "Revenue grew $500M last year",
            "Market share increased 15%",
            "Trading at 12.5x EV/EBITDA",
        ]
        for bullet in bad_bullets:
            assert _METRIC_PATTERNS.search(bullet), (
                f"Expected metric pattern in: {bullet}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback Tier Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSegmentsFallback:

    def test_tier_a_with_mix(self):
        segments = [{"name": "Seg A", "mix_pct": 60}, {"name": "Seg B", "mix_pct": 40}]
        mode, confidence = resolve_segments_tier(segments, has_mix=True)
        assert mode == "tier_a"
        assert confidence == "high"

    def test_tier_b_no_mix(self):
        segments = [{"name": "Seg A"}, {"name": "Seg B"}]
        mode, confidence = resolve_segments_tier(segments, has_mix=False)
        assert mode == "tier_b"
        assert confidence == "medium"

    def test_tier_c_no_data(self):
        mode, confidence = resolve_segments_tier(None)
        assert mode == "tier_c"
        assert confidence == "low"

    def test_tier_c_empty_list(self):
        mode, confidence = resolve_segments_tier([])
        assert mode == "tier_c"
        assert confidence == "low"


class TestCustomersFallback:

    def test_disclosed_concentration(self):
        text, conf = resolve_customer_concentration("top 5 = 40% of revenue")
        assert text == "top 5 = 40% of revenue"
        assert conf == "high"

    def test_undisclosed_concentration(self):
        text, conf = resolve_customer_concentration(None)
        assert "not disclosed" in text
        assert conf == "medium"

    def test_blank_concentration(self):
        text, conf = resolve_customer_concentration("  ")
        assert "not disclosed" in text
        assert conf == "medium"


class TestMoneyModelFallback:

    def test_known_pricing_unit(self):
        unit, conf, notes = resolve_money_model("per seat per month")
        assert unit == "per seat per month"
        assert conf == "high"
        assert notes is None

    def test_inferred_from_saas_sector(self):
        unit, conf, notes = resolve_money_model(None, sector="SaaS", industry="Software")
        assert "subscription" in unit or "contracted" in unit
        assert conf == "low"
        assert notes is not None

    def test_inferred_from_commodity_sector(self):
        unit, conf, notes = resolve_money_model(None, sector="Commodity Trading")
        assert "volume" in unit
        assert conf == "low"
        assert notes is not None

    def test_no_clues(self):
        unit, conf, notes = resolve_money_model(None, sector="Unknown", industry="Unknown")
        assert conf == "low"
        assert notes is not None


class TestQuickStatsFallback:

    def test_sufficient_stats(self):
        financials = {
            "market_cap": 5_200_000_000,
            "ev": 6_100_000_000,
            "revenue_ttm_or_fy0": 3_100_000_000,
        }
        stats, low_flag = resolve_quick_stats(financials)
        assert len(stats) == 3
        assert low_flag is False
        assert stats[0]["label"] == "Market Cap"

    def test_missing_all_data(self):
        stats, low_flag = resolve_quick_stats(None)
        assert stats == []
        assert low_flag is True

    def test_single_stat(self):
        financials = {"market_cap": 1_000_000_000}
        stats, low_flag = resolve_quick_stats(financials)
        assert len(stats) == 1
        assert low_flag is True  # fewer than 2

    def test_two_stats_sufficient(self):
        financials = {"market_cap": 1_000_000_000, "ev": 1_500_000_000}
        stats, low_flag = resolve_quick_stats(financials)
        assert len(stats) == 2
        assert low_flag is False

    def test_max_six_stats(self):
        financials = {
            "market_cap": 5e9,
            "ev": 6e9,
            "revenue_ttm_or_fy0": 3e9,
            "ebitda_ttm_or_fy0": 600e6,
            "fcf_ttm": 400e6,
            "net_debt": 900e6,
            "leverage": 1.5,
        }
        stats, low_flag = resolve_quick_stats(financials)
        assert len(stats) == 6  # capped at 6
        assert low_flag is False

    def test_leverage_formatted_as_ratio(self):
        financials = {"market_cap": 1e9, "leverage": 2.3}
        stats, _ = resolve_quick_stats(financials)
        leverage_stat = next(s for s in stats if s["label"] == "Leverage")
        assert leverage_stat["value"] == "2.3x"


class TestProofPointsFallback:

    def test_sufficient_kpis(self):
        kpis = [
            {"label": "A", "value": "1"},
            {"label": "B", "value": "2"},
            {"label": "C", "value": "3"},
        ]
        conf, notes = resolve_proof_points_confidence(kpis)
        assert conf == "high"
        assert notes is None

    def test_few_kpis(self):
        kpis = [{"label": "A", "value": "1"}, {"label": "B", "value": "2"}]
        conf, notes = resolve_proof_points_confidence(kpis)
        assert conf == "low"
        assert "limited disclosure" in notes

    def test_no_kpis(self):
        conf, notes = resolve_proof_points_confidence(None)
        assert conf == "low"
        assert "limited disclosure" in notes


# ═══════════════════════════════════════════════════════════════════════════════
# Low Confidence Footnote
# ═══════════════════════════════════════════════════════════════════════════════


class TestLowConfidenceFlag:

    def test_all_high_confidence(self):
        modules = {
            "positioning": {"confidence": "high"},
            "segments": {"confidence": "high"},
            "money_model": {"confidence": "high"},
            "customers": {"confidence": "high"},
            "footprint": {"confidence": "high"},
            "proof_points": {"confidence": "high"},
        }
        assert any_module_low_confidence(modules) is False

    def test_one_low_triggers_flag(self):
        modules = {
            "positioning": {"confidence": "high"},
            "segments": {"confidence": "low"},
            "money_model": {"confidence": "high"},
            "customers": {"confidence": "medium"},
            "footprint": {"confidence": "high"},
            "proof_points": {"confidence": "high"},
        }
        assert any_module_low_confidence(modules) is True

    def test_medium_does_not_trigger(self):
        modules = {
            "positioning": {"confidence": "medium"},
            "segments": {"confidence": "medium"},
            "money_model": {"confidence": "medium"},
            "customers": {"confidence": "medium"},
            "footprint": {"confidence": "medium"},
            "proof_points": {"confidence": "medium"},
        }
        assert any_module_low_confidence(modules) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════════


class TestRendering:

    def test_render_produces_valid_slides(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert isinstance(slides, list)
        assert 1 <= len(slides) <= 2

        for slide in slides:
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert isinstance(slide["bullets"], list)
            assert len(slide["bullets"]) <= 4
            assert "speaker_notes" in slide
            assert "layout_hints" in slide
            assert "flags" in slide

    def test_slide_1_has_snapshot_header_style(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert slides[0]["layout_hints"]["style"] == "snapshot_header"

    def test_slide_2_has_snapshot_detail_style(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert len(slides) == 2
        assert slides[1]["layout_hints"]["style"] == "snapshot_detail"

    def test_slide_1_title_contains_company_and_ticker(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert "Acme Corp" in slides[0]["title"]
        assert "ACME" in slides[0]["title"]

    def test_positioning_sentence_in_slide_1_bullets(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("specialty chemicals" in t.lower() for t in bullet_texts)

    def test_money_model_in_slide_1_speaker_notes(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert "Money Model" in slides[0]["speaker_notes"]
        assert "per kg" in slides[0]["speaker_notes"]

    def test_segments_in_slide_2_bullets(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        bullet_texts = [b["text"] for b in slides[1]["bullets"]]
        assert any("Performance Additives" in t for t in bullet_texts)

    def test_proof_points_in_slide_2_speaker_notes(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        assert "Proof Points" in slides[1]["speaker_notes"]
        assert "Production capacity" in slides[1]["speaker_notes"]

    def test_low_confidence_footnote_in_slide_2(self):
        snapshot = _make_full_snapshot()
        snapshot["header"]["low_confidence_flag"] = True
        slides = render_to_slides(snapshot)
        assert "Low confidence" in slides[1]["speaker_notes"]

    def test_no_slide_2_if_no_module_data(self):
        snapshot = _make_full_snapshot()
        snapshot["modules"]["segments"]["items"] = []
        snapshot["modules"]["customers"]["types"] = []
        snapshot["modules"]["footprint"]["regions"] = []
        # Re-validate and render
        slides = render_to_slides(snapshot)
        # Should still produce slide 1 at minimum
        assert len(slides) >= 1

    def test_raw_snapshot_attached(self):
        snapshot = _make_full_snapshot()
        slides = render_to_slides(snapshot)
        raw = slides[0]["layout_hints"].get("_raw_snapshot")
        assert raw is not None
        import json
        parsed = json.loads(raw)
        assert parsed["header"]["ticker"] == "ACME"


# ═══════════════════════════════════════════════════════════════════════════════
# Spec / build_prompt / postprocess
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpec:

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "company_snapshot"

    def test_section_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_build_prompt_returns_string(self):
        inputs = {
            "ticker": "ACME",
            "company_name": "Acme Corp",
            "sector": "Industrials",
            "company": {"name": "Acme Corp", "ticker": "ACME", "sector": "Industrials"},
            "financials": {"market_cap": 5e9, "revenue_ttm_or_fy0": 3e9},
        }
        prompt = _build_prompt(inputs)
        assert isinstance(prompt, str)
        assert "company_snapshot" in prompt.lower() or "HEADER" in prompt
        assert "positioning" in prompt.lower()
        assert "segments" in prompt.lower()

    def test_build_prompt_includes_schema(self):
        inputs = {
            "ticker": "TEST",
            "company_name": "Test Co",
            "company": {"name": "Test Co", "ticker": "TEST"},
        }
        prompt = _build_prompt(inputs)
        assert "CompanySnapshotOutput" in prompt or "header" in prompt.lower()

    def test_postprocess_produces_valid_section_output(self):
        content = _make_full_snapshot()
        inputs = {"ticker": "ACME", "company_name": "Acme Corp"}
        result = _postprocess(content, inputs)
        assert result["section_id"] == "company_snapshot"
        assert "slides" in result
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1
        assert result["needs_verification"] is False

    def test_postprocess_sets_verification_notes_on_low_confidence(self):
        content = _make_full_snapshot()
        content["modules"]["segments"]["confidence"] = "low"
        inputs = {"ticker": "ACME", "company_name": "Acme Corp"}
        result = _postprocess(content, inputs)
        assert len(result["verification_notes"]) > 0
        assert "Low confidence" in result["verification_notes"][0]

    def test_postprocess_no_verification_notes_when_high_confidence(self):
        content = _make_full_snapshot()
        inputs = {"ticker": "ACME", "company_name": "Acme Corp"}
        result = _postprocess(content, inputs)
        assert result["verification_notes"] == []

    def test_postprocess_handles_invalid_content_gracefully(self):
        """If Pydantic validation fails, should still produce slides."""
        content = {"header": {"company_name": "X", "ticker": "X", "positioning_sentence": "test"}, "modules": {}}
        inputs = {"ticker": "X", "company_name": "X"}
        result = _postprocess(content, inputs)
        assert result["section_id"] == "company_snapshot"
        assert "slides" in result


# ═══════════════════════════════════════════════════════════════════════════════
# Currency formatting helper
# ═══════════════════════════════════════════════════════════════════════════════


class TestFmtCurrency:

    def test_billions(self):
        assert fmt_currency(5_200_000_000) == "$5.2B"

    def test_millions(self):
        assert fmt_currency(620_000_000) == "$620.0M"

    def test_trillions(self):
        assert fmt_currency(1_500_000_000_000) == "$1.5T"

    def test_thousands(self):
        assert fmt_currency(45_000) == "$45.0K"

    def test_small(self):
        assert fmt_currency(999) == "$999"

    def test_negative(self):
        assert fmt_currency(-2_000_000_000) == "-$2.0B"

    def test_none(self):
        assert fmt_currency(None) is None


# ═══════════════════════════════════════════════════════════════════════════════
# Registry integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryIntegration:

    def test_company_snapshot_in_registry(self):
        from app.deck.services.sections import ALL_SECTIONS
        assert "company_snapshot" in ALL_SECTIONS

    def test_get_section_returns_spec(self):
        from app.deck.services.sections import get_section
        spec = get_section("company_snapshot")
        assert spec.id == "company_snapshot"
        assert spec.postprocess is not None
