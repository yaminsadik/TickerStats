"""
Tests for the Risks & Underwriting section.

Covers:
  - Deterministic ranking ordering
  - Cap at 8 risks
  - No placeholder strings survive
  - No invention: output risk strings are subset of input risk strings
  - break_thesis_line only from flip_conditions
  - Render produces valid slide dict(s)
  - Fallback pipeline correctness
  - Schema validation
  - Spec prompt building and postprocess
  - Registry integration
"""

import pytest

from app.deck.services.sections.risks_underwriting.fallbacks import (
    apply_fallbacks,
    compute_rank_score,
    item_confidence,
    normalize_rank,
    normalize_risks,
    overall_confidence,
    placeholder_scrub,
    sort_risks_by_score,
)
from app.deck.services.sections.risks_underwriting.modules.break_thesis import (
    build_context as break_thesis_build_context,
)
from app.deck.services.sections.risks_underwriting.modules.risk_items import (
    build_context as risk_items_build_context,
)
from app.deck.services.sections.risks_underwriting.render import render_to_slides
from app.deck.services.sections.risks_underwriting.schemas import (
    RiskOut,
    RisksUnderwritingOutput,
)
from app.deck.services.sections.risks_underwriting.spec import SECTION_SPEC


# ── Test data helpers ────────────────────────────────────────────────────────


def _make_risk(
    risk: str = "Revenue concentration",
    impact: str | None = "high",
    probability: str | None = "medium",
    leading_indicator: str | None = "Top-5 customer share",
    mitigant: str | None = "Diversification into SMB",
) -> dict:
    return {
        "risk": risk,
        "impact": impact,
        "probability": probability,
        "leading_indicator": leading_indicator,
        "mitigant": mitigant,
    }


def _make_risks(n: int) -> list[dict]:
    """Generate n distinct risks."""
    base_risks = [
        _make_risk("Revenue concentration", "high", "medium", "Top-5 customer share", "Diversification"),
        _make_risk("Regulatory risk", "high", "low", "Legislative tracker", "Compliance team"),
        _make_risk("FX exposure", "medium", "high", "USD/EUR rate", "Natural hedge"),
        _make_risk("Key person risk", "medium", "medium", "Exec turnover", None),
        _make_risk("Supply chain disruption", "high", "high", "Supplier lead times", "Dual sourcing"),
        _make_risk("Interest rate sensitivity", "low", "medium", "10Y yield", None),
        _make_risk("Technology obsolescence", "medium", "low", None, None),
        _make_risk("Competitive entry", "high", "medium", "Market share data", "Brand moat"),
        _make_risk("Margin compression", "medium", "medium", "Gross margin trend", None),
        _make_risk("Geopolitical risk", "low", "low", None, None),
    ]
    return base_risks[:n]


def _make_output_dict(
    risks: list[dict] | None = None,
    break_thesis_line: str | None = None,
    ticker: str = "AAPL",
) -> dict:
    """Build a RisksUnderwritingOutput-shaped dict."""
    if risks is None:
        risks = _make_risks(5)
    processed, _ = apply_fallbacks(risks)
    conf, flag = overall_confidence(processed)
    return {
        "ticker": ticker,
        "risks": processed,
        "break_thesis_line": break_thesis_line,
        "confidence": conf,
        "low_confidence_flag": flag,
        "notes": None,
    }


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Fallbacks
# ──────────────────────────────────────────────────────────────────────────────


class TestNormalizeRank:
    def test_valid_values(self):
        assert normalize_rank("high") == "high"
        assert normalize_rank("medium") == "medium"
        assert normalize_rank("low") == "low"

    def test_none(self):
        assert normalize_rank(None) == "not_provided"

    def test_empty_string(self):
        assert normalize_rank("") == "not_provided"

    def test_invalid(self):
        assert normalize_rank("extreme") == "not_provided"

    def test_case_insensitive(self):
        assert normalize_rank("HIGH") == "high"
        assert normalize_rank("Medium") == "medium"


class TestComputeRankScore:
    def test_high_high(self):
        assert compute_rank_score("high", "high") == 33

    def test_high_medium(self):
        assert compute_rank_score("high", "medium") == 32

    def test_not_provided(self):
        assert compute_rank_score("not_provided", "not_provided") == 0

    def test_mixed(self):
        assert compute_rank_score("medium", "low") == 21
        assert compute_rank_score("low", "high") == 13


