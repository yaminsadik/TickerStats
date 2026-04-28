"""
Tests for schemas and Pydantic models.
"""

import pytest
from pydantic import ValidationError

from app.deck.api.schemas import (
    Provider,
    ReasoningLevel,
    SectionId,
    FundConstraints,
    DeckGenerateRequest,
    DeckPlanRequest,
    BulletPoint,
    Slide,
    SectionResult,
    SECTION_METADATA,
    get_section_schema,
)


class TestEnums:
    """Tests for enum definitions."""
    
    def test_provider_values(self):
        assert Provider.GEMINI.value == "gemini"
    
    def test_reasoning_level_values(self):
        assert ReasoningLevel.LOW.value == "low"
        assert ReasoningLevel.MEDIUM.value == "medium"
        assert ReasoningLevel.HIGH.value == "high"
    
    def test_section_ids(self):
        expected = {
            "company_snapshot",
            "overview",
            "history",
            "business_model_segments",
            "industry_competitive_landscape",
            "historical_performance_current_setup",
            "management_ownership_governance",
            "capital_structure_financial_health",
            "swot",
            "key_drivers_kpis",
            "sector_invariants",
            "investment_thesis",
            "investment_thesis_variant_view",
            "catalysts_timeline",
            "valuation",
            "valuation_summary",
            "risks_underwriting",
        }
        actual = {s.value for s in SectionId}
        assert actual == expected


class TestFundConstraints:
    """Tests for FundConstraints model."""
    
    def test_valid_constraints(self):
        constraints = FundConstraints(
            time_horizon="12-24 months",
            risk_profile="moderate",
        )
        assert constraints.time_horizon == "12-24 months"
        assert constraints.risk_profile == "moderate"
    
    def test_default_style(self):
        constraints = FundConstraints(
            time_horizon="12 months",
            risk_profile="low",
        )
        assert "student investment fund" in constraints.style.lower()
    
    def test_optional_portfolio_context(self):
        constraints = FundConstraints(
            time_horizon="12 months",
            risk_profile="high",
            portfolio_context="Tech-heavy portfolio",
        )
        assert constraints.portfolio_context == "Tech-heavy portfolio"
    
    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            FundConstraints(time_horizon="12 months")  # Missing risk_profile


class TestDeckGenerateRequest:
    """Tests for DeckGenerateRequest model."""
    
    def test_valid_request(self):
        request = DeckGenerateRequest(
            ticker="AAPL",
            company_name="Apple Inc",
            sector="Technology",
            fund_constraints=FundConstraints(
                time_horizon="12-24 months",
                risk_profile="moderate",
            ),
            sections=["overview", "swot"],
            provider=Provider.GEMINI,
        )
        assert request.ticker == "AAPL"
        assert len(request.sections) == 2
    
    def test_ticker_uppercase_conversion(self):
        request = DeckGenerateRequest(
            ticker="aapl",
            company_name="Apple Inc",
            sector="Technology",
            fund_constraints=FundConstraints(
                time_horizon="12 months",
                risk_profile="moderate",
            ),
            sections=["overview"],
            provider=Provider.GEMINI,
        )
        assert request.ticker == "AAPL"
    
    def test_invalid_section_id(self):
        with pytest.raises(ValidationError) as exc_info:
            DeckGenerateRequest(
                ticker="AAPL",
                company_name="Apple",
                sector="Tech",
                fund_constraints=FundConstraints(
                    time_horizon="12 months",
                    risk_profile="low",
                ),
                sections=["overview", "invalid_section"],
                provider=Provider.GEMINI,
            )
        assert "invalid_section" in str(exc_info.value).lower()
    
    def test_duplicate_sections_removed(self):
        request = DeckGenerateRequest(
            ticker="AAPL",
            company_name="Apple",
            sector="Tech",
            fund_constraints=FundConstraints(
                time_horizon="12 months",
                risk_profile="low",
            ),
            sections=["overview", "overview", "swot", "overview"],
            provider=Provider.GEMINI,
        )
        assert request.sections == ["overview", "swot"]
    
    def test_default_reasoning_level(self):
        request = DeckGenerateRequest(
            ticker="AAPL",
            company_name="Apple",
            sector="Tech",
            fund_constraints=FundConstraints(
                time_horizon="12 months",
                risk_profile="low",
            ),
            sections=["overview"],
            provider=Provider.GEMINI,
        )
        assert request.reasoning_level == ReasoningLevel.MEDIUM
    
    def test_empty_sections_list(self):
        with pytest.raises(ValidationError):
            DeckGenerateRequest(
                ticker="AAPL",
                company_name="Apple",
                sector="Tech",
                fund_constraints=FundConstraints(
                    time_horizon="12 months",
                    risk_profile="low",
                ),
                sections=[],
                provider=Provider.GEMINI,
            )
    
    def test_invalid_ticker_format(self):
        with pytest.raises(ValidationError):
            DeckGenerateRequest(
                ticker="INVALID$TICKER",
                company_name="Company",
                sector="Sector",
                fund_constraints=FundConstraints(
                    time_horizon="12 months",
                    risk_profile="low",
                ),
                sections=["overview"],
                provider=Provider.GEMINI,
            )


