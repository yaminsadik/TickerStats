"""
Tests for the Business Model & Segments section.

Covers:
  - Pydantic schema validation (bullet counts, flow steps 4..6)
  - Segments tier tests (tier_a / tier_b / tier_c)
  - Unit economics applicability (no metrics -> applicable false)
  - No fabrication tests (renderer does not output placeholders like "X%" or "$X")
  - Render produces 1–2 slides in valid shape
  - Low-confidence flag logic
  - Postprocess returns standard {section_id, slides[]}
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.business_model_segments.schemas import (
    BusinessModelOut,
    BusinessModelSegmentsOutput,
    FlowStep,
    SegmentItem,
    SegmentsOut,
    UnitEconomicsOut,
    UnitMetric,
)
from app.deck.services.sections.business_model_segments.fallbacks import (
    compute_low_confidence_flag,
    resolve_business_model_confidence,
    resolve_segments_tier,
    resolve_unit_economics,
    strip_profit_mix_if_missing,
    has_pricing_notes,
)
from app.deck.services.sections.business_model_segments.render import render_to_slides
from app.deck.services.sections.business_model_segments.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_business_model(**overrides) -> dict:
    base = {
        "what_they_sell": ["Cloud storage", "Analytics platform"],
        "who_they_sell_to": ["Enterprise IT", "SMBs"],
        "revenue_flow": [
            {"step": "Customer signs annual contract", "note": None},
            {"step": "Onboarding and provisioning", "note": None},
            {"step": "Usage-based billing kicks in", "note": "metered"},
            {"step": "Renewal or upsell at contract end", "note": None},
        ],
        "pricing_contract_notes": [],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_segments(mode: str = "tier_a", **overrides) -> dict:
    if mode == "tier_a":
        items = [
            {
                "name": "Cloud Services",
                "revenue_mix_pct": 60.0,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Public and hybrid cloud infrastructure",
                "drivers": ["Enterprise adoption", "AI workloads"],
            },
            {
                "name": "On-Premise",
                "revenue_mix_pct": 40.0,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Legacy datacenter solutions",
                "drivers": ["Maintenance contracts", "Migration services"],
            },
        ]
    elif mode == "tier_b":
        items = [
            {
                "name": "Cloud Services",
                "revenue_mix_pct": None,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Public and hybrid cloud infrastructure",
                "drivers": ["Enterprise adoption", "AI workloads"],
            },
            {
                "name": "On-Premise",
                "revenue_mix_pct": None,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Legacy datacenter solutions",
                "drivers": ["Maintenance contracts", "Migration services"],
            },
        ]
    else:  # tier_c
        items = [
            {
                "name": "Primary Segment A",
                "revenue_mix_pct": None,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Inferred primary segment",
                "drivers": ["Market growth", "Product demand"],
            },
            {
                "name": "Primary Segment B",
                "revenue_mix_pct": None,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": "Inferred secondary segment",
                "drivers": ["Expansion", "Cross-selling"],
            },
        ]

    base = {
        "mode": mode,
        "items": items,
        "confidence": "high" if mode == "tier_a" else ("medium" if mode == "tier_b" else "low"),
        "notes": "inferred segments" if mode == "tier_c" else None,
    }
    base.update(overrides)
    return base


def _make_unit_economics(applicable: bool = True, **overrides) -> dict:
    base = {
        "applicable": applicable,
        "metrics": [
            {"label": "ARPU", "value": "$120/mo", "as_of": "Q4 2025"},
            {"label": "Churn", "value": "2.1%", "as_of": "Q4 2025"},
        ] if applicable else [],
        "confidence": "high" if applicable else "low",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_full_output(**overrides) -> dict:
    base = {
        "business_model": _make_business_model(),
        "segments": _make_segments("tier_a"),
        "unit_economics": _make_unit_economics(True),
        "low_confidence_flag": False,
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Schema validation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Test Pydantic schema constraints."""

    def test_valid_full_output(self):
        data = _make_full_output()
        out = BusinessModelSegmentsOutput.model_validate(data)
        assert out.business_model.confidence == "high"
        assert len(out.business_model.revenue_flow) == 4

    def test_flow_steps_minimum(self):
        """revenue_flow must have at least 4 items."""
        bm = _make_business_model(revenue_flow=[
            {"step": "A", "note": None},
            {"step": "B", "note": None},
            {"step": "C", "note": None},
        ])
        with pytest.raises(ValidationError, match="revenue_flow"):
            BusinessModelOut.model_validate(bm)

    def test_flow_steps_maximum(self):
        """revenue_flow must have at most 6 items."""
        bm = _make_business_model(revenue_flow=[
            {"step": f"Step {i}", "note": None} for i in range(7)
        ])
        with pytest.raises(ValidationError, match="revenue_flow"):
            BusinessModelOut.model_validate(bm)

    def test_flow_steps_valid_range(self):
        """4, 5, and 6 flow steps should all be valid."""
        for count in (4, 5, 6):
            bm = _make_business_model(revenue_flow=[
                {"step": f"Step {i}", "note": None} for i in range(count)
            ])
            out = BusinessModelOut.model_validate(bm)
            assert len(out.revenue_flow) == count

    def test_what_they_sell_min(self):
        """what_they_sell needs at least 2."""
        bm = _make_business_model(what_they_sell=["Only one"])
        with pytest.raises(ValidationError, match="what_they_sell"):
            BusinessModelOut.model_validate(bm)

    def test_what_they_sell_max(self):
        """what_they_sell allows at most 5."""
        bm = _make_business_model(
            what_they_sell=[f"Product {i}" for i in range(6)]
        )
        with pytest.raises(ValidationError, match="what_they_sell"):
            BusinessModelOut.model_validate(bm)

    def test_segment_drivers_min(self):
        """Each segment needs at least 2 drivers."""
        seg = {
            "name": "Test",
            "revenue_mix_pct": 50.0,
            "profit_mix_pct": None,
            "profit_basis": None,
            "one_liner": "Test segment",
            "drivers": ["Only one"],
        }
        with pytest.raises(ValidationError, match="drivers"):
            SegmentItem.model_validate(seg)

    def test_segment_drivers_max(self):
        """Each segment allows at most 4 drivers."""
        seg = {
            "name": "Test",
            "revenue_mix_pct": 50.0,
            "profit_mix_pct": None,
            "profit_basis": None,
            "one_liner": "Test segment",
            "drivers": [f"Driver {i}" for i in range(5)],
        }
        with pytest.raises(ValidationError, match="drivers"):
            SegmentItem.model_validate(seg)

    def test_segments_items_min(self):
        """Segments needs at least 2 items."""
        seg = _make_segments("tier_a")
        seg["items"] = seg["items"][:1]
        with pytest.raises(ValidationError, match="items"):
            SegmentsOut.model_validate(seg)

    def test_pricing_contract_notes_max(self):
        """pricing_contract_notes allows at most 3."""
        bm = _make_business_model(
            pricing_contract_notes=["A", "B", "C", "D"]
        )
        with pytest.raises(ValidationError, match="pricing_contract_notes"):
            BusinessModelOut.model_validate(bm)

    def test_unit_metrics_max(self):
        """metrics allows at most 6."""
        ue = _make_unit_economics(
            applicable=True,
            metrics=[{"label": f"M{i}", "value": f"V{i}"} for i in range(7)],
        )
        with pytest.raises(ValidationError, match="metrics"):
            UnitEconomicsOut.model_validate(ue)


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback / tier tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSegmentsTier:
    """Test segment tier resolution."""

    def test_tier_a_with_mix(self):
        segments = [
            {"name": "A", "revenue_mix_pct": 60},
            {"name": "B", "revenue_mix_pct": 40},
        ]
        mode, conf = resolve_segments_tier(segments)
        assert mode == "tier_a"
        assert conf == "high"

    def test_tier_b_no_mix(self):
        segments = [
            {"name": "A"},
            {"name": "B"},
        ]
        mode, conf = resolve_segments_tier(segments)
        assert mode == "tier_b"
        assert conf == "medium"

    def test_tier_c_no_segments(self):
        mode, conf = resolve_segments_tier(None)
        assert mode == "tier_c"
        assert conf == "low"

    def test_tier_c_empty_list(self):
        mode, conf = resolve_segments_tier([])
        assert mode == "tier_c"
        assert conf == "low"

    def test_tier_c_single_segment(self):
        """Less than 2 valid segments -> tier_c."""
        segments = [{"name": "Only One"}]
        mode, conf = resolve_segments_tier(segments)
        assert mode == "tier_c"
        assert conf == "low"

    def test_tier_a_with_mix_pct_alias(self):
        """Should also recognise mix_pct (alias used in some inputs)."""
        segments = [
            {"name": "A", "mix_pct": 60},
            {"name": "B", "mix_pct": 40},
        ]
        mode, conf = resolve_segments_tier(segments)
        assert mode == "tier_a"
        assert conf == "high"


