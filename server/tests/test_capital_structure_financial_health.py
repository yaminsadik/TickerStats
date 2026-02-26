"""
Tests for the Capital Structure & Financial Health section.

Covers:
  - Pydantic schema validation (leverage, maturities, liquidity, share count)
  - Confidence resolution and fallback helpers
  - low_confidence_flag logic
  - Runway only when burn rate exists
  - Covenants not inferred
  - Render produces 1–2 valid slide dicts
  - Postprocess returns standard {section_id, slides[]}
  - No fabrication / placeholder tokens ($X, X%, TBD)
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.capital_structure_financial_health.schemas import (
    CapitalStructureFinancialHealthOutput,
    Covenant,
    DebtMaturity,
    InterestMetric,
    LeverageOut,
    LeveragePoint,
    LiquidityMetric,
    LiquidityOut,
    MaturitiesOut,
    Runway,
    ShareCountOut,
    SharePoint,
)
from app.deck.services.sections.capital_structure_financial_health.fallbacks import (
    compute_low_confidence_flag,
    has_burn_rate,
    has_covenant_data,
    has_leverage_data,
    has_maturity_data,
    has_share_data,
    resolve_leverage_confidence,
    resolve_liquidity_confidence,
    resolve_maturities_confidence,
    resolve_share_count_confidence,
)
from app.deck.services.sections.capital_structure_financial_health.render import (
    render_to_slides,
)
from app.deck.services.sections.capital_structure_financial_health.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_leverage(
    series: list | None = None,
    current: float | None = 2.5,
    interest_metrics: list | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    if series is None:
        series = [
            {"period": "FY2021", "net_debt_to_ebitda": 3.0},
            {"period": "FY2022", "net_debt_to_ebitda": 2.8},
            {"period": "TTM", "net_debt_to_ebitda": 2.5},
        ]
    if interest_metrics is None:
        interest_metrics = [
            {"label": "Interest coverage", "value": "5.2x", "as_of": "TTM"},
        ]
    if takeaways is None:
        takeaways = [
            "Net Debt/EBITDA declined from 3.0x to 2.5x over three years",
            "Interest coverage ratio is comfortable at 5.2x",
        ]
    return {
        "leverage_series": series,
        "current_net_debt_to_ebitda": current,
        "interest_metrics": interest_metrics,
        "takeaways": takeaways,
        "confidence": confidence,
    }


def _make_maturities(
    ladder: list | None = None,
    covenants: list | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
    notes: str | None = None,
) -> dict:
    if ladder is None:
        ladder = [
            {"year_bucket": "2025", "amount": "$500M", "instrument": "Term Loan A"},
            {"year_bucket": "2027", "amount": "$1.2B", "instrument": "Senior Notes"},
            {"year_bucket": "2030", "amount": "$800M", "instrument": "Senior Notes"},
        ]
    if covenants is None:
        covenants = []
    if takeaways is None:
        takeaways = [
            "No near-term maturities; earliest maturity in 2025",
            "Debt maturity profile is well-laddered across 2025-2030",
        ]
    return {
        "ladder": ladder,
        "covenants": covenants,
        "takeaways": takeaways,
        "confidence": confidence,
        "notes": notes,
    }


def _make_liquidity(
    metrics: list | None = None,
    runway: dict | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    if metrics is None:
        metrics = [
            {"label": "Cash & equivalents", "value": "$2.1B", "as_of": "Q4 2024"},
            {"label": "Revolver availability", "value": "$1.5B"},
        ]
    if takeaways is None:
        takeaways = [
            "Total liquidity of ~$3.6B provides ample cushion",
            "No near-term liquidity concerns",
        ]
    return {
        "metrics": metrics,
        "runway": runway,
        "takeaways": takeaways,
        "confidence": confidence,
    }


def _make_share_count(
    series: list | None = None,
    buybacks: list[str] | None = None,
    dividends: list[str] | None = None,
    sbc: list[str] | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    if series is None:
        series = [
            {"period": "FY2021", "diluted_shares": 500.0},
            {"period": "FY2022", "diluted_shares": 490.0},
            {"period": "TTM", "diluted_shares": 480.0},
        ]
    if buybacks is None:
        buybacks = ["$2B buyback program authorized in FY2022"]
    if dividends is None:
        dividends = []
    if sbc is None:
        sbc = ["SBC ~$200M/year"]
    if takeaways is None:
        takeaways = [
            "Diluted share count declined 4% over 3 years via buybacks",
            "SBC dilution partially offset by repurchase activity",
        ]
    return {
        "share_series": series,
        "buybacks": buybacks,
        "dividends": dividends,
        "sbc_dilution": sbc,
        "takeaways": takeaways,
        "confidence": confidence,
    }


def _make_full_output(
    leverage: dict | None = None,
    maturities: dict | None = None,
    liquidity: dict | None = None,
    share_count: dict | None = None,
    low_confidence_flag: bool = False,
) -> dict:
    return {
        "leverage_interest": leverage or _make_leverage(),
        "maturities": maturities or _make_maturities(),
        "liquidity": liquidity or _make_liquidity(),
        "share_count": share_count or _make_share_count(),
        "low_confidence_flag": low_confidence_flag,
    }


def _minimal_inputs() -> dict:
    return {"ticker": "AAPL", "company_name": "Apple Inc"}


# ═══════════════════════════════════════════════════════════════════════════════
# Schema validation tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    """Tests for Pydantic schema validation."""

    def test_valid_full_output(self):
        data = _make_full_output()
        parsed = CapitalStructureFinancialHealthOutput.model_validate(data)
        assert len(parsed.leverage_interest.leverage_series) == 3
        assert parsed.leverage_interest.current_net_debt_to_ebitda == 2.5

    def test_leverage_series_max(self):
        """leverage_series may have up to 8 points."""
        series = [{"period": f"FY{2016+i}", "net_debt_to_ebitda": float(i)} for i in range(8)]
        lev = _make_leverage(series=series)
        data = _make_full_output(leverage=lev)
        parsed = CapitalStructureFinancialHealthOutput.model_validate(data)
        assert len(parsed.leverage_interest.leverage_series) == 8

    def test_leverage_null_values_allowed(self):
        pt = LeveragePoint(period="TTM", net_debt_to_ebitda=None)
        assert pt.net_debt_to_ebitda is None

    def test_maturity_ladder_max(self):
        ladder = [{"year_bucket": str(2025 + i), "amount": f"${i}M"} for i in range(10)]
        mat = _make_maturities(ladder=ladder)
        data = _make_full_output(maturities=mat)
        parsed = CapitalStructureFinancialHealthOutput.model_validate(data)
        assert len(parsed.maturities.ladder) == 10

    def test_covenant_types(self):
        for ctype in ["leverage", "interest_coverage", "fixed_charge", "other"]:
            cov = Covenant(type=ctype, description="Test covenant")
            assert cov.type == ctype

    def test_runway_model(self):
        r = Runway(basis="Based on FY burn rate", estimate="≈18 months")
        assert r.estimate == "≈18 months"

    def test_share_series_allows_null(self):
        sp = SharePoint(period="TTM", diluted_shares=None)
        assert sp.diluted_shares is None

    def test_confidence_literals(self):
        for conf in ["high", "medium", "low"]:
            lev = _make_leverage(confidence=conf)
            data = _make_full_output(leverage=lev)
            parsed = CapitalStructureFinancialHealthOutput.model_validate(data)
            assert parsed.leverage_interest.confidence == conf


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbacks:
    """Tests for deterministic fallback helpers."""

    # ── Leverage ──

    def test_resolve_leverage_confidence_high(self):
        assert resolve_leverage_confidence(3, True) == "high"

    def test_resolve_leverage_confidence_medium(self):
        assert resolve_leverage_confidence(1, False) == "medium"
        assert resolve_leverage_confidence(0, True) == "medium"

    def test_resolve_leverage_confidence_low(self):
        assert resolve_leverage_confidence(0, False) == "low"

    def test_has_leverage_data_true(self):
        assert has_leverage_data({"leverage": {"net_debt_to_ebitda": 2.5}})
        assert has_leverage_data({"debt": {"series": [{"period": "FY2021"}]}})

    def test_has_leverage_data_false(self):
        assert not has_leverage_data({})
        assert not has_leverage_data({"leverage": {}})

    # ── Maturities ──

    def test_resolve_maturities_confidence_high(self):
        assert resolve_maturities_confidence(3, False) == "high"

    def test_resolve_maturities_confidence_medium(self):
        assert resolve_maturities_confidence(1, False) == "medium"

    def test_resolve_maturities_confidence_low(self):
        assert resolve_maturities_confidence(0, False) == "low"

    def test_has_maturity_data(self):
        assert has_maturity_data({"maturities": {"ladder": [{"year_bucket": "2025"}]}})
        assert not has_maturity_data({})

    def test_has_covenant_data_true(self):
        assert has_covenant_data({"covenants": [{"description": "Max leverage 4.0x"}]})

    def test_has_covenant_data_false(self):
        assert not has_covenant_data({})
        assert not has_covenant_data({"covenants": []})

    # ── Liquidity ──

    def test_resolve_liquidity_confidence(self):
        assert resolve_liquidity_confidence(2, False) == "high"
        assert resolve_liquidity_confidence(1, False) == "medium"
        assert resolve_liquidity_confidence(0, True) == "medium"
        assert resolve_liquidity_confidence(0, False) == "low"

    def test_has_burn_rate_true(self):
        assert has_burn_rate({"liquidity": {"burn_rate": 100}})
        assert has_burn_rate({"liquidity": {"fcf": -50}})

    def test_has_burn_rate_false(self):
        assert not has_burn_rate({})
        assert not has_burn_rate({"liquidity": {}})
        assert not has_burn_rate({"liquidity": {"fcf": 50}})  # positive FCF

    def test_has_burn_rate_non_numeric(self):
        assert not has_burn_rate({"liquidity": {"burn_rate": "unknown"}})

    # ── Share count ──

    def test_resolve_share_count_confidence_high(self):
        assert resolve_share_count_confidence(2, True, False) == "high"
        assert resolve_share_count_confidence(3, False, True) == "high"

    def test_resolve_share_count_confidence_medium(self):
        assert resolve_share_count_confidence(1, False, False) == "medium"
        assert resolve_share_count_confidence(0, True, False) == "medium"

    def test_resolve_share_count_confidence_low(self):
        assert resolve_share_count_confidence(0, False, False) == "low"

    def test_has_share_data(self):
        assert has_share_data({"shares": {"series": [{"period": "FY2021"}]}})
        assert has_share_data({"shares": {"buybacks": ["$1B"]}})
        assert not has_share_data({})

    # ── Low-confidence flag ──

    def test_compute_low_confidence_flag_all_high(self):
        assert not compute_low_confidence_flag(
            "high", "high", "high", "high",
            maturities_ladder_empty=False,
            leverage_series_empty=False,
        )

    def test_compute_low_confidence_flag_low_module(self):
        assert compute_low_confidence_flag(
            "low", "high", "high", "high",
            maturities_ladder_empty=False,
            leverage_series_empty=False,
        )

    def test_compute_low_confidence_flag_both_empty(self):
        """Flag true when both ladder AND leverage series empty."""
        assert compute_low_confidence_flag(
            "high", "high", "high", "high",
            maturities_ladder_empty=True,
            leverage_series_empty=True,
        )

    def test_compute_low_confidence_flag_one_empty_ok(self):
        """Flag false when only one of ladder/series is empty (and all high)."""
        assert not compute_low_confidence_flag(
            "high", "high", "high", "high",
            maturities_ladder_empty=True,
            leverage_series_empty=False,
        )
        assert not compute_low_confidence_flag(
            "high", "high", "high", "high",
            maturities_ladder_empty=False,
            leverage_series_empty=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Render tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRender:
    """Tests for slide rendering."""

    def test_render_produces_two_slides(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert len(slides) == 2

    def test_render_produces_one_slide_when_no_liq_sc(self):
        """Only 1 slide when liquidity + share count have no takeaways."""
        out = _make_full_output(
            liquidity=_make_liquidity(takeaways=[]),
            share_count=_make_share_count(takeaways=[]),
        )
        slides = render_to_slides(out)
        assert len(slides) == 1

    def test_slide_1_title(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[0]["title"] == "Capital Structure"

    def test_slide_2_title(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[1]["title"] == "Liquidity & Share Count"

    def test_slide_ids(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[0]["slide_id"] == "capital_structure_financial_health_1"
        assert slides[1]["slide_id"] == "capital_structure_financial_health_2"

    def test_bullets_max_4(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        for slide in slides:
            assert len(slide["bullets"]) <= 4

    def test_slide_has_valid_structure(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        for slide in slides:
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert "speaker_notes" in slide
            assert "layout_hints" in slide
            assert "flags" in slide
            for bullet in slide["bullets"]:
                assert "text" in bullet

    def test_slide_1_speaker_notes_contain_ladder(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        notes = slides[0]["speaker_notes"]
        assert "Maturity ladder" in notes

    def test_slide_2_speaker_notes_contain_share_info(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        notes = slides[1]["speaker_notes"]
        assert "Diluted shares" in notes

    def test_low_confidence_annotation(self):
        out = _make_full_output(low_confidence_flag=True)
        slides = render_to_slides(out)
        # Low confidence note should appear in speaker notes
        all_notes = " ".join(s["speaker_notes"] for s in slides)
        assert "Low confidence" in all_notes

    def test_render_with_empty_data(self):
        out = _make_full_output(
            leverage=_make_leverage(series=[], current=None, interest_metrics=[],
                                    takeaways=["No leverage data", "Cannot assess"]),
            maturities=_make_maturities(ladder=[], takeaways=["No maturity data"],
                                         notes="Maturity ladder not provided"),
            liquidity=_make_liquidity(metrics=[], takeaways=["No liquidity data"]),
            share_count=_make_share_count(series=[], buybacks=[], sbc=[],
                                           takeaways=["No share data"]),
        )
        slides = render_to_slides(out)
        assert 1 <= len(slides) <= 2

    def test_no_fabricated_values_in_render(self):
        """Renderer should not insert placeholder values like '$X', 'X%', 'TBD'."""
        out = _make_full_output(
            leverage=_make_leverage(series=[], current=None, interest_metrics=[],
                                    takeaways=["Limited data", "Cannot assess"]),
            maturities=_make_maturities(ladder=[], takeaways=["No data"],
                                         notes="Maturity ladder not provided"),
            liquidity=_make_liquidity(metrics=[], takeaways=["No data"]),
            share_count=_make_share_count(series=[], buybacks=[], sbc=[],
                                           takeaways=["No data"]),
        )
        slides = render_to_slides(out)
        for slide in slides:
            for bullet in slide["bullets"]:
                text = bullet["text"]
                assert "$X" not in text
                assert "X%" not in text
                assert "TBD" not in text
                assert "N/A%" not in text

    def test_runway_only_when_burn_exists(self):
        """Runway should appear in slides only if provided."""
        out_no_runway = _make_full_output(
            liquidity=_make_liquidity(runway=None, takeaways=["No liquidity concerns"]),
        )
        slides = render_to_slides(out_no_runway)
        all_notes = " ".join(s["speaker_notes"] for s in slides)
        assert "Runway:" not in all_notes

        # With runway
        out_with_runway = _make_full_output(
            liquidity=_make_liquidity(
                runway={"basis": "Based on FY burn rate", "estimate": "≈18 months"},
                takeaways=["Runway of ~18 months"],
            ),
        )
        slides2 = render_to_slides(out_with_runway)
        all_notes2 = " ".join(s["speaker_notes"] for s in slides2)
        assert "Runway:" in all_notes2

    def test_covenants_not_inferred(self):
        """Covenants should only appear if explicitly provided."""
        out_no_cov = _make_full_output(
            maturities=_make_maturities(covenants=[], takeaways=["Well-laddered"]),
        )
        slides = render_to_slides(out_no_cov)
        all_notes = " ".join(s["speaker_notes"] for s in slides)
        assert "Covenants:" not in all_notes

        # With covenants
        out_with_cov = _make_full_output(
            maturities=_make_maturities(
                covenants=[{"type": "leverage", "description": "Max 4.0x Net Debt/EBITDA", "headroom": "1.5x"}],
                takeaways=["Well-laddered", "Covenant headroom comfortable"],
            ),
        )
        slides2 = render_to_slides(out_with_cov)
        all_notes2 = " ".join(s["speaker_notes"] for s in slides2)
        assert "Covenants:" in all_notes2


# ═══════════════════════════════════════════════════════════════════════════════
# Spec / postprocess tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpec:
    """Tests for SectionSpec and postprocess."""

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "capital_structure_financial_health"

    def test_section_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_section_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_build_prompt_returns_string(self):
        inputs = _minimal_inputs()
        prompt = _build_prompt(inputs)
        assert isinstance(prompt, str)
        assert "LEVERAGE & INTEREST MODULE" in prompt
        assert "MATURITIES MODULE" in prompt
        assert "LIQUIDITY MODULE" in prompt
        assert "SHARE COUNT MODULE" in prompt

    def test_build_prompt_contains_schema(self):
        inputs = _minimal_inputs()
        prompt = _build_prompt(inputs)
        assert "leverage_interest" in prompt
        assert "maturities" in prompt

    def test_postprocess_standard_shape(self):
        """Postprocess returns standard {section_id, slides[]} shape."""
        content = _make_full_output()
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "capital_structure_financial_health"
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1
        assert len(result["slides"]) <= 2
        assert "needs_verification" in result
        assert "verification_notes" in result

    def test_postprocess_recomputes_flag(self):
        """Postprocess recomputes low_confidence_flag deterministically."""
        content = _make_full_output(low_confidence_flag=False)
        content["leverage_interest"]["confidence"] = "low"
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        # Should have a verification note about low confidence
        assert result["section_id"] == "capital_structure_financial_health"
        assert any("Low confidence" in n for n in result["verification_notes"])

    def test_postprocess_handles_invalid_content(self):
        """Postprocess handles invalid LLM output gracefully."""
        content = {"invalid": "data"}
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "capital_structure_financial_health"
        assert isinstance(result["slides"], list)

    def test_postprocess_with_all_empty(self):
        """Postprocess with fully empty data still returns valid output."""
        content = _make_full_output(
            leverage=_make_leverage(series=[], current=None, interest_metrics=[],
                                    takeaways=["No data", "Cannot assess"],
                                    confidence="low"),
            maturities=_make_maturities(ladder=[], takeaways=["No data"],
                                         confidence="low",
                                         notes="Maturity ladder not provided"),
            liquidity=_make_liquidity(metrics=[], takeaways=["No data"],
                                      confidence="low"),
            share_count=_make_share_count(series=[], buybacks=[], sbc=[],
                                           takeaways=["No data"],
                                           confidence="low"),
        )
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "capital_structure_financial_health"
        assert len(result["slides"]) >= 1
        # Low confidence flag should be set
        assert any("Low confidence" in n for n in result["verification_notes"])


# ═══════════════════════════════════════════════════════════════════════════════
# Module context / prompt tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModules:
    """Tests for module build_context / build_prompt_fragment."""

    def test_leverage_module_basic(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            leverage_interest,
        )

        inputs = {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "leverage": {
                "leverage_series": [
                    {"period": "FY2021", "net_debt_to_ebitda": 3.0},
                    {"period": "FY2022", "net_debt_to_ebitda": 2.8},
                ],
                "net_debt_to_ebitda": 2.5,
                "interest_coverage": 5.2,
            },
        }
        ctx = leverage_interest.build_context(inputs)
        assert len(ctx["leverage_series"]) == 2
        assert ctx["current_net_debt_to_ebitda"] == 2.5
        assert ctx["confidence"] == "high"
        fragment = leverage_interest.build_prompt_fragment(ctx)
        assert "LEVERAGE & INTEREST MODULE" in fragment

    def test_leverage_module_no_data(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            leverage_interest,
        )

        ctx = leverage_interest.build_context(_minimal_inputs())
        assert ctx["confidence"] == "low"
        fragment = leverage_interest.build_prompt_fragment(ctx)
        assert "No leverage series provided" in fragment

    def test_maturities_module_basic(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            maturities,
        )

        inputs = {
            **_minimal_inputs(),
            "maturities": {
                "ladder": [
                    {"year_bucket": "2025", "amount": "$500M", "instrument": "TLA"},
                    {"year_bucket": "2027", "amount": "$1.2B"},
                ],
            },
        }
        ctx = maturities.build_context(inputs)
        assert len(ctx["ladder"]) == 2
        assert ctx["confidence"] == "medium"
        fragment = maturities.build_prompt_fragment(ctx)
        assert "MATURITIES MODULE" in fragment

    def test_maturities_module_no_data(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            maturities,
        )

        ctx = maturities.build_context(_minimal_inputs())
        assert ctx["ladder"] == []
        assert ctx["confidence"] == "low"
        assert ctx["notes"] == "Maturity ladder not provided"

    def test_liquidity_module_basic(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            liquidity,
        )

        inputs = {
            **_minimal_inputs(),
            "liquidity": {
                "metrics": [
                    {"label": "Cash", "value": "$2.1B"},
                    {"label": "Revolver", "value": "$1.5B"},
                ],
            },
        }
        ctx = liquidity.build_context(inputs)
        assert len(ctx["metrics"]) == 2
        assert ctx["confidence"] == "high"
        assert ctx["runway"] is None

    def test_liquidity_module_runway_only_with_burn(self):
        """Runway is None when no burn rate provided."""
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            liquidity,
        )

        # No burn rate — runway should be None even if runway data present
        inputs_no_burn = {
            **_minimal_inputs(),
            "liquidity": {
                "metrics": [{"label": "Cash", "value": "$500M"}],
                "runway": {"basis": "Estimated", "estimate": "12 months"},
            },
        }
        ctx = liquidity.build_context(inputs_no_burn)
        assert ctx["runway"] is None

        # With burn rate
        inputs_burn = {
            **_minimal_inputs(),
            "liquidity": {
                "burn_rate": 100,
                "metrics": [{"label": "Cash", "value": "$500M"}],
                "runway": {"basis": "Based on FY burn rate", "estimate": "≈5 months"},
            },
        }
        ctx2 = liquidity.build_context(inputs_burn)
        assert ctx2["runway"] is not None
        assert ctx2["runway"]["estimate"] == "≈5 months"

    def test_share_count_module_basic(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            share_count,
        )

        inputs = {
            **_minimal_inputs(),
            "shares": {
                "share_series": [
                    {"period": "FY2021", "diluted_shares": 500.0},
                    {"period": "FY2022", "diluted_shares": 490.0},
                ],
                "buybacks": ["$2B program"],
                "sbc": ["~$200M/yr"],
            },
        }
        ctx = share_count.build_context(inputs)
        assert len(ctx["share_series"]) == 2
        assert ctx["confidence"] == "high"
        fragment = share_count.build_prompt_fragment(ctx)
        assert "SHARE COUNT MODULE" in fragment

    def test_share_count_module_no_data(self):
        from app.deck.services.sections.capital_structure_financial_health.modules import (
            share_count,
        )

        ctx = share_count.build_context(_minimal_inputs())
        assert ctx["share_series"] == []
        assert ctx["confidence"] == "low"