class TestDeckPlanRequest:
    """Tests for DeckPlanRequest model."""
    
    def test_valid_plan_request(self):
        request = DeckPlanRequest(
            ticker="MSFT",
            sector="Technology",
            fund_constraints=FundConstraints(
                time_horizon="24 months",
                risk_profile="moderate",
            ),
        )
        assert request.ticker == "MSFT"
    
    def test_optional_company_name(self):
        request = DeckPlanRequest(
            ticker="MSFT",
            sector="Technology",
            fund_constraints=FundConstraints(
                time_horizon="24 months",
                risk_profile="moderate",
            ),
        )
        assert request.company_name is None


class TestBulletPoint:
    """Tests for BulletPoint model."""
    
    def test_basic_bullet(self):
        bullet = BulletPoint(text="Key insight about the company")
        assert bullet.text == "Key insight about the company"
        assert bullet.source_needed is False
    
    def test_bullet_with_source_flag(self):
        bullet = BulletPoint(
            text="Revenue grew 15% (source needed)",
            source_needed=True,
        )
        assert bullet.source_needed is True


class TestSlide:
    """Tests for Slide model."""
    
    def test_valid_slide(self):
        slide = Slide(
            slide_id="overview_1",
            title="Company Overview",
            bullets=[
                BulletPoint(text="First point"),
                BulletPoint(text="Second point"),
            ],
        )
        assert slide.slide_id == "overview_1"
        assert len(slide.bullets) == 2
    
    def test_max_bullets_enforced(self):
        with pytest.raises(ValidationError):
            Slide(
                slide_id="test_1",
                title="Test",
                bullets=[BulletPoint(text=f"Point {i}") for i in range(6)],
            )
    
    def test_default_layout_hints(self):
        slide = Slide(
            slide_id="test_1",
            title="Test",
            bullets=[BulletPoint(text="Point")],
        )
        assert slide.layout_hints.style == "bullets"
        assert slide.layout_hints.max_bullets == 4


class TestSectionMetadata:
    """Tests for section metadata."""
    
    def test_all_sections_have_metadata(self):
        for section_id in SectionId:
            assert section_id in SECTION_METADATA
            meta = SECTION_METADATA[section_id]
            assert "id" in meta
            assert "label" in meta
    
    def test_history_requires_verification(self):
        meta = SECTION_METADATA[SectionId.HISTORY]
        assert meta.get("requires_verification") is True


class TestGetSectionSchema:
    """Tests for dynamic schema generation."""
    
    def test_overview_schema(self):
        schema = get_section_schema("overview")
        assert schema["type"] == "object"
        assert "section_id" in schema["required"]
        assert "slides" in schema["required"]
    
    def test_history_schema_requires_verification(self):
        schema = get_section_schema("history")
        assert "needs_verification" in schema["required"]
        assert "verification_notes" in schema["required"]
    
    def test_company_snapshot_slide_limit(self):
        schema = get_section_schema("company_snapshot")
        assert schema["properties"]["slides"]["maxItems"] == 2
