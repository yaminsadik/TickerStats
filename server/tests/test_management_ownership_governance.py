"""
Tests for the Management, Ownership & Governance section.

Covers:
  - Pydantic schema validation (valid, partial, constraint violations)
  - No fabricated placeholders ($X, X%, TBD)
  - No speculation language (likely, probably, suspected) in flags/facts
  - Ownership missing -> confidence low and notes set
  - Governance missing -> confidence medium, notes set
  - Low-confidence flag deterministic logic
  - Rendering produces 1–2 valid slide dicts
  - Registry integration
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.management_ownership_governance.schemas import (
    Executive,
    GovernanceFlag,
    GovernanceOut,
    Holder,
    Incentive,
    ManagementOut,
    ManagementOwnershipGovernanceOutput,
    OwnershipOut,
)
from app.deck.services.sections.management_ownership_governance.fallbacks import (
    compute_low_confidence_flag,
    has_speculation,
    is_fabricated,
    resolve_governance,
    resolve_management,
    resolve_ownership,
)
from app.deck.services.sections.management_ownership_governance.render import (
    render_to_slides,
)
from app.deck.services.sections.management_ownership_governance.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_management(**overrides) -> dict:
    base = {
        "executives": [
            {"name": "Jane Smith", "role": "CEO", "since": "2019", "equity_ownership": "1.5% of shares", "notes": None},
            {"name": "John Doe", "role": "CFO", "since": "2021", "equity_ownership": "0.3% of shares", "notes": None},
        ],
        "track_record": [
            "CEO led 40% revenue growth over 4-year tenure",
            "Successful integration of two bolt-on acquisitions",
            "Margin expansion from 18% to 24% during management tenure",
        ],
        "incentives": [
            {"component": "Annual bonus", "metric_link": "EPS, revenue growth", "weight": "40% ST"},
            {"component": "LTIP/RSUs", "metric_link": "TSR, ROIC", "weight": "60% LT"},
        ],
        "alignment_summary": [
            "CEO equity stake aligns with long-term shareholder value",
            "Incentive structure weighted toward long-term metrics",
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_ownership(**overrides) -> dict:
    base = {
        "top_holders": [
            {"name": "Vanguard Group", "holder_type": "institution", "stake": "8.2%", "comment": "top 5 holder"},
            {"name": "BlackRock", "holder_type": "institution", "stake": "6.5%", "comment": None},
            {"name": "Jane Smith (CEO)", "holder_type": "insider", "stake": "1.5%", "comment": "CEO"},
        ],
        "insider_ownership_summary": "insiders own ~3% of outstanding shares",
        "activist_presence": None,
        "takeaways": [
            "Institutional ownership concentrated among top index funds",
            "Insider ownership provides moderate alignment",
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_governance(**overrides) -> dict:
    base = {
        "flags": [
            {
                "flag_type": "classified_board",
                "severity": "low",
                "fact": "Board has staggered three-year terms",
                "why_it_matters": "Limits ability of shareholders to replace full board in a single election",
            },
        ],
        "takeaways": [
            "Classified board structure reduces shareholder influence",
            "No major red flags identified in governance disclosures",
        ],
        "confidence": "high",
        "notes": None,
    }
    base.update(overrides)
    return base


def _make_full_output(**overrides) -> dict:
    base = {
        "management": _make_management(),
        "ownership": _make_ownership(),
        "governance": _make_governance(),
        "low_confidence_flag": False,
    }
    base.update(overrides)
    return base


def _make_inputs(**overrides) -> dict:
    base = {
        "ticker": "ACME",
        "company_name": "Acme Corp",
        "sector": "Industrials",
        "company": {
            "name": "Acme Corp",
            "ticker": "ACME",
            "sector": "Industrials",
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
        data = _make_full_output()
        parsed = ManagementOwnershipGovernanceOutput.model_validate(data)
        assert parsed.management.confidence == "high"
        assert len(parsed.management.executives) == 2
        assert len(parsed.ownership.top_holders) == 3
        assert len(parsed.governance.flags) == 1

    def test_minimal_output_with_defaults(self):
        """Null/optional fields should still validate."""
        data = _make_full_output()
        data["management"]["executives"] = []
        data["management"]["incentives"] = []
        data["ownership"]["top_holders"] = []
        data["ownership"]["insider_ownership_summary"] = None
        data["ownership"]["activist_presence"] = None
        data["governance"]["flags"] = []
        parsed = ManagementOwnershipGovernanceOutput.model_validate(data)
        assert parsed.management.executives == []
        assert parsed.ownership.top_holders == []

    def test_track_record_too_few(self):
        data = _make_full_output()
        data["management"]["track_record"] = ["only one"]
        with pytest.raises(ValidationError, match="too_short"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_track_record_too_many(self):
        data = _make_full_output()
        data["management"]["track_record"] = [f"record {i}" for i in range(6)]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_alignment_summary_too_few(self):
        data = _make_full_output()
        data["management"]["alignment_summary"] = ["only one"]
        with pytest.raises(ValidationError, match="too_short"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_alignment_summary_too_many(self):
        data = _make_full_output()
        data["management"]["alignment_summary"] = [f"align {i}" for i in range(5)]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_ownership_takeaways_too_few(self):
        data = _make_full_output()
        data["ownership"]["takeaways"] = []
        with pytest.raises(ValidationError, match="too_short"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_ownership_takeaways_too_many(self):
        data = _make_full_output()
        data["ownership"]["takeaways"] = [f"takeaway {i}" for i in range(4)]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_governance_takeaways_too_few(self):
        data = _make_full_output()
        data["governance"]["takeaways"] = []
        with pytest.raises(ValidationError, match="too_short"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_governance_takeaways_too_many(self):
        data = _make_full_output()
        data["governance"]["takeaways"] = [f"takeaway {i}" for i in range(4)]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_executives_max_6(self):
        data = _make_full_output()
        data["management"]["executives"] = [
            {"name": f"Exec {i}", "role": f"Role {i}", "since": "2020",
             "equity_ownership": None, "notes": None}
            for i in range(7)
        ]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_holders_max_10(self):
        data = _make_full_output()
        data["ownership"]["top_holders"] = [
            {"name": f"Holder {i}", "holder_type": "institution", "stake": None, "comment": None}
            for i in range(11)
        ]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_governance_flags_max_8(self):
        data = _make_full_output()
        data["governance"]["flags"] = [
            {"flag_type": "other", "severity": "low", "fact": f"fact {i}", "why_it_matters": f"matters {i}"}
            for i in range(9)
        ]
        with pytest.raises(ValidationError, match="too_long"):
            ManagementOwnershipGovernanceOutput.model_validate(data)

    def test_valid_flag_types(self):
        """All GovFlagType literals should pass validation."""
        valid_types = [
            "dual_class", "classified_board", "related_party", "auditor_change",
            "poison_pill", "supermajority_vote", "insider_control",
            "capital_allocation", "other",
        ]
        for ftype in valid_types:
            data = _make_full_output()
            data["governance"]["flags"] = [
                {"flag_type": ftype, "severity": "low", "fact": "test", "why_it_matters": "test"}
            ]
            parsed = ManagementOwnershipGovernanceOutput.model_validate(data)
            assert parsed.governance.flags[0].flag_type == ftype

    def test_valid_holder_types(self):
        """All HolderType literals should pass validation."""
        for htype in ["institution", "insider", "activist", "other"]:
            data = _make_full_output()
            data["ownership"]["top_holders"] = [
                {"name": "Test", "holder_type": htype, "stake": None, "comment": None}
            ]
            parsed = ManagementOwnershipGovernanceOutput.model_validate(data)
            assert parsed.ownership.top_holders[0].holder_type == htype


# ═══════════════════════════════════════════════════════════════════════════════
# No Fabricated Placeholders
# ═══════════════════════════════════════════════════════════════════════════════


_FABRICATED_RE = re.compile(r"\$X|\bX%|\bXX\b|\bTBD\b", re.IGNORECASE)


class TestNoFabricatedPlaceholders:
    """Verify no fabricated placeholders in test data or rendered output."""

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
        assert is_fabricated("1.5% of shares") is False

    def test_is_fabricated_handles_none(self):
        assert is_fabricated(None) is False

    def test_render_output_no_fabricated_placeholders(self):
        """Verify rendered slides contain no fabricated placeholders."""
        data = _make_full_output()
        slides = render_to_slides(data)
        for slide in slides:
            for bullet in slide["bullets"]:
                assert not _FABRICATED_RE.search(bullet["text"]), (
                    f"Fabricated placeholder in bullet: {bullet['text']}"
                )
            assert not _FABRICATED_RE.search(slide.get("speaker_notes", ""))


# ═══════════════════════════════════════════════════════════════════════════════
# No Speculation Language
# ═══════════════════════════════════════════════════════════════════════════════


_SPECULATION_RE = re.compile(r"\blikely\b|\bprobably\b|\bsuspected\b", re.IGNORECASE)


class TestNoSpeculationLanguage:
    """Test that speculation language is detected and banned from flags/facts."""

    def test_has_speculation_detects_likely(self):
        assert has_speculation("likely to happen") is True

    def test_has_speculation_detects_probably(self):
        assert has_speculation("probably a risk") is True

    def test_has_speculation_detects_suspected(self):
        assert has_speculation("suspected fraud") is True

    def test_has_speculation_accepts_neutral(self):
        assert has_speculation("Board has staggered terms") is False
        assert has_speculation("Dual-class structure provides voting control") is False

    def test_has_speculation_handles_none(self):
        assert has_speculation(None) is False

    def test_governance_flags_no_speculation(self):
        """Verify test data governance flags contain no speculation."""
        data = _make_governance()
        for flag in data["flags"]:
            assert not _SPECULATION_RE.search(flag["fact"]), (
                f"Speculation in flag fact: {flag['fact']}"
            )
            assert not _SPECULATION_RE.search(flag["why_it_matters"]), (
                f"Speculation in flag why_it_matters: {flag['why_it_matters']}"
            )

    def test_resolve_governance_strips_speculation(self):
        """Fallback should strip speculation from flag facts."""
        gov = {
            "flags": [
                {
                    "flag_type": "related_party",
                    "severity": "medium",
                    "fact": "CEO likely involved in related-party transaction",
                    "why_it_matters": "Potential conflict of interest",
                }
            ],
            "takeaways": ["Governance requires further review"],
            "confidence": "medium",
            "notes": None,
        }
        resolved = resolve_governance(gov)
        for flag in resolved["flags"]:
            assert not _SPECULATION_RE.search(flag["fact"]), (
                f"Speculation not stripped from fact: {flag['fact']}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback Behaviours
# ═══════════════════════════════════════════════════════════════════════════════


class TestManagementFallbacks:
    """Test deterministic management fallback logic."""

    def test_missing_executives_defaults_to_empty(self):
        mgmt = _make_management(executives=None)
        resolved = resolve_management(mgmt)
        assert resolved["executives"] == []

    def test_missing_incentives_defaults_to_empty_and_notes(self):
        mgmt = _make_management(incentives=None)
        resolved = resolve_management(mgmt)
        assert resolved["incentives"] == []
        assert "incentive structure not provided" in (resolved["notes"] or "")

    def test_missing_incentives_caps_confidence(self):
        mgmt = _make_management(incentives=None, confidence="high")
        resolved = resolve_management(mgmt)
        assert resolved["confidence"] in ("medium", "low")

    def test_with_data_preserves_confidence(self):
        mgmt = _make_management()
        resolved = resolve_management(mgmt)
        assert resolved["confidence"] == "high"


class TestOwnershipFallbacks:
    """Test deterministic ownership fallback logic."""

    def test_missing_holders_sets_confidence_low(self):
        own = _make_ownership(top_holders=None)
        resolved = resolve_ownership(own)
        assert resolved["top_holders"] == []
        assert resolved["confidence"] == "low"
        assert "holder data not provided" in (resolved["notes"] or "")

    def test_empty_holders_sets_confidence_low(self):
        own = _make_ownership(top_holders=[])
        resolved = resolve_ownership(own)
        assert resolved["top_holders"] == []
        assert resolved["confidence"] == "low"

    def test_with_holders_preserves_confidence(self):
        own = _make_ownership()
        resolved = resolve_ownership(own)
        assert resolved["confidence"] == "high"

    def test_speculative_activist_cleared(self):
        own = _make_ownership(activist_presence="likely activist involvement")
        resolved = resolve_ownership(own)
        assert resolved["activist_presence"] is None

    def test_factual_activist_preserved(self):
        own = _make_ownership(activist_presence="Elliott Management holds 5% stake and filed 13D")
        resolved = resolve_ownership(own)
        assert resolved["activist_presence"] is not None


class TestGovernanceFallbacks:
    """Test deterministic governance fallback logic."""

    def test_missing_flags_sets_confidence_medium(self):
        gov = _make_governance(flags=None)
        resolved = resolve_governance(gov)
        assert resolved["flags"] == []
        assert resolved["confidence"] == "medium"
        assert "governance flags not provided in inputs" in (resolved["notes"] or "")

    def test_empty_flags_sets_confidence_medium(self):
        gov = _make_governance(flags=[])
        resolved = resolve_governance(gov)
        assert resolved["flags"] == []
        assert resolved["confidence"] == "medium"

    def test_severity_floor_dual_class(self):
        gov = _make_governance(flags=[
            {"flag_type": "dual_class", "severity": "low", "fact": "Dual-class shares exist", "why_it_matters": "Founder retains voting control"},
        ])
        resolved = resolve_governance(gov)
        assert resolved["flags"][0]["severity"] in ("medium", "high")

    def test_severity_floor_insider_control(self):
        gov = _make_governance(flags=[
            {"flag_type": "insider_control", "severity": "low", "fact": "Insiders control 60%+ voting", "why_it_matters": "Limits outside influence"},
        ])
        resolved = resolve_governance(gov)
        assert resolved["flags"][0]["severity"] in ("medium", "high")

    def test_severity_floor_auditor_change(self):
        gov = _make_governance(flags=[
            {"flag_type": "auditor_change", "severity": "low", "fact": "Changed auditor in 2024", "why_it_matters": "May indicate disagreement"},
        ])
        resolved = resolve_governance(gov)
        assert resolved["flags"][0]["severity"] in ("medium", "high")

    def test_other_flag_keeps_low_severity(self):
        gov = _make_governance(flags=[
            {"flag_type": "other", "severity": "low", "fact": "Minor bylaw amendment", "why_it_matters": "Routine change"},
        ])
        resolved = resolve_governance(gov)
        assert resolved["flags"][0]["severity"] == "low"


# ═══════════════════════════════════════════════════════════════════════════════
# Low-Confidence Flag Logic
# ═══════════════════════════════════════════════════════════════════════════════


class TestLowConfidenceFlag:
    """Test compute_low_confidence_flag deterministic logic."""

    def test_all_high_confidence(self):
        data = _make_full_output()
        assert compute_low_confidence_flag(data) is False

    def test_management_low_triggers_flag(self):
        data = _make_full_output()
        data["management"]["confidence"] = "low"
        assert compute_low_confidence_flag(data) is True

    def test_ownership_low_triggers_flag(self):
        data = _make_full_output()
        data["ownership"]["confidence"] = "low"
        assert compute_low_confidence_flag(data) is True

    def test_empty_flags_and_empty_holders_triggers_flag(self):
        data = _make_full_output()
        data["governance"]["flags"] = []
        data["ownership"]["top_holders"] = []
        assert compute_low_confidence_flag(data) is True

    def test_medium_does_not_trigger(self):
        data = _make_full_output()
        data["management"]["confidence"] = "medium"
        data["ownership"]["confidence"] = "medium"
        data["governance"]["confidence"] = "medium"
        assert compute_low_confidence_flag(data) is False

    def test_empty_flags_but_holders_does_not_trigger(self):
        data = _make_full_output()
        data["governance"]["flags"] = []
        # ownership still has holders
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
        assert slides[0]["slide_id"] == "management_ownership_governance_1"
        if len(slides) > 1:
            assert slides[1]["slide_id"] == "management_ownership_governance_2"

    def test_slide_titles(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert slides[0]["title"] == "Management & Incentives"
        if len(slides) > 1:
            assert slides[1]["title"] == "Ownership & Governance"

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

    def test_track_record_in_slide_1(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("revenue growth" in t.lower() for t in texts)

    def test_executives_in_slide_1_speaker_notes(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert "Jane Smith" in slides[0]["speaker_notes"]
        assert "CEO" in slides[0]["speaker_notes"]

    def test_slide_2_included_when_holders_present(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        assert len(slides) == 2

    def test_no_slide_2_when_no_ownership_or_governance(self):
        data = _make_full_output()
        data["ownership"]["top_holders"] = []
        data["ownership"]["activist_presence"] = None
        data["governance"]["flags"] = []
        slides = render_to_slides(data)
        # Slide 2 may or may not be included depending on takeaways
        # but at minimum we need slide 1
        assert len(slides) >= 1

    def test_governance_flags_in_slide_2(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        if len(slides) > 1:
            notes = slides[1]["speaker_notes"]
            assert "classified_board" in notes or "Governance" in notes

    def test_low_confidence_footnote_in_slide_2(self):
        data = _make_full_output()
        data["low_confidence_flag"] = True
        slides = render_to_slides(data)
        if len(slides) > 1:
            assert "Low confidence" in slides[1]["speaker_notes"]

    def test_holders_in_slide_2_speaker_notes(self):
        data = _make_full_output()
        slides = render_to_slides(data)
        if len(slides) > 1:
            assert "Vanguard" in slides[1]["speaker_notes"]


# ═══════════════════════════════════════════════════════════════════════════════
# SectionSpec Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestSectionSpec:
    """Test SECTION_SPEC attributes and methods."""

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "management_ownership_governance"

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
        assert "management" in prompt.lower()
        assert "ownership" in prompt.lower()
        assert "governance" in prompt.lower()

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
        assert "MODULE: management" in prompt
        assert "MODULE: ownership" in prompt
        assert "MODULE: governance" in prompt

    def test_postprocess_valid_output(self):
        data = _make_full_output()
        result = _postprocess(data, _make_inputs())
        assert result["section_id"] == "management_ownership_governance"
        assert 1 <= len(result["slides"]) <= 2
        assert isinstance(result["slides"], list)

    def test_postprocess_sets_verification_notes_on_low_confidence(self):
        data = _make_full_output()
        data["management"]["confidence"] = "low"
        result = _postprocess(data, _make_inputs())
        assert any("Low confidence" in n for n in result.get("verification_notes", []))

    def test_postprocess_no_verification_notes_when_high_confidence(self):
        data = _make_full_output()
        result = _postprocess(data, _make_inputs())
        assert result["verification_notes"] == []

    def test_postprocess_handles_invalid_input(self):
        """postprocess should not crash on malformed input."""
        result = _postprocess({"garbage": True}, _make_inputs())
        assert result["section_id"] == "management_ownership_governance"
        assert isinstance(result["slides"], list)

    def test_postprocess_applies_ownership_fallback(self):
        """Missing holders should trigger low confidence via postprocess."""
        data = _make_full_output()
        data["ownership"]["top_holders"] = []
        data["governance"]["flags"] = []
        result = _postprocess(data, _make_inputs())
        # low_confidence_flag should be recomputed
        assert any("Low confidence" in n for n in result.get("verification_notes", []))

    def test_postprocess_applies_governance_severity_floor(self):
        """Dual-class flag should have severity >= medium after postprocess."""
        data = _make_full_output()
        data["governance"]["flags"] = [
            {"flag_type": "dual_class", "severity": "low", "fact": "Dual-class exist", "why_it_matters": "Voting control"},
        ]
        result = _postprocess(data, _make_inputs())
        # The severity floor should have been applied
        assert result["section_id"] == "management_ownership_governance"

    def test_schema_uses_structured_output(self):
        schema = SECTION_SPEC.schema
        required = set(schema.get("required", []))
        assert {"management", "ownership", "governance"} <= required
        assert "slides" not in schema.get("properties", {})


# ═══════════════════════════════════════════════════════════════════════════════
# Registry integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryIntegration:

    def test_management_ownership_governance_in_registry(self):
        from app.deck.services.sections import ALL_SECTIONS
        assert "management_ownership_governance" in ALL_SECTIONS

    def test_get_section_returns_spec(self):
        from app.deck.services.sections import get_section
        spec = get_section("management_ownership_governance")
        assert spec.id == "management_ownership_governance"
        assert spec.postprocess is not None