class TestNormalizeRisks:
    def test_basic(self):
        result = normalize_risks([_make_risk()])
        assert len(result) == 1
        assert result[0]["risk"] == "Revenue concentration"

    def test_empty_list(self):
        assert normalize_risks([]) == []

    def test_none(self):
        assert normalize_risks(None) == []

    def test_drops_empty_risk_text(self):
        result = normalize_risks([_make_risk(risk=""), _make_risk(risk="Valid")])
        assert len(result) == 1
        assert result[0]["risk"] == "Valid"

    def test_caps_at_8(self):
        result = normalize_risks(_make_risks(10))
        assert len(result) == 8

    def test_trims_whitespace(self):
        result = normalize_risks([_make_risk(risk="  Padded risk  ")])
        assert result[0]["risk"] == "Padded risk"

    def test_normalizes_ranks(self):
        result = normalize_risks([_make_risk(impact="HIGH", probability=None)])
        assert result[0]["impact"] == "high"
        assert result[0]["probability"] == "not_provided"


class TestItemConfidence:
    def test_high(self):
        r = {"leading_indicator": "metric", "impact": "high", "probability": "medium"}
        assert item_confidence(r) == "high"

    def test_medium_indicator_only(self):
        r = {"leading_indicator": "metric", "impact": "not_provided", "probability": "not_provided"}
        assert item_confidence(r) == "medium"

    def test_medium_rank_only(self):
        r = {"leading_indicator": None, "impact": "high", "probability": "not_provided"}
        assert item_confidence(r) == "medium"

    def test_low(self):
        r = {"leading_indicator": None, "impact": "not_provided", "probability": "not_provided"}
        assert item_confidence(r) == "low"


class TestOverallConfidence:
    def test_high(self):
        risks = [
            {"confidence": "high"}, {"confidence": "high"}, {"confidence": "high"},
            {"confidence": "high"}, {"confidence": "medium"},
        ]
        conf, flag = overall_confidence(risks)
        assert conf == "high"
        assert flag is False

    def test_medium(self):
        risks = [
            {"confidence": "high"}, {"confidence": "medium"}, {"confidence": "low"},
        ]
        conf, flag = overall_confidence(risks)
        assert conf == "medium"
        assert flag is True  # any_low

    def test_low_few_risks(self):
        risks = [{"confidence": "high"}]
        conf, flag = overall_confidence(risks)
        assert conf == "low"
        assert flag is True

    def test_empty(self):
        conf, flag = overall_confidence([])
        assert conf == "low"
        assert flag is True


class TestPlaceholderScrub:
    def test_removes_tbd(self):
        risks = [
            {"risk": "TBD risk", "leading_indicator": None, "mitigant": None},
            {"risk": "Valid risk", "leading_indicator": None, "mitigant": None},
        ]
        cleaned, notes = placeholder_scrub(risks)
        assert len(cleaned) == 1
        assert cleaned[0]["risk"] == "Valid risk"
        assert len(notes) == 1

    def test_removes_question_marks(self):
        risks = [{"risk": "Some risk ??", "leading_indicator": None, "mitigant": None}]
        cleaned, notes = placeholder_scrub(risks)
        assert len(cleaned) == 0

    def test_removes_dollar_x(self):
        risks = [{"risk": "Cost is $X per unit", "leading_indicator": None, "mitigant": None}]
        cleaned, notes = placeholder_scrub(risks)
        assert len(cleaned) == 0

    def test_removes_xx_percent(self):
        risks = [{"risk": "Margin at XX%", "leading_indicator": None, "mitigant": None}]
        cleaned, notes = placeholder_scrub(risks)
        assert len(cleaned) == 0

    def test_keeps_clean(self):
        risks = [{"risk": "Revenue drop", "leading_indicator": "Q metrics", "mitigant": "hedge"}]
        cleaned, notes = placeholder_scrub(risks)
        assert len(cleaned) == 1
        assert len(notes) == 0


class TestApplyFallbacks:
    def test_full_pipeline(self):
        risks, notes = apply_fallbacks(_make_risks(5))
        assert len(risks) == 5
        # Should be sorted descending by rank_score
        scores = [r["rank_score"] for r in risks]
        assert scores == sorted(scores, reverse=True)
        # Each risk has confidence set
        for r in risks:
            assert r["confidence"] in ("high", "medium", "low")


class TestSortStability:
    """Verify stable sort for tied scores."""

    def test_stable_sort(self):
        # Two risks with same impact/probability should maintain original order
        risks = [
            {"risk": "First", "impact": "medium", "probability": "medium",
             "rank_score": compute_rank_score("medium", "medium")},
            {"risk": "Second", "impact": "medium", "probability": "medium",
             "rank_score": compute_rank_score("medium", "medium")},
        ]
        sorted_risks = sort_risks_by_score(risks)
        assert sorted_risks[0]["risk"] == "First"
        assert sorted_risks[1]["risk"] == "Second"


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Ranking ordering deterministic
# ──────────────────────────────────────────────────────────────────────────────


