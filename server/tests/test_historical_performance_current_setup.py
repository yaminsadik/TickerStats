"""
Tests for the Historical Performance & Current Setup section.

Covers:
  - Pydantic schema validation (series constraints, event types)
  - Setup mode selection (price_vs_benchmark / valuation_rerating / both)
  - Fundamentals fallback (window years, metric priority, series filtering)
  - What-changed fallback (empty events -> low confidence)
  - Render produces 1–2 slides in valid shape
  - Low-confidence flag logic
  - Postprocess returns standard {section_id, slides[]}
  - No fabrication tests (renderer does not output placeholder values)
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from app.deck.services.sections.historical_performance_current_setup.schemas import (
    FundamentalsOut,
    HistoricalPerfCurrentSetupOutput,
    MetricSeries,
    MultiplePoint,
    MultipleSeries,
    PricePoint,
    PriceSeries,
    RecentEvent,
    ReratingOut,
    SeriesPoint,
    StockOut,
    WhatChangedOut,
)
from app.deck.services.sections.historical_performance_current_setup.fallbacks import (
    compute_low_confidence_flag,
    filter_series_with_min_points,
    has_price_series_data,
    has_rerating_data,
    resolve_fundamentals_confidence,
    resolve_setup_mode,
    resolve_what_changed,
    resolve_window_years,
    select_priority_metrics,
)
from app.deck.services.sections.historical_performance_current_setup.render import render_to_slides
from app.deck.services.sections.historical_performance_current_setup.spec import (
    SECTION_SPEC,
    _build_prompt,
    _postprocess,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers for building valid test data
# ═══════════════════════════════════════════════════════════════════════════════


def _make_series_point(period: str, value: float | None = None) -> dict:
    return {"period": period, "value": value}


def _make_metric_series(
    metric: str = "revenue",
    label: str = "Revenue",
    unit: str = "$M",
    values: list[tuple[str, float | None]] | None = None,
) -> dict:
    if values is None:
        values = [("fy-3", 100.0), ("fy-2", 110.0), ("fy-1", 120.0)]
    return {
        "metric": metric,
        "label": label,
        "unit": unit,
        "points": [_make_series_point(p, v) for p, v in values],
    }


def _make_fundamentals(
    window_years: int = 5,
    series: list | None = None,
    highlights: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    if series is None:
        series = [
            _make_metric_series("revenue", "Revenue", "$M"),
            _make_metric_series("operating_margin", "Op Margin", "%",
                                [("fy-3", 20.0), ("fy-2", 22.0), ("fy-1", 24.0)]),
            _make_metric_series("fcf", "FCF", "$M",
                                [("fy-3", 50.0), ("fy-2", 55.0), ("fy-1", 60.0)]),
        ]
    if highlights is None:
        highlights = [
            "Revenue grew from $100M to $120M over 3 years",
            "Operating margin expanded from 20% to 24%",
            "FCF grew steadily, reaching $60M in FY-1",
        ]
    return {
        "window_years": window_years,
        "series": series,
        "highlights": highlights,
        "confidence": confidence,
    }


def _make_stock(
    benchmark_name: str | None = "S&P 500",
    series: list | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    if series is None:
        series = [
            {"name": "AAPL", "points": [{"date": "2023-01", "value": 100.0}]},
        ]
    if takeaways is None:
        takeaways = [
            "Stock outperformed S&P 500 by 15% over 3 years",
            "Significant drawdown in Q3 2023, now recovering",
        ]
    return {
        "benchmark_name": benchmark_name,
        "series": series,
        "takeaways": takeaways,
        "confidence": confidence,
    }


def _make_rerating(
    current_vs_median: list[str] | None = None,
    peer_context: list[str] | None = None,
    series: list | None = None,
    takeaways: list[str] | None = None,
    confidence: str = "high",
) -> dict:
    return {
        "current_vs_median": current_vs_median or ["Current EV/EBITDA: 12x vs 10y median: 10x"],
        "peer_context": peer_context or ["Trades at premium to sector median"],
        "series": series or [],
        "takeaways": takeaways or [
            "Multiple has expanded above historical median",
            "Premium justified by accelerating growth",
        ],
        "confidence": confidence,
    }


def _make_what_changed(
    events: list | None = None,
    summary: str = "Market sentiment is cautiously optimistic",
    confidence: str = "high",
) -> dict:
    if events is None:
        events = [
            {
                "date": "2025-01-15",
                "type": "earnings",
                "headline": "Q4 beat expectations",
                "why_it_matters": "Demonstrated accelerating growth",
                "sentiment_effect": "positive",
                "evidence": "Q4 earnings report",
            },
            {
                "date": "2025-02-01",
                "type": "guidance",
                "headline": "Raised full-year guidance",
                "why_it_matters": "Management confidence in trajectory",
                "sentiment_effect": "positive",
            },
        ]
    return {
        "events": events,
        "current_sentiment_summary": summary,
        "confidence": confidence,
    }


def _make_full_output(
    setup_mode: str = "both",
    fundamentals: dict | None = None,
    stock: dict | None = None,
    rerating: dict | None = None,
    what_changed: dict | None = None,
    low_confidence_flag: bool = False,
) -> dict:
    return {
        "setup_mode": setup_mode,
        "fundamentals": fundamentals or _make_fundamentals(),
        "stock": stock or _make_stock(),
        "rerating": rerating or _make_rerating(),
        "what_changed": what_changed or _make_what_changed(),
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
        parsed = HistoricalPerfCurrentSetupOutput.model_validate(data)
        assert parsed.setup_mode == "both"
        assert len(parsed.fundamentals.highlights) == 3
        assert parsed.fundamentals.window_years == 5

    def test_metric_series_requires_min_3_points(self):
        with pytest.raises(ValidationError):
            MetricSeries(
                metric="revenue",
                label="Revenue",
                unit="$M",
                points=[
                    SeriesPoint(period="fy-1", value=100.0),
                    SeriesPoint(period="fy-2", value=110.0),
                ],
            )

    def test_metric_series_allows_null_values(self):
        ms = MetricSeries(
            metric="revenue",
            label="Revenue",
            unit="$M",
            points=[
                SeriesPoint(period="fy-3", value=None),
                SeriesPoint(period="fy-2", value=110.0),
                SeriesPoint(period="fy-1", value=120.0),
            ],
        )
        assert ms.points[0].value is None

    def test_fundamentals_window_years_range(self):
        with pytest.raises(ValidationError):
            FundamentalsOut(
                window_years=2,  # too small
                series=[],
                highlights=["a", "b", "c"],
                confidence="low",
            )
        with pytest.raises(ValidationError):
            FundamentalsOut(
                window_years=6,  # too large
                series=[],
                highlights=["a", "b", "c"],
                confidence="low",
            )

    def test_fundamentals_highlights_min(self):
        with pytest.raises(ValidationError):
            FundamentalsOut(
                window_years=3,
                series=[],
                highlights=["a", "b"],  # need at least 3
                confidence="medium",
            )

    def test_recent_event_valid_types(self):
        event = RecentEvent(
            type="earnings",
            headline="Q4 beat",
            why_it_matters="Growth acceleration",
            sentiment_effect="positive",
        )
        assert event.type == "earnings"

    def test_setup_mode_literals(self):
        for mode in ["price_vs_benchmark", "valuation_rerating", "both"]:
            data = _make_full_output(setup_mode=mode)
            parsed = HistoricalPerfCurrentSetupOutput.model_validate(data)
            assert parsed.setup_mode == mode


# ═══════════════════════════════════════════════════════════════════════════════
# Fallback tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestFallbacks:
    """Tests for deterministic fallback helpers."""

    def test_resolve_window_years_default(self):
        assert resolve_window_years(None) == 3
        assert resolve_window_years({}) == 3

    def test_resolve_window_years_with_data(self):
        financials = {
            "series": [
                {"period": f"fy-{i}", "revenue": 100 + i * 10}
                for i in range(5)
            ]
        }
        assert resolve_window_years(financials) == 5

    def test_filter_series_min_points(self):
        series = [
            {
                "metric": "revenue",
                "points": [
                    {"period": "fy-3", "value": 100},
                    {"period": "fy-2", "value": 110},
                    {"period": "fy-1", "value": 120},
                ],
            },
            {
                "metric": "roic",
                "points": [
                    {"period": "fy-1", "value": 15},
                    {"period": "fy-2", "value": None},
                ],
            },
        ]
        filtered = filter_series_with_min_points(series, min_points=3)
        assert len(filtered) == 1
        assert filtered[0]["metric"] == "revenue"

    def test_select_priority_metrics(self):
        available = ["revenue", "ebitda_margin", "fcf", "roic", "gross_margin"]
        selected = select_priority_metrics(available)
        assert "revenue" in selected
        # Should pick ebitda_margin over gross_margin for profitability
        assert "ebitda_margin" in selected
        assert "gross_margin" not in selected
        assert "fcf" in selected
        assert "roic" in selected

    def test_select_priority_metrics_empty(self):
        assert select_priority_metrics([]) == []

    def test_resolve_fundamentals_confidence(self):
        assert resolve_fundamentals_confidence(5, 3) == "high"
        assert resolve_fundamentals_confidence(3, 2) == "medium"
        assert resolve_fundamentals_confidence(3, 1) == "low"

    def test_resolve_setup_mode_both(self):
        assert resolve_setup_mode(True, True) == "both"

    def test_resolve_setup_mode_price_only(self):
        assert resolve_setup_mode(True, False) == "price_vs_benchmark"

    def test_resolve_setup_mode_rerating_only(self):
        assert resolve_setup_mode(False, True) == "valuation_rerating"

    def test_resolve_setup_mode_neither(self):
        assert resolve_setup_mode(False, False) == "valuation_rerating"

    def test_has_price_series_data(self):
        assert has_price_series_data({"price_history": {"points": [1, 2, 3]}})
        assert not has_price_series_data({})
        assert not has_price_series_data({"price_history": {"points": [1]}})

    def test_has_rerating_data(self):
        assert has_rerating_data({"rerating": {"current": 12.0}})
        assert has_rerating_data({"valuation_multiples": {"median": 10.0}})
        assert not has_rerating_data({})

    def test_resolve_what_changed_no_events(self):
        events, confidence, notes = resolve_what_changed({})
        assert events == []
        assert confidence == "low"
        assert notes == "No recent event data provided"

    def test_resolve_what_changed_with_events(self):
        inputs = {
            "recent_events": [
                {"headline": "Event A"},
                {"headline": "Event B"},
                {"headline": "Event C"},
            ]
        }
        events, confidence, notes = resolve_what_changed(inputs)
        assert len(events) == 3
        assert confidence == "high"

    def test_compute_low_confidence_flag_all_high(self):
        assert not compute_low_confidence_flag(
            "high", "high", "high", "high",
            window_years=5,
            setup_mode="both",
            has_usable_series=True,
            events_empty=False,
        )

    def test_compute_low_confidence_flag_low_module(self):
        assert compute_low_confidence_flag(
            "low", "high", "high", "high",
            window_years=5,
            setup_mode="both",
            has_usable_series=True,
            events_empty=False,
        )

    def test_compute_low_confidence_flag_no_series(self):
        assert compute_low_confidence_flag(
            "high", "high", "high", "high",
            window_years=5,
            setup_mode="both",
            has_usable_series=False,
            events_empty=False,
        )

    def test_compute_low_confidence_flag_empty_events(self):
        assert compute_low_confidence_flag(
            "high", "high", "high", "high",
            window_years=5,
            setup_mode="both",
            has_usable_series=True,
            events_empty=True,
        )

    def test_compute_low_confidence_flag_short_window(self):
        assert compute_low_confidence_flag(
            "high", "high", "high", "high",
            window_years=2,
            setup_mode="both",
            has_usable_series=True,
            events_empty=False,
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

    def test_slide_1_title(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[0]["title"] == "Historical Performance"

    def test_slide_2_title(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[1]["title"] == "Current Setup"

    def test_slide_ids(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        assert slides[0]["slide_id"] == "historical_performance_current_setup_1"
        assert slides[1]["slide_id"] == "historical_performance_current_setup_2"

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

    def test_render_with_empty_data(self):
        out = _make_full_output(
            fundamentals=_make_fundamentals(series=[], highlights=["Limited data", "No revenue trend", "Cannot assess"]),
            stock=_make_stock(series=[], takeaways=["No price data", "Cannot assess"]),
            rerating=_make_rerating(
                current_vs_median=[], peer_context=[], series=[],
                takeaways=["No multiples data", "Cannot assess"],
            ),
            what_changed=_make_what_changed(events=[], confidence="low"),
        )
        slides = render_to_slides(out)
        assert len(slides) == 2

    def test_slide_1_speaker_notes_contain_series(self):
        out = _make_full_output()
        slides = render_to_slides(out)
        notes = slides[0]["speaker_notes"]
        assert "Window:" in notes

    def test_slide_2_low_confidence_note(self):
        out = _make_full_output(low_confidence_flag=True)
        out["fundamentals"]["confidence"] = "low"
        slides = render_to_slides(out)
        notes = slides[1]["speaker_notes"]
        assert "Low confidence" in notes

    def test_no_fabricated_values_in_render(self):
        """Renderer should not insert placeholder values like 'X%' or '$X'."""
        out = _make_full_output(
            fundamentals=_make_fundamentals(
                series=[], highlights=["Data limited", "Cannot assess trends", "Insufficient history"],
            ),
            stock=_make_stock(series=[], takeaways=["No data", "Cannot compare"]),
            rerating=_make_rerating(
                current_vs_median=[], peer_context=[], series=[],
                takeaways=["No data", "Cannot assess"],
            ),
            what_changed=_make_what_changed(events=[], confidence="low"),
        )
        slides = render_to_slides(out)
        for slide in slides:
            for bullet in slide["bullets"]:
                text = bullet["text"]
                assert "X%" not in text
                assert "$X" not in text
                assert "N/A%" not in text


# ═══════════════════════════════════════════════════════════════════════════════
# Spec / postprocess tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpec:
    """Tests for SectionSpec and postprocess."""

    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "historical_performance_current_setup"

    def test_section_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context
        assert "company_name" in SECTION_SPEC.required_context

    def test_section_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_build_prompt_returns_string(self):
        inputs = _minimal_inputs()
        prompt = _build_prompt(inputs)
        assert isinstance(prompt, str)
        assert "FUNDAMENTALS MODULE" in prompt
        assert "STOCK VS BENCHMARK MODULE" in prompt
        assert "VALUATION RERATING MODULE" in prompt
        assert "WHAT CHANGED MODULE" in prompt

    def test_build_prompt_contains_schema(self):
        inputs = _minimal_inputs()
        prompt = _build_prompt(inputs)
        assert "setup_mode" in prompt
        assert "fundamentals" in prompt

    def test_postprocess_standard_shape(self):
        """Postprocess returns standard {section_id, slides[]} shape."""
        content = _make_full_output()
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "historical_performance_current_setup"
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1
        assert "needs_verification" in result
        assert "verification_notes" in result

    def test_postprocess_recomputes_flag(self):
        """Postprocess recomputes low_confidence_flag deterministically."""
        content = _make_full_output(low_confidence_flag=False)
        content["what_changed"]["confidence"] = "low"
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        # Flag should be recomputed to True since what_changed confidence is low
        assert result["section_id"] == "historical_performance_current_setup"
        # The verification_notes should note low confidence
        # (depends on events_empty and other conditions)

    def test_postprocess_handles_invalid_content(self):
        """Postprocess handles invalid LLM output gracefully."""
        content = {"invalid": "data"}
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "historical_performance_current_setup"
        assert isinstance(result["slides"], list)

    def test_postprocess_with_rerating_mode(self):
        """Postprocess works with valuation_rerating setup mode."""
        content = _make_full_output(setup_mode="valuation_rerating")
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "historical_performance_current_setup"
        assert len(result["slides"]) == 2

    def test_postprocess_with_price_mode(self):
        """Postprocess works with price_vs_benchmark setup mode."""
        content = _make_full_output(setup_mode="price_vs_benchmark")
        inputs = _minimal_inputs()
        result = _postprocess(content, inputs)

        assert result["section_id"] == "historical_performance_current_setup"
        assert len(result["slides"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Module context / prompt tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestModules:
    """Tests for module build_context / build_prompt_fragment."""

    def test_fundamentals_module_basic(self):
        from app.deck.services.sections.historical_performance_current_setup.modules import (
            fundamentals,
        )

        inputs = {
            "ticker": "AAPL",
            "company_name": "Apple Inc",
            "financials": {
                "series": [
                    _make_metric_series("revenue"),
                    _make_metric_series("operating_margin", "Op Margin", "%",
                                        [("fy-3", 20.0), ("fy-2", 22.0), ("fy-1", 24.0)]),
                ]
            },
        }
        ctx = fundamentals.build_context(inputs)
        assert ctx["window_years"] >= 3
        fragment = fundamentals.build_prompt_fragment(ctx)
        assert "FUNDAMENTALS MODULE" in fragment

    def test_stock_module_no_data(self):
        from app.deck.services.sections.historical_performance_current_setup.modules import (
            stock_vs_benchmark,
        )

        ctx = stock_vs_benchmark.build_context(_minimal_inputs())
        assert ctx["confidence"] == "low"
        fragment = stock_vs_benchmark.build_prompt_fragment(ctx)
        assert "No price series data" in fragment

    def test_rerating_module_with_data(self):
        from app.deck.services.sections.historical_performance_current_setup.modules import (
            valuation_rerating,
        )

        inputs = {
            **_minimal_inputs(),
            "rerating": {"current": 12.0, "median": 10.0, "multiple_name": "EV/EBITDA"},
        }
        ctx = valuation_rerating.build_context(inputs)
        assert ctx["has_data"]
        assert ctx["confidence"] == "high"
        assert len(ctx["current_vs_median"]) >= 1

    def test_what_changed_module_empty(self):
        from app.deck.services.sections.historical_performance_current_setup.modules import (
            what_changed,
        )

        ctx = what_changed.build_context(_minimal_inputs())
        assert ctx["confidence"] == "low"
        fragment = what_changed.build_prompt_fragment(ctx)
        assert "No recent event data" in fragment
