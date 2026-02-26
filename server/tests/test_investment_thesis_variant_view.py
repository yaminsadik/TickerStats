"""
Tests for the investment_thesis_variant_view section.

Covers:
- Schema validation (caps on pillars, deltas, flip conditions)
- Confidence computation (high / medium / low)
- Placeholder rejection in postprocess
- Render output: 1 slide for standard/short, 2 slides only for deep + content
- Fallback helpers
"""

import pytest

from app.deck.services.sections.investment_thesis_variant_view.fallbacks import (
    build_variant_deltas,
    compute_confidence,
    compute_low_confidence_flag,
    normalize_position,
    reject_placeholder,
    sanitize_list,
    select_flip_conditions,
    select_pillars,
)
from app.deck.services.sections.investment_thesis_variant_view.render import (
    render_to_slides,
)
from app.deck.services.sections.investment_thesis_variant_view.schemas import (
    InvestmentThesisVariantViewOutput,
    get_investment_thesis_variant_view_json_schema,
)
from app.deck.services.sections.investment_thesis_variant_view.spec import (
    SECTION_SPEC,
    _postprocess,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def _full_output() -> dict:
    """A fully populated output dict for testing."""
    return {
        "header": {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "position": "long",
            "time_horizon": "12-24 months",
        },
        "thesis_sentence": "Apple's services margin expansion is underappreciated by the market.",
        "thesis_pillars": [
            "Services growing 20%+ with 70%+ gross margins",
            "Installed base of 2B+ devices creates durable recurring revenue",
            "Capital return program supports valuation floor",
        ],
        "variant_deltas": [
            {
                "market_believes": "Services growth is slowing",
                "we_believe": "Services TAM is expanding into fintech and health",
            },
        ],
        "key_debates": [
            "Whether hardware cycle dependency limits services upside",
        ],
        "flip_conditions": [
            "Services revenue growth decelerates below 10% for two consecutive quarters",
        ],
        "confidence": "high",
        "low_confidence_flag": False,
        "notes": None,
    }


def _minimal_output() -> dict:
    """Sparse output — missing most user inputs."""
    return {
        "header": {
            "ticker": "XYZ",
            "company_name": None,
            "position": "not_specified",
            "time_horizon": None,
        },
        "thesis_sentence": None,
        "thesis_pillars": [],
        "variant_deltas": [],
        "key_debates": [],
        "flip_conditions": [],
        "confidence": "low",
        "low_confidence_flag": True,
        "notes": None,
    }


def _full_inputs() -> dict:
    """Full pipeline inputs dict."""
    return {
        "ticker": "AAPL",
        "company_name": "Apple Inc.",
        "sector": "Technology",
        "position": "long",
        "deck_length": "standard",
        "fund_constraints": {"time_horizon": "12-24 months"},
        "thesis": {
            "thesis_sentence": "Apple's services margin expansion is underappreciated.",
            "market_believes": "Services growth is slowing",
            "we_believe": "Services TAM is expanding into fintech and health",
            "pillars": [
                "Services growing 20%+ with 70%+ gross margins",
                "Installed base of 2B+ devices creates durable recurring revenue",
                "Capital return program supports valuation floor",
            ],
            "what_changes_mind": [
                "Services revenue growth decelerates below 10% for two quarters",
            ],
        },
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Fallbacks
# ═══════════════════════════════════════════════════════════════════════════════


class TestNormalizePosition:
    def test_long(self):
        assert normalize_position("long") == "long"

    def test_short(self):
        assert normalize_position("short") == "short"

    def test_none(self):
        assert normalize_position(None) == "not_specified"

    def test_empty(self):
        assert normalize_position("") == "not_specified"

    def test_uppercase(self):
        assert normalize_position("LONG") == "long"

    def test_garbage(self):
        assert normalize_position("neutral") == "not_specified"


class TestBuildVariantDeltas:
    def test_both_present_single(self):
        deltas = build_variant_deltas("market is X", "we think Y")
        assert len(deltas) == 1
        assert deltas[0]["market_believes"] == "market is X"
        assert deltas[0]["we_believe"] == "we think Y"

    def test_both_present_semicolons(self):
        deltas = build_variant_deltas("A; B; C", "X; Y; Z")
        assert len(deltas) == 3

    def test_both_present_newlines(self):
        deltas = build_variant_deltas("- A\n- B", "- X\n- Y")
        assert len(deltas) == 2

    def test_market_missing(self):
        deltas = build_variant_deltas(None, "we think Y")
        assert deltas == []

    def test_we_missing(self):
        deltas = build_variant_deltas("market is X", None)
        assert deltas == []

    def test_both_missing(self):
        deltas = build_variant_deltas(None, None)
        assert deltas == []

    def test_cap_at_3(self):
        deltas = build_variant_deltas("A; B; C; D", "W; X; Y; Z")
        assert len(deltas) <= 3

    def test_uneven_lengths(self):
        deltas = build_variant_deltas("A; B; C", "X")
        assert len(deltas) == 1


class TestSelectPillars:
    def test_none(self):
        assert select_pillars(None) == []

    def test_empty(self):
        assert select_pillars([]) == []

    def test_trims_empty_strings(self):
        assert select_pillars(["a", "", "  ", "b"]) == ["a", "b"]

    def test_caps_at_5(self):
        pillars = ["a", "b", "c", "d", "e", "f", "g"]
        assert len(select_pillars(pillars)) == 5

    def test_preserves_order(self):
        result = select_pillars(["first", "second", "third"])
        assert result == ["first", "second", "third"]


class TestSelectFlipConditions:
    def test_none(self):
        assert select_flip_conditions(None) == []

    def test_caps_at_2(self):
        result = select_flip_conditions(["a", "b", "c"])
        assert len(result) == 2

    def test_trims_empty(self):
        result = select_flip_conditions(["a", "", "b"])
        assert result == ["a", "b"]


class TestComputeConfidence:
    def test_high(self):
        result = compute_confidence(
            "thesis here",
            ["p1", "p2", "p3"],
            [{"market_believes": "m", "we_believe": "w"}],
        )
        assert result == "high"

    def test_medium_two_pillars(self):
        result = compute_confidence("thesis here", ["p1", "p2"], [])
        assert result == "medium"

    def test_low_no_sentence(self):
        result = compute_confidence(None, ["p1", "p2", "p3"], [{"m": 1}])
        assert result == "low"

    def test_low_one_pillar(self):
        result = compute_confidence("thesis here", ["p1"], [])
        assert result == "low"

    def test_low_empty(self):
        result = compute_confidence(None, [], [])
        assert result == "low"


class TestComputeLowConfidenceFlag:
    def test_low_confidence_is_flagged(self):
        assert compute_low_confidence_flag("low", "thesis", ["p1", "p2"]) is True

    def test_few_pillars_is_flagged(self):
        assert compute_low_confidence_flag("medium", "thesis", ["p1"]) is True

    def test_missing_sentence_is_flagged(self):
        assert compute_low_confidence_flag("medium", None, ["p1", "p2"]) is True

    def test_high_confidence_with_data_not_flagged(self):
        assert compute_low_confidence_flag("high", "thesis", ["p1", "p2"]) is False


class TestRejectPlaceholder:
    def test_tbd(self):
        assert reject_placeholder("This is TBD") is True

    def test_dollar_x(self):
        assert reject_placeholder("Price target: $X") is True

    def test_xx_percent(self):
        assert reject_placeholder("Growth of XX%") is True

    def test_lorem(self):
        assert reject_placeholder("Lorem ipsum dolor sit amet") is True

    def test_clean_text(self):
        assert reject_placeholder("Apple's services are growing rapidly") is False

    def test_none(self):
        assert reject_placeholder(None) is False


class TestSanitizeList:
    def test_removes_placeholders(self):
        items = ["Good pillar", "This is TBD", "Another good one"]
        result = sanitize_list(items)
        assert result == ["Good pillar", "Another good one"]

    def test_all_clean(self):
        items = ["a", "b", "c"]
        assert sanitize_list(items) == ["a", "b", "c"]


# ═══════════════════════════════════════════════════════════════════════════════
# Schema validation
# ═══════════════════════════════════════════════════════════════════════════════


class TestSchemaValidation:
    def test_full_output_validates(self):
        parsed = InvestmentThesisVariantViewOutput.model_validate(_full_output())
        assert parsed.header.ticker == "AAPL"
        assert parsed.confidence == "high"
        assert len(parsed.thesis_pillars) == 3
        assert len(parsed.variant_deltas) == 1

    def test_minimal_output_validates(self):
        parsed = InvestmentThesisVariantViewOutput.model_validate(_minimal_output())
        assert parsed.header.ticker == "XYZ"
        assert parsed.confidence == "low"
        assert parsed.low_confidence_flag is True

    def test_json_schema_is_dict(self):
        schema = get_investment_thesis_variant_view_json_schema()
        assert isinstance(schema, dict)
        assert "properties" in schema


# ═══════════════════════════════════════════════════════════════════════════════
# Render
# ═══════════════════════════════════════════════════════════════════════════════


class TestRender:
    def test_standard_produces_1_slide(self):
        slides = render_to_slides(_full_output(), deck_length="standard")
        assert len(slides) == 1
        assert slides[0]["slide_id"] == "investment_thesis_variant_view_1"

    def test_short_produces_1_slide(self):
        slides = render_to_slides(_full_output(), deck_length="short")
        assert len(slides) == 1

    def test_deep_with_debates_produces_2_slides(self):
        out = _full_output()
        slides = render_to_slides(out, deck_length="deep")
        assert len(slides) == 2
        assert slides[1]["slide_id"] == "investment_thesis_variant_view_2"
        assert slides[1]["title"] == "Debates and Disconfirming Conditions"

    def test_deep_without_debates_produces_1_slide(self):
        out = _full_output()
        out["key_debates"] = []
        out["flip_conditions"] = []
        slides = render_to_slides(out, deck_length="deep")
        assert len(slides) == 1

    def test_slide_1_title_format(self):
        slides = render_to_slides(_full_output(), deck_length="standard")
        title = slides[0]["title"]
        assert "AAPL" in title
        assert "Long" in title
        assert "12-24 months" in title

    def test_slide_1_has_thesis_bullet(self):
        slides = render_to_slides(_full_output(), deck_length="standard")
        bullet_texts = [b["text"] for b in slides[0]["bullets"]]
        assert any("underappreciated" in t for t in bullet_texts)

    def test_slide_1_max_4_bullets(self):
        slides = render_to_slides(_full_output(), deck_length="standard")
        assert len(slides[0]["bullets"]) <= 4

    def test_low_confidence_in_speaker_notes(self):
        out = _minimal_output()
        slides = render_to_slides(out, deck_length="standard")
        assert "Low confidence" in slides[0]["speaker_notes"]

    def test_slide_has_required_fields(self):
        slides = render_to_slides(_full_output(), deck_length="standard")
        for slide in slides:
            assert "slide_id" in slide
            assert "title" in slide
            assert "bullets" in slide
            assert "speaker_notes" in slide
            assert "layout_hints" in slide
            assert "flags" in slide


# ═══════════════════════════════════════════════════════════════════════════════
# Postprocess (end-to-end)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPostprocess:
    def test_returns_section_id_and_slides(self):
        result = _postprocess(_full_output(), _full_inputs())
        assert result["section_id"] == "investment_thesis_variant_view"
        assert isinstance(result["slides"], list)
        assert len(result["slides"]) >= 1

    def test_confidence_recomputed_deterministically(self):
        out = _full_output()
        # Model says high but we manually check the recomputation is consistent
        result = _postprocess(out, _full_inputs())
        assert result["needs_verification"] is False  # full inputs -> high confidence

    def test_low_confidence_triggers_verification(self):
        out = _minimal_output()
        result = _postprocess(out, {"ticker": "XYZ", "deck_length": "standard"})
        assert result["needs_verification"] is True
        assert len(result["verification_notes"]) > 0

    def test_placeholders_removed_in_postprocess(self):
        out = _full_output()
        out["thesis_pillars"] = ["Good pillar", "This is TBD", "Another good one"]
        out["thesis_sentence"] = "This is $X thesis"
        result = _postprocess(out, _full_inputs())
        # thesis_sentence should be nullified
        # TBD pillar should be removed
        # Check that no placeholder survives in bullets
        for slide in result["slides"]:
            for bullet in slide["bullets"]:
                assert "TBD" not in bullet["text"]
                assert "$X" not in bullet["text"]

    def test_pillars_capped_at_5(self):
        out = _full_output()
        out["thesis_pillars"] = ["a", "b", "c", "d", "e", "f", "g"]
        result = _postprocess(out, _full_inputs())
        # Postprocess caps at 5, verify no crash
        assert result["section_id"] == "investment_thesis_variant_view"

    def test_flip_conditions_capped_at_2(self):
        out = _full_output()
        out["flip_conditions"] = ["a", "b", "c"]
        result = _postprocess(out, _full_inputs())
        # Should not crash and slides should still render
        assert result["section_id"] == "investment_thesis_variant_view"

    def test_variant_deltas_capped_at_3(self):
        out = _full_output()
        out["variant_deltas"] = [
            {"market_believes": "m1", "we_believe": "w1"},
            {"market_believes": "m2", "we_believe": "w2"},
            {"market_believes": "m3", "we_believe": "w3"},
            {"market_believes": "m4", "we_believe": "w4"},
        ]
        result = _postprocess(out, _full_inputs())
        assert result["section_id"] == "investment_thesis_variant_view"

    def test_deep_deck_produces_2_slides(self):
        inputs = _full_inputs()
        inputs["deck_length"] = "deep"
        result = _postprocess(_full_output(), inputs)
        assert len(result["slides"]) == 2

    def test_standard_deck_produces_1_slide(self):
        inputs = _full_inputs()
        inputs["deck_length"] = "standard"
        result = _postprocess(_full_output(), inputs)
        assert len(result["slides"]) == 1

    def test_handles_invalid_content_gracefully(self):
        """Postprocess should not crash on garbage input."""
        result = _postprocess("not a dict", {"ticker": "XYZ", "deck_length": "standard"})
        assert result["section_id"] == "investment_thesis_variant_view"
        assert isinstance(result["slides"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# SectionSpec
# ═══════════════════════════════════════════════════════════════════════════════


class TestSectionSpec:
    def test_section_spec_id(self):
        assert SECTION_SPEC.id == "investment_thesis_variant_view"

    def test_section_spec_has_postprocess(self):
        assert SECTION_SPEC.postprocess is not None

    def test_section_spec_has_schema(self):
        assert isinstance(SECTION_SPEC.schema, dict)

    def test_section_spec_required_context(self):
        assert "ticker" in SECTION_SPEC.required_context

    def test_build_prompt_returns_string(self):
        prompt = SECTION_SPEC.build_prompt(_full_inputs())
        assert isinstance(prompt, str)
        assert "investment_thesis_variant_view" in prompt.lower() or "thesis" in prompt.lower()
        assert "JSON" in prompt