class TestRankingOrder:
    def test_ranking_is_deterministic(self):
        """Same input always produces same order."""
        risks = _make_risks(6)
        result_a, _ = apply_fallbacks(risks)
        result_b, _ = apply_fallbacks(risks)
        assert [r["risk"] for r in result_a] == [r["risk"] for r in result_b]

    def test_highest_score_first(self):
        """Risk with highest impact+probability is first."""
        risks = [
            _make_risk("Low risk", "low", "low"),
            _make_risk("High risk", "high", "high"),
            _make_risk("Med risk", "medium", "medium"),
        ]
        result, _ = apply_fallbacks(risks)
        assert result[0]["risk"] == "High risk"
        assert result[-1]["risk"] == "Low risk"


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Cap at 8
# ──────────────────────────────────────────────────────────────────────────────


class TestCap:
    def test_caps_at_8(self):
        risks, _ = apply_fallbacks(_make_risks(10))
        assert len(risks) <= 8


# ──────────────────────────────────────────────────────────────────────────────
# Tests: No placeholders survive
# ──────────────────────────────────────────────────────────────────────────────


class TestNoPlaceholders:
    def test_tbd_removed(self):
        risks_in = [_make_risk("TBD"), _make_risk("Real risk")]
        result, notes = apply_fallbacks(risks_in)
        risk_texts = [r["risk"] for r in result]
        assert "TBD" not in risk_texts
        assert "Real risk" in risk_texts


# ──────────────────────────────────────────────────────────────────────────────
# Tests: No invention
# ──────────────────────────────────────────────────────────────────────────────


class TestNoInvention:
    def test_output_risks_are_subset_of_input(self):
        """Output risk strings must be subset of input risk strings."""
        input_risks = _make_risks(5)
        input_texts = {r["risk"].strip() for r in input_risks}
        processed, _ = apply_fallbacks(input_risks)
        output_texts = {r["risk"] for r in processed}
        assert output_texts.issubset(input_texts)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: break_thesis_line
# ──────────────────────────────────────────────────────────────────────────────


class TestBreakThesis:
    def test_no_flip_conditions(self):
        ctx = break_thesis_build_context({"risks": []})
        assert ctx["has_flip"] is False
        assert ctx["flip_conditions"] == []

    def test_from_flip_conditions(self):
        ctx = break_thesis_build_context({
            "flip_conditions": ["Revenue drops 20%", "Key customer churns"],
        })
        assert ctx["has_flip"] is True
        assert len(ctx["flip_conditions"]) == 2

    def test_from_thesis_what_changes_mind(self):
        ctx = break_thesis_build_context({
            "thesis": {"what_changes_mind": ["Margin expansion fails"]},
        })
        assert ctx["has_flip"] is True
        assert "Margin expansion fails" in ctx["flip_conditions"]

    def test_dedup_across_sources(self):
        ctx = break_thesis_build_context({
            "flip_conditions": ["Revenue drops"],
            "thesis": {"what_changes_mind": ["Revenue drops", "New condition"]},
        })
        assert len(ctx["flip_conditions"]) == 2


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Render
# ──────────────────────────────────────────────────────────────────────────────


class TestRender:
    def test_produces_valid_slide(self):
        data = _make_output_dict()
        slides = render_to_slides(data)
        assert len(slides) >= 1
        slide = slides[0]
        # Required keys
        assert "slide_id" in slide
        assert "title" in slide
        assert "bullets" in slide
        assert "speaker_notes" in slide
        assert "layout_hints" in slide
        assert "flags" in slide

    def test_slide_title_format(self):
        data = _make_output_dict(ticker="AAPL")
        slides = render_to_slides(data)
        assert "AAPL" in slides[0]["title"]
        assert "Risks & Underwriting" in slides[0]["title"]

    def test_bullets_max_4(self):
        data = _make_output_dict(risks=_make_risks(8))
        slides = render_to_slides(data)
        assert len(slides[0]["bullets"]) <= 4

    def test_break_thesis_in_bullets(self):
        data = _make_output_dict(break_thesis_line="Revenue drops 20%")
        slides = render_to_slides(data)
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("Breaks thesis if:" in t for t in bullet_texts)

    def test_no_break_thesis_when_none(self):
        data = _make_output_dict(break_thesis_line=None)
        slides = render_to_slides(data)
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert not any("Breaks thesis if:" in t for t in bullet_texts)

    def test_empty_risks_minimal_slide(self):
        data = _make_output_dict(risks=[])
        slides = render_to_slides(data)
        assert len(slides) == 1
        assert slides[0]["bullets"][0]["text"] == "No risks provided"

    def test_slide_2_deep_only(self):
        data = _make_output_dict(risks=_make_risks(6))
        # Standard: no slide 2
        slides_std = render_to_slides(data, deck_length="standard")
        assert len(slides_std) == 1
        # Deep: slide 2 if crowded
        slides_deep = render_to_slides(data, deck_length="deep")
        assert len(slides_deep) == 2
        assert "Risk Monitoring" in slides_deep[1]["title"]

    def test_low_confidence_speaker_notes(self):
        data = _make_output_dict(risks=[_make_risk(impact=None, probability=None, leading_indicator=None)])
        data["low_confidence_flag"] = True
        slides = render_to_slides(data)
        assert "Low confidence" in slides[0]["speaker_notes"]


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Schema
# ──────────────────────────────────────────────────────────────────────────────


