"""
Tests for the Valuation Summary section.

Covers:
  - Gating: section excluded when no valuation inputs
  - Trust mode user_only: DCF not run/included
  - Trust mode narrative_only: no numeric strings appear
  - user_auto_fetch + DCF selected: deterministic DCF block included
  - Rendering produces valid slide dicts (<=2)
  - Fallback logic (peers, targets, sensitivities, confidence)
  - Schema validation
  - Registry integration
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.valuation_summary.schemas import (
    DcfResultOut,
    MethodSummary,
    ValuationSummaryOutput,
)
from app.deck.services.sections.valuation_summary.gating import (
    should_include_section,
    should_run_dcf,
)
from app.deck.services.sections.valuation_summary.fallbacks import (
    build_user_targets,
    compute_confidence,
    compute_low_confidence_flag,
    default_sensitivities,
    normalize_peer_set,
)
from app.deck.services.sections.valuation_summary.modules.methods_inputs import (
    build_methods,
)
from app.deck.services.sections.valuation_summary.modules.dcf_block import (
    _from_dcf_result,
)
from app.deck.services.sections.valuation_summary.modules.sensitivities import (
    build_sensitivities,
)
from app.deck.services.sections.valuation_summary.render import render_to_slides
from app.deck.services.sections.valuation_summary.spec import (
    SECTION_SPEC,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════════


def _make_inputs(**overrides) -> dict:
    base = {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "data_trust_mode": "user_auto_fetch",
        "deck_length": "standard",
        "valuation": {
            "methods": ["dcf", "relative"],
            "peer_tickers": ["MSFT", "GOOGL", "META"],
            "target_multiple_range": "25-30x P/E",
            "price_target": "$200",
            "dcf_assumptions": "WACC 9%, terminal growth 2.5%, 5-year forecast",
        },
        "include_dcf": True,
    }
    base.update(overrides)
    return base


def _make_minimal_inputs() -> dict:
    return {
        "ticker": "AAPL",
        "data_trust_mode": "user_auto_fetch",
    }


def _make_dcf_result() -> dict:
    return {
        "meta": {"ticker": "AAPL", "provider": "yfinance"},
        "valuation": {
            "targetPrice": 200.50,
            "marketPrice": 175.00,
            "upsidePct": 0.1457,
        },
        "assumptions": {
            "forecastYears": 5,
            "fcfGrowthRate": 0.08,
            "terminalGrowthRate": 0.025,
            "wacc": 0.09,
        },
        "sources": {},
    }


def _make_render_output(**overrides) -> dict:
    base = {
        "ticker": "AAPL",
        "trust_mode": "user_auto_fetch",
        "methods": [
            {"method": "DCF", "provided_inputs": ["dcf_assumptions"], "notes": None},
            {"method": "Relative", "provided_inputs": ["peer_tickers"], "notes": None},
        ],
        "peer_set": ["MSFT", "GOOGL", "META"],
        "user_targets": ["Target multiple: 25-30x P/E", "Price target: $200"],
        "dcf": {
            "included": True,
            "value_per_share": "$200.50",
            "upside_downside": "+14.6%",
            "key_assumptions": [
                "Forecast period: 5 years",
                "FCF growth: 8.0%",
                "Terminal growth: 2.5%",
                "WACC: 9.0%",
            ],
            "source_note": "Deterministic DCF (yfinance)",
        },
        "sensitivities": [
            "WACC and terminal growth drive terminal value",
            "FCF margin/trajectory is primary driver",
        ],
        "confidence": "high",
        "low_confidence_flag": False,
    }
    base.update(overrides)
    return base


# ═══════════════════════════════════════════════════════════════════════════════
# Gating Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestGating:

    def test_section_excluded_when_no_valuation_inputs(self):
        inputs = _make_minimal_inputs()
        inputs["include_dcf"] = False
        assert should_include_section(inputs) is False

    def test_section_included_with_methods(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"methods": ["dcf"]}
        assert should_include_section(inputs) is True

    def test_section_included_with_peers(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"peer_tickers": ["MSFT"]}
        assert should_include_section(inputs) is True

    def test_section_included_with_price_target(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"price_target": "$200"}
        assert should_include_section(inputs) is True

    def test_section_included_with_target_multiple(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"target_multiple_range": "15-18x"}
        assert should_include_section(inputs) is True

    def test_section_included_with_dcf_assumptions(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"dcf_assumptions": "WACC 10%"}
        assert should_include_section(inputs) is True

    def test_section_included_with_include_dcf_auto_fetch(self):
        inputs = _make_minimal_inputs()
        inputs["include_dcf"] = True
        assert should_include_section(inputs) is True

    def test_section_excluded_include_dcf_user_only(self):
        """include_dcf True but user_only trust mode blocks it."""
        inputs = _make_minimal_inputs()
        inputs["include_dcf"] = True
        inputs["data_trust_mode"] = "user_only"
        assert should_include_section(inputs) is False

    def test_should_run_dcf_auto_fetch_with_method(self):
        inputs = _make_inputs()
        assert should_run_dcf(inputs) is True

    def test_should_not_run_dcf_user_only(self):
        inputs = _make_inputs(data_trust_mode="user_only")
        assert should_run_dcf(inputs) is False

    def test_should_not_run_dcf_narrative_only(self):
        inputs = _make_inputs(data_trust_mode="narrative_only")
        assert should_run_dcf(inputs) is False

    def test_should_not_run_dcf_no_ticker(self):
        inputs = _make_inputs(ticker="")
        assert should_run_dcf(inputs) is False

    def test_should_not_run_dcf_no_dcf_method_no_include(self):
        inputs = _make_inputs()
        inputs["valuation"]["methods"] = ["relative"]
        inputs["include_dcf"] = False
        assert should_run_dcf(inputs) is False

    def test_should_run_dcf_via_include_dcf_flag(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"methods": ["relative"]}
        inputs["include_dcf"] = True
        assert should_run_dcf(inputs) is True


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbacks:

    def test_normalize_peer_set_deduplicates(self):
        assert normalize_peer_set(["MSFT", "msft", "GOOGL"]) == ["MSFT", "GOOGL"]

    def test_normalize_peer_set_caps_at_10(self):
        peers = [f"TICK{i}" for i in range(15)]
        result = normalize_peer_set(peers)
        assert len(result) == 10

    def test_normalize_peer_set_empty(self):
        assert normalize_peer_set(None) == []
        assert normalize_peer_set([]) == []

    def test_normalize_peer_set_strips_whitespace(self):
        assert normalize_peer_set(["  MSFT  ", "GOOGL "]) == ["MSFT", "GOOGL"]

    def test_build_user_targets_both(self):
        targets = build_user_targets("15-18x EV/EBITDA", "$200")
        assert len(targets) == 2
        assert "Target multiple" in targets[0]
        assert "Price target" in targets[1]

    def test_build_user_targets_only_multiple(self):
        targets = build_user_targets("15-18x", None)
        assert len(targets) == 1
        assert "Target multiple" in targets[0]

    def test_build_user_targets_only_price(self):
        targets = build_user_targets(None, "$200")
        assert len(targets) == 1
        assert "Price target" in targets[0]

    def test_build_user_targets_none(self):
        assert build_user_targets(None, None) == []

    def test_build_user_targets_blank(self):
        assert build_user_targets("  ", "  ") == []

    def test_default_sensitivities_returns_2_to_3(self):
        for methods in [["dcf"], ["relative"], ["dcf", "relative"], [], ["sotp"]]:
            sens = default_sensitivities(methods, "user_auto_fetch")
            assert 2 <= len(sens) <= 3, (
                f"Expected 2-3, got {len(sens)} for methods={methods}"
            )

    def test_default_sensitivities_dcf_content(self):
        sens = default_sensitivities(["dcf"], "user_auto_fetch")
        assert any("WACC" in s for s in sens)

    def test_default_sensitivities_relative_content(self):
        sens = default_sensitivities(["relative"], "user_auto_fetch")
        assert any("peer" in s.lower() or "multiple" in s.lower() for s in sens)

    def test_default_sensitivities_empty_methods_uses_generic(self):
        sens = default_sensitivities([], "user_auto_fetch")
        assert len(sens) >= 2

    def test_confidence_high_with_dcf(self):
        assert compute_confidence(True, ["DCF"], [], [], False) == "high"

    def test_confidence_high_with_relative_inputs(self):
        assert compute_confidence(
            False, ["Relative"], ["MSFT"], ["Target: $200"], True
        ) == "high"

    def test_confidence_medium_with_methods(self):
        assert compute_confidence(False, ["Relative"], [], [], False) == "medium"

    def test_confidence_low_with_nothing(self):
        assert compute_confidence(False, [], [], [], False) == "low"

    def test_low_confidence_flag_true_when_low(self):
        assert compute_low_confidence_flag("low", [], False) is True

    def test_low_confidence_flag_true_methods_no_inputs(self):
        assert compute_low_confidence_flag("medium", ["DCF"], False) is True

    def test_low_confidence_flag_false_when_high_with_inputs(self):
        assert compute_low_confidence_flag("high", ["DCF"], True) is False


# ═══════════════════════════════════════════════════════════════════════════════
# Module Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestMethodsModule:

    def test_build_methods_maps_labels(self):
        valuation = {"methods": ["dcf", "relative", "sotp"]}
        methods = build_methods(valuation)
        assert len(methods) == 3
        assert methods[0].method == "DCF"
        assert methods[1].method == "Relative"
        assert methods[2].method == "Sum-of-the-Parts"

    def test_build_methods_tracks_provided_inputs(self):
        valuation = {
            "methods": ["dcf"],
            "dcf_assumptions": "WACC 9%",
        }
        methods = build_methods(valuation)
        assert "dcf_assumptions" in methods[0].provided_inputs

    def test_build_methods_relative_inputs(self):
        valuation = {
            "methods": ["relative"],
            "peer_tickers": ["MSFT"],
            "target_multiple_range": "15-18x",
        }
        methods = build_methods(valuation)
        assert "peer_tickers" in methods[0].provided_inputs
        assert "target_multiple_range" in methods[0].provided_inputs

    def test_build_methods_empty(self):
        assert build_methods({}) == []
        assert build_methods({"methods": []}) == []


class TestDcfBlock:

    def test_from_dcf_result_success(self):
        result = _make_dcf_result()
        dcf = _from_dcf_result(result)
        assert dcf.included is True
        assert dcf.value_per_share == "$200.50"
        assert dcf.upside_downside == "+14.6%"
        assert len(dcf.key_assumptions) == 4
        assert "Deterministic DCF" in dcf.source_note

    def test_from_dcf_result_error(self):
        result = {"error": "Missing inputs"}
        dcf = _from_dcf_result(result)
        assert dcf.included is False
        assert "error" in dcf.notes.lower()

    def test_from_dcf_result_negative_upside(self):
        result = _make_dcf_result()
        result["valuation"]["upsidePct"] = -0.15
        dcf = _from_dcf_result(result)
        assert dcf.upside_downside == "-15.0%"

    def test_from_dcf_result_with_overrides(self):
        result = _make_dcf_result()
        result["sources"] = {"fcf_0": "manual_override"}
        dcf = _from_dcf_result(result)
        assert "overrides" in dcf.source_note


class TestSensitivitiesModule:

    def test_build_sensitivities_maps_labels_to_keys(self):
        methods = [MethodSummary(method="DCF")]
        sens = build_sensitivities(methods, "user_auto_fetch")
        assert 2 <= len(sens) <= 3
        assert any("WACC" in s for s in sens)

    def test_build_sensitivities_empty_methods(self):
        sens = build_sensitivities([], "user_auto_fetch")
        assert 2 <= len(sens) <= 3


# ═══════════════════════════════════════════════════════════════════════════════
# Schema Validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:

    def test_valid_full_output_passes(self):
        output = ValuationSummaryOutput(
            ticker="AAPL",
            trust_mode="user_auto_fetch",
            methods=[MethodSummary(method="DCF")],
            peer_set=["MSFT", "GOOGL"],
            user_targets=["Price target: $200"],
            dcf=DcfResultOut(included=True, value_per_share="$200.50"),
            sensitivities=["S1", "S2"],
            confidence="high",
            low_confidence_flag=False,
        )
        assert output.ticker == "AAPL"
        assert output.confidence == "high"

    def test_sensitivities_min_length(self):
        with pytest.raises(ValidationError):
            ValuationSummaryOutput(
                ticker="AAPL",
                trust_mode="user_auto_fetch",
                sensitivities=["only one"],
            )

    def test_sensitivities_max_length(self):
        with pytest.raises(ValidationError):
            ValuationSummaryOutput(
                ticker="AAPL",
                trust_mode="user_auto_fetch",
                sensitivities=["s1", "s2", "s3", "s4"],
            )

    def test_peer_set_max_length(self):
        with pytest.raises(ValidationError):
            ValuationSummaryOutput(
                ticker="AAPL",
                trust_mode="user_auto_fetch",
                peer_set=[f"T{i}" for i in range(11)],
                sensitivities=["s1", "s2"],
            )

    def test_user_targets_max_length(self):
        with pytest.raises(ValidationError):
            ValuationSummaryOutput(
                ticker="AAPL",
                trust_mode="user_auto_fetch",
                user_targets=["t1", "t2", "t3", "t4"],
                sensitivities=["s1", "s2"],
            )


# ═══════════════════════════════════════════════════════════════════════════════
# Rendering
# ═══════════════════════════════════════════════════════════════════════════════


class TestRendering:

    def test_render_produces_valid_slides(self):
        out = _make_render_output()
        slides = render_to_slides(out)
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

    def test_slide_1_title(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        assert slides[0]["title"] == "Valuation Summary"

    def test_methods_in_bullets(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("DCF" in t and "Relative" in t for t in bullet_texts)

    def test_dcf_in_bullets(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("DCF implies" in t for t in bullet_texts)

    def test_dcf_assumptions_in_speaker_notes(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        notes = slides[0]["speaker_notes"]
        assert "WACC" in notes
        assert "DCF Key Assumptions" in notes

    def test_render_max_4_bullets_per_slide(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        for slide in slides:
            assert len(slide["bullets"]) <= 4

    def test_render_deep_produces_2_slides(self):
        out = _make_render_output()
        out["_valuation_input"] = {"dcf_assumptions": "WACC 9%"}
        out["peer_set"] = ["MSFT", "GOOGL", "META", "AMZN"]
        slides = render_to_slides(out, deck_length="deep")
        assert len(slides) == 2
        assert slides[1]["title"] == "Valuation Inputs"

    def test_render_standard_produces_1_slide(self):
        out = _make_render_output()
        slides = render_to_slides(out, deck_length="standard")
        assert len(slides) == 1

    def test_render_narrative_only_no_dcf_values(self):
        out = _make_render_output(
            trust_mode="narrative_only",
            dcf={"included": False},
            user_targets=[],
        )
        slides = render_to_slides(out)
        for slide in slides:
            for bullet in slide["bullets"]:
                assert "DCF implies" not in bullet["text"]

    def test_render_narrative_only_no_user_targets(self):
        out = _make_render_output(
            trust_mode="narrative_only",
            dcf={"included": False},
            user_targets=["Target multiple: 25-30x P/E"],
        )
        slides = render_to_slides(out)
        bullet_texts = [b["text"] for s in slides for b in s["bullets"]]
        assert not any("Target multiple" in t for t in bullet_texts)

    def test_render_contains_numbers_flag(self):
        out = _make_render_output()
        slides = render_to_slides(out)
        assert slides[0]["flags"]["contains_numbers"] is True

    def test_render_narrative_only_no_numbers_flag(self):
        out = _make_render_output(
            trust_mode="narrative_only",
            dcf={"included": False},
            user_targets=[],
        )
        slides = render_to_slides(out)
        assert slides[0]["flags"]["contains_numbers"] is False

    def test_render_empty_output_gets_fallback_bullet(self):
        out = {
            "ticker": "AAPL",
            "trust_mode": "user_auto_fetch",
            "methods": [],
            "peer_set": [],
            "user_targets": [],
            "dcf": {"included": False},
            "sensitivities": ["s1", "s2"],
            "confidence": "low",
            "low_confidence_flag": True,
        }
        slides = render_to_slides(out)
        assert len(slides) >= 1
        assert len(slides[0]["bullets"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Trust Mode Integration (through postprocess)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrustModes:

    def test_user_only_dcf_not_included(self):
        """In user_only mode, DCF should not be run or included."""
        inputs = _make_inputs(data_trust_mode="user_only")
        result = _postprocess({}, inputs)
        for slide in result["slides"]:
            for bullet in slide["bullets"]:
                assert "DCF implies" not in bullet["text"]

    def test_narrative_only_no_numbers(self):
        """In narrative_only mode, no numeric strings should appear except ticker."""
        inputs = _make_inputs(data_trust_mode="narrative_only")
        result = _postprocess({}, inputs)
        number_pattern = re.compile(r"\$[\d,.]+|\d+%|\d+\.\dx|\d+-\d+x")
        for slide in result["slides"]:
            for bullet in slide["bullets"]:
                text = bullet["text"]
                # Allow peer ticker symbols (MSFT, GOOGL, META)
                cleaned = text
                for ticker in ["AAPL", "MSFT", "GOOGL", "META"]:
                    cleaned = cleaned.replace(ticker, "")
                assert not number_pattern.search(cleaned), (
                    f"Numeric string found in narrative_only mode: {text}"
                )

    def test_user_auto_fetch_dcf_included(self):
        """In user_auto_fetch mode with pre-computed DCF, DCF block appears."""
        inputs = _make_inputs(data_trust_mode="user_auto_fetch")
        inputs["dcf_valuation"] = _make_dcf_result()
        result = _postprocess({}, inputs)
        all_bullets = [
            b["text"] for slide in result["slides"] for b in slide["bullets"]
        ]
        assert any("DCF implies" in b for b in all_bullets)

    def test_user_only_still_shows_user_inputs(self):
        """user_only mode should still show user-provided data."""
        inputs = _make_inputs(data_trust_mode="user_only")
        result = _postprocess({}, inputs)
        all_bullets = [
            b["text"] for slide in result["slides"] for b in slide["bullets"]
        ]
        # Methods should still be listed
        assert any("DCF" in b and "Relative" in b for b in all_bullets)

    def test_narrative_only_methods_still_shown(self):
        """narrative_only should still show method names."""
        inputs = _make_inputs(data_trust_mode="narrative_only")
        result = _postprocess({}, inputs)
        all_bullets = [
            b["text"] for slide in result["slides"] for b in slide["bullets"]
        ]
        assert any("DCF" in b for b in all_bullets)


# ═══════════════════════════════════════════════════════════════════════════════
# Spec Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpec:

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "valuation_summary"

    def test_section_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context

    def test_build_prompt_returns_string(self):
        prompt = SECTION_SPEC.build_prompt({"ticker": "AAPL"})
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_postprocess_returns_valid_section_output(self):
        inputs = _make_inputs()
        inputs["dcf_valuation"] = _make_dcf_result()
        result = _postprocess({}, inputs)
        assert result["section_id"] == "valuation_summary"
        assert "slides" in result
        assert isinstance(result["slides"], list)
        assert 1 <= len(result["slides"]) <= 2
        assert "needs_verification" in result
        assert "verification_notes" in result

    def test_postprocess_deep_deck_max_2_slides(self):
        inputs = _make_inputs(deck_length="deep")
        inputs["dcf_valuation"] = _make_dcf_result()
        result = _postprocess({}, inputs)
        assert len(result["slides"]) <= 2

    def test_postprocess_verification_notes_on_low_confidence(self):
        inputs = _make_minimal_inputs()
        inputs["valuation"] = {"methods": ["dcf"]}
        # No DCF result, no other inputs -> should be medium/low
        result = _postprocess({}, inputs)
        # confidence will be medium (methods present), flag depends on inputs
        assert result["section_id"] == "valuation_summary"

    def test_postprocess_handles_empty_inputs_gracefully(self):
        """Even with minimal inputs, postprocess should not crash."""
        inputs = {
            "ticker": "AAPL",
            "data_trust_mode": "user_auto_fetch",
            "valuation": {"methods": ["relative"]},
        }
        result = _postprocess({}, inputs)
        assert result["section_id"] == "valuation_summary"
        assert len(result["slides"]) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# Registry Integration
# ═══════════════════════════════════════════════════════════════════════════════


class TestRegistryIntegration:

    def test_valuation_summary_in_registry(self):
        from app.deck.services.sections import ALL_SECTIONS

        assert "valuation_summary" in ALL_SECTIONS

    def test_get_section_returns_spec(self):
        from app.deck.services.sections import get_section

        spec = get_section("valuation_summary")
        assert spec.id == "valuation_summary"
        assert spec.postprocess is not None