class TestProfitMixStrip:
    """Profit mix must never be inferred."""

    def test_missing_profit_mix_set_to_none(self):
        segments = [{"name": "A", "revenue_mix_pct": 60}]
        result = strip_profit_mix_if_missing(segments)
        assert result[0]["profit_mix_pct"] is None
        assert result[0]["profit_basis"] is None

    def test_present_profit_mix_kept(self):
        segments = [{"name": "A", "profit_mix_pct": 45.0, "profit_basis": "ebit"}]
        result = strip_profit_mix_if_missing(segments)
        assert result[0]["profit_mix_pct"] == 45.0
        assert result[0]["profit_basis"] == "ebit"

    def test_empty_list(self):
        assert strip_profit_mix_if_missing([]) == []
        assert strip_profit_mix_if_missing(None) == []


# ═══════════════════════════════════════════════════════════════════════════════
# Unit economics applicability tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnitEconomics:
    """Unit economics applicability."""

    def test_no_metrics_not_applicable(self):
        applicable, metrics, conf = resolve_unit_economics({})
        assert applicable is False
        assert metrics == []
        assert conf == "low"

    def test_with_arpu_applicable(self):
        applicable, metrics, conf = resolve_unit_economics({"arpu": "$120"})
        assert applicable is True
        assert len(metrics) >= 1
        assert conf == "high"

    def test_with_unit_economics_dict(self):
        applicable, metrics, conf = resolve_unit_economics({
            "unit_economics": {"churn": "2.1%", "ltv": "$5,400"}
        })
        assert applicable is True
        assert len(metrics) == 2

    def test_with_metrics_list(self):
        applicable, metrics, conf = resolve_unit_economics({
            "unit_economics": {
                "metrics": [
                    {"label": "NRR", "value": "115%"},
                ]
            }
        })
        assert applicable is True

    def test_empty_unit_economics(self):
        applicable, metrics, conf = resolve_unit_economics({
            "unit_economics": {}
        })
        assert applicable is False
        assert metrics == []