class TestSchemaValidation:
    def test_valid_output(self):
        output = RisksUnderwritingOutput(
            ticker="AAPL",
            risks=[
                RiskOut(risk="Revenue concentration", impact="high", probability="medium",
                        leading_indicator="Top-5 share", rank_score=32, confidence="high"),
            ],
            confidence="medium",
            low_confidence_flag=True,
        )
        assert output.ticker == "AAPL"
        assert len(output.risks) == 1

    def test_empty_risks_valid(self):
        output = RisksUnderwritingOutput(ticker="AAPL", risks=[])
        assert len(output.risks) == 0

    def test_max_8_risks(self):
        risks = [RiskOut(risk=f"Risk {i}") for i in range(9)]
        with pytest.raises(Exception):
            RisksUnderwritingOutput(ticker="AAPL", risks=risks)


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Spec
# ──────────────────────────────────────────────────────────────────────────────


class TestSpec:
    def test_section_id(self):
        assert SECTION_SPEC.id == "risks_underwriting"

    def test_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context

    def test_build_prompt_with_risks(self):
        inputs = {"ticker": "AAPL", "risks": _make_risks(3)}
        prompt = SECTION_SPEC.build_prompt(inputs)
        assert "AAPL" in prompt
        assert "risk_items" in prompt.lower() or "Risk" in prompt

    def test_build_prompt_empty_risks(self):
        inputs = {"ticker": "AAPL", "risks": []}
        prompt = SECTION_SPEC.build_prompt(inputs)
        assert "AAPL" in prompt

    def test_postprocess_produces_slides(self):
        llm_output = {
            "ticker": "AAPL",
            "risks": [
                {
                    "risk": "Revenue concentration",
                    "impact": "high",
                    "probability": "medium",
                    "leading_indicator": "Top-5 share",
                    "mitigant": "Diversify",
                    "rank_score": 32,
                    "confidence": "high",
                    "notes": None,
                },
                {
                    "risk": "FX exposure",
                    "impact": "medium",
                    "probability": "high",
                    "leading_indicator": "USD/EUR",
                    "mitigant": None,
                    "rank_score": 23,
                    "confidence": "high",
                    "notes": None,
                },
            ],
            "break_thesis_line": "Revenue drops 20%",
            "confidence": "medium",
            "low_confidence_flag": False,
            "notes": None,
        }
        inputs = {"ticker": "AAPL", "deck_length": "standard"}
        result = SECTION_SPEC.postprocess(llm_output, inputs)

        assert result["section_id"] == "risks_underwriting"
        assert "slides" in result
        assert len(result["slides"]) >= 1

        # Verify slide structure
        slide = result["slides"][0]
        assert "slide_id" in slide
        assert "title" in slide
        assert "bullets" in slide

    def test_postprocess_recomputes_ordering(self):
        """Postprocess must recompute rank_score and re-sort."""
        llm_output = {
            "ticker": "AAPL",
            "risks": [
                {"risk": "Low risk", "impact": "low", "probability": "low",
                 "leading_indicator": "X", "rank_score": 99, "confidence": "high"},
                {"risk": "High risk", "impact": "high", "probability": "high",
                 "leading_indicator": "Y", "rank_score": 1, "confidence": "low"},
            ],
            "break_thesis_line": None,
            "confidence": "high",
            "low_confidence_flag": False,
        }
        inputs = {"ticker": "AAPL"}
        result = SECTION_SPEC.postprocess(llm_output, inputs)
        # After recomputation, high/high should be first
        slides = result["slides"]
        # The first bullet should reference high risk
        first_bullet = slides[0]["bullets"][0]["text"]
        assert "High risk" in first_bullet


# ──────────────────────────────────────────────────────────────────────────────
# Tests: Registry integration
# ──────────────────────────────────────────────────────────────────────────────


class TestRegistryIntegration:
    def test_section_registered(self):
        from app.deck.services.sections import ALL_SECTIONS
        assert "risks_underwriting" in ALL_SECTIONS

    def test_get_section(self):
        from app.deck.services.sections import get_section
        spec = get_section("risks_underwriting")
        assert spec.id == "risks_underwriting"

    def test_schema_is_dict(self):
        assert isinstance(SECTION_SPEC.schema, dict)

    def test_postprocess_is_callable(self):
        assert callable(SECTION_SPEC.postprocess)
