import pytest

from app.deck.services.sections import ALL_SECTIONS, get_section


def test_registry_contains_initial_sections():
    assert set(ALL_SECTIONS.keys()) == {
        "overview",
        "history",
        "swot",
        "company_snapshot",
        "business_model_segments",
        "industry_competitive_landscape",
        "historical_performance_current_setup",
        "management_ownership_governance",
        "capital_structure_financial_health",
        "key_drivers_kpis",
        "sector_invariants",
        "investment_thesis",
        "investment_thesis_variant_view",
        "catalysts_timeline",
        "valuation",
        "valuation_summary",
        "risks_underwriting",
    }


def test_get_section_raises_for_unknown_id():
    with pytest.raises(ValueError, match="Unknown section ID"):
        get_section("unknown_section")