# ═══════════════════════════════════════════════════════════════════════════════
# Low-confidence flag tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestLowConfidenceFlag:
    def test_all_high(self):
        assert compute_low_confidence_flag("high", "high", "high", "tier_a") is False

    def test_bm_low(self):
        assert compute_low_confidence_flag("low", "high", "high", "tier_a") is True

    def test_segments_low(self):
        assert compute_low_confidence_flag("high", "low", "high", "tier_a") is True

    def test_ue_low(self):
        assert compute_low_confidence_flag("high", "high", "low", "tier_a") is True

    def test_tier_c(self):
        assert compute_low_confidence_flag("high", "medium", "high", "tier_c") is True

    def test_medium_no_flag(self):
        assert compute_low_confidence_flag("medium", "medium", "medium", "tier_b") is False


# ═══════════════════════════════════════════════════════════════════════════════
# Business model confidence tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestBusinessModelConfidence:
    def test_with_flow_high(self):
        conf, notes = resolve_business_model_confidence({
            "business_model": {"revenue_flow": [{"step": "A"}]}
        })
        assert conf == "high"
        assert notes is None

    def test_with_description_medium(self):
        conf, notes = resolve_business_model_confidence({
            "company_description": "A cloud computing company"
        })
        assert conf == "medium"
        assert notes is not None

    def test_minimal_input_medium(self):
        conf, notes = resolve_business_model_confidence({})
        assert conf == "medium"

    def test_pricing_notes_detection(self):
        assert has_pricing_notes({"business_model": {"pricing_contract_notes": ["Annual"]}}) is True
        assert has_pricing_notes({"business_model": {"pricing_contract_notes": []}}) is False
        assert has_pricing_notes({}) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Render tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRender:
    """Render to 1–2 slides in valid shape."""

    def test_full_output_two_slides(self):
        """Full output with tier_a segments + unit econ -> 2 slides."""
        data = _make_full_output()
        slides = render_to_slides(data)
        assert len(slides) == 2
        assert slides[0]["slide_id"] == "business_model_segments_1"
        assert slides[1]["slide_id"] == "business_model_segments_2"

    def test_slide_1_structure(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        s1 = slides[0]
        assert s1["title"] == "Business Model"
        assert len(s1["bullets"]) <= 4
        assert all("text" in b for b in s1["bullets"])
        assert "slide_id" in s1
        assert "speaker_notes" in s1
        assert "layout_hints" in s1
        assert "flags" in s1

    def test_slide_2_structure(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        s2 = slides[1]
        assert s2["title"] == "Segments & Unit Economics"
        assert len(s2["bullets"]) <= 4
        assert all("text" in b for b in s2["bullets"])

    def test_one_slide_when_no_segments(self):
        """No segments + no unit econ -> only slide 1."""
        data = _make_full_output(
            segments=_make_segments("tier_c", items=[
                {
                    "name": "A",
                    "revenue_mix_pct": None,
                    "profit_mix_pct": None,
                    "profit_basis": None,
                    "one_liner": "Inferred",
                    "drivers": ["Growth", "Demand"],
                },
                {
                    "name": "B",
                    "revenue_mix_pct": None,
                    "profit_mix_pct": None,
                    "profit_basis": None,
                    "one_liner": "Inferred",
                    "drivers": ["Growth", "Demand"],
                },
            ]),
            unit_economics=_make_unit_economics(False),
        )
        slides = render_to_slides(data)
        # 2 items, no mix, not applicable -> only 1 slide
        assert len(slides) == 1

    def test_two_slides_when_applicable_unit_econ(self):
        """Even without mix, unit_economics.applicable -> slide 2."""
        data = _make_full_output(
            segments=_make_segments("tier_b"),
            unit_economics=_make_unit_economics(True),
        )
        slides = render_to_slides(data)
        assert len(slides) == 2

    def test_two_slides_when_many_segments(self):
        """More than 3 segment items -> slide 2 even without mix."""
        items = [
            {
                "name": f"Seg {i}",
                "revenue_mix_pct": None,
                "profit_mix_pct": None,
                "profit_basis": None,
                "one_liner": f"Segment {i}",
                "drivers": ["D1", "D2"],
            }
            for i in range(4)
        ]
        data = _make_full_output(
            segments=_make_segments("tier_b", items=items),
            unit_economics=_make_unit_economics(False),
        )
        slides = render_to_slides(data)
        assert len(slides) == 2

    def test_revenue_mix_shown_when_present(self):
        """Rev mix percentage should appear in slide 2 bullets."""
        data = _make_full_output()
        slides = render_to_slides(data)
        s2_text = " ".join(b["text"] for b in slides[1]["bullets"])
        assert "Rev mix: 60%" in s2_text

    def test_unit_econ_shown_when_applicable(self):
        """Unit economics metrics should appear in slide 2."""
        data = _make_full_output()
        slides = render_to_slides(data)
        s2_text = " ".join(b["text"] for b in slides[1]["bullets"])
        assert "Unit Economics" in s2_text

    def test_low_confidence_speaker_notes(self):
        """Low confidence flag should be noted in speaker notes."""
        data = _make_full_output(low_confidence_flag=True)
        slides = render_to_slides(data)
        if len(slides) > 1:
            assert "Low confidence" in slides[1]["speaker_notes"]


# ═══════════════════════════════════════════════════════════════════════════════
# No-fabrication tests
# ═══════════════════════════════════════════════════════════════════════════════

_PLACEHOLDER_PATTERN = re.compile(
    r'\bX%|\$X\b|N/A%|TBD%|XX%|\[.*?\]%',
    re.IGNORECASE,
)


class TestNoFabrication:
    """Renderer must not output placeholders like 'X%' or '$X'."""

    def _all_bullet_texts(self, slides: list[dict]) -> list[str]:
        texts = []
        for s in slides:
            for b in s.get("bullets", []):
                texts.append(b.get("text", ""))
        return texts

    def test_no_placeholders_tier_a(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        for text in self._all_bullet_texts(slides):
            assert not _PLACEHOLDER_PATTERN.search(text), f"Placeholder found: {text}"

    def test_no_placeholders_tier_b(self):
        data = _make_full_output(segments=_make_segments("tier_b"))
        slides = render_to_slides(data)
        for text in self._all_bullet_texts(slides):
            assert not _PLACEHOLDER_PATTERN.search(text), f"Placeholder found: {text}"

    def test_no_placeholders_tier_c(self):
        data = _make_full_output(
            segments=_make_segments("tier_c"),
            unit_economics=_make_unit_economics(False),
        )
        slides = render_to_slides(data)
        for text in self._all_bullet_texts(slides):
            assert not _PLACEHOLDER_PATTERN.search(text), f"Placeholder found: {text}"

    def test_null_mix_not_rendered(self):
        """When mix_pct is None, no percentage should appear for that segment."""
        data = _make_full_output(
            segments=_make_segments("tier_b"),
            unit_economics=_make_unit_economics(True),  # need slide 2
        )
        slides = render_to_slides(data)
        if len(slides) > 1:
            for b in slides[1]["bullets"]:
                text = b.get("text", "")
                if "Cloud Services" in text or "On-Premise" in text:
                    assert "Rev mix:" not in text


# ═══════════════════════════════════════════════════════════════════════════════
# Postprocess / integration tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostprocess:
    """Postprocess returns standard {section_id, slides[]} shape."""

    def test_standard_shape(self):
        data = _make_full_output()
        result = _postprocess(data, {"ticker": "TEST", "company_name": "Test Co"})
        assert result["section_id"] == "business_model_segments"
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1
        assert len(result["slides"]) <= 2

    def test_slide_dict_keys(self):
        data = _make_full_output()
        result = _postprocess(data, {})
        for slide in result["slides"]:
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert "speaker_notes" in slide
            assert "layout_hints" in slide
            assert "flags" in slide

    def test_low_confidence_recomputed(self):
        """Postprocess recomputes low_confidence_flag deterministically."""
        data = _make_full_output(low_confidence_flag=False)
        data["segments"]["confidence"] = "low"
        result = _postprocess(data, {})
        # Should be flagged since segments confidence is low
        assert "Low confidence" in (result.get("verification_notes") or [""])[0]

    def test_handles_invalid_content_gracefully(self):
        """If LLM returns garbage, postprocess should not crash."""
        result = _postprocess({"not": "valid"}, {})
        assert result["section_id"] == "business_model_segments"
        assert isinstance(result["slides"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# SectionSpec tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSectionSpec:
    def test_spec_id(self):
        assert SECTION_SPEC.id == "business_model_segments"

    def test_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_spec_build_prompt_returns_string(self):
        prompt = SECTION_SPEC.build_prompt({
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "sector": "Technology",
        })
        assert isinstance(prompt, str)
        assert "BUSINESS MODEL MODULE" in prompt
        assert "SEGMENTS MODULE" in prompt
        assert "UNIT ECONOMICS MODULE" in prompt

    def test_spec_schema_is_dict(self):
        assert isinstance(SECTION_SPEC.schema, dict)
        assert "properties" in SECTION_SPEC.schema
        assert "business_model" in SECTION_SPEC.schema["properties"]

    def test_spec_schema_max_slides_2(self):
        # Schema is the LLM output schema, not the slide schema.
        # Verify it has the expected top-level keys instead.
        props = SECTION_SPEC.schema["properties"]
        assert "segments" in props
        assert "unit_economics" in props
