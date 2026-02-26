"""
Section registry for deck generation.
"""

from app.deck.services.sections.base import SectionSpec
from app.deck.services.sections.business_model_segments import SECTION_SPEC as BUSINESS_MODEL_SEGMENTS_SECTION
from app.deck.services.sections.capital_structure_financial_health import (
    SECTION_SPEC as CAPITAL_STRUCTURE_FINANCIAL_HEALTH_SECTION,
)
from app.deck.services.sections.catalysts_timeline import SECTION_SPEC as CATALYSTS_TIMELINE_SECTION
from app.deck.services.sections.company_snapshot import SECTION_SPEC as COMPANY_SNAPSHOT_SECTION
from app.deck.services.sections.history import SECTION_SPEC as HISTORY_SECTION
from app.deck.services.sections.historical_performance_current_setup import SECTION_SPEC as HISTORICAL_PERFORMANCE_CURRENT_SETUP_SECTION
from app.deck.services.sections.industry_competitive_landscape import SECTION_SPEC as INDUSTRY_COMPETITIVE_LANDSCAPE_SECTION
from app.deck.services.sections.investment_thesis import SECTION_SPEC as INVESTMENT_THESIS_SECTION
from app.deck.services.sections.investment_thesis_variant_view import SECTION_SPEC as INVESTMENT_THESIS_VARIANT_VIEW_SECTION
from app.deck.services.sections.key_drivers_kpis import SECTION_SPEC as KEY_DRIVERS_KPIS_SECTION
from app.deck.services.sections.management_ownership_governance import (
    SECTION_SPEC as MANAGEMENT_OWNERSHIP_GOVERNANCE_SECTION,
)
from app.deck.services.sections.overview import SECTION_SPEC as OVERVIEW_SECTION
from app.deck.services.sections.risks_underwriting import SECTION_SPEC as RISKS_UNDERWRITING_SECTION
from app.deck.services.sections.sector_invariants import SECTION_SPEC as SECTOR_INVARIANTS_SECTION
from app.deck.services.sections.swot import SECTION_SPEC as SWOT_SECTION
from app.deck.services.sections.valuation import SECTION_SPEC as VALUATION_SECTION
from app.deck.services.sections.valuation_summary import SECTION_SPEC as VALUATION_SUMMARY_SECTION

ALL_SECTIONS: dict[str, SectionSpec] = {
    OVERVIEW_SECTION.id: OVERVIEW_SECTION,
    HISTORY_SECTION.id: HISTORY_SECTION,
    SWOT_SECTION.id: SWOT_SECTION,
    COMPANY_SNAPSHOT_SECTION.id: COMPANY_SNAPSHOT_SECTION,
    BUSINESS_MODEL_SEGMENTS_SECTION.id: BUSINESS_MODEL_SEGMENTS_SECTION,
    INDUSTRY_COMPETITIVE_LANDSCAPE_SECTION.id: INDUSTRY_COMPETITIVE_LANDSCAPE_SECTION,
    HISTORICAL_PERFORMANCE_CURRENT_SETUP_SECTION.id: HISTORICAL_PERFORMANCE_CURRENT_SETUP_SECTION,
    MANAGEMENT_OWNERSHIP_GOVERNANCE_SECTION.id: MANAGEMENT_OWNERSHIP_GOVERNANCE_SECTION,
    CAPITAL_STRUCTURE_FINANCIAL_HEALTH_SECTION.id: CAPITAL_STRUCTURE_FINANCIAL_HEALTH_SECTION,
    KEY_DRIVERS_KPIS_SECTION.id: KEY_DRIVERS_KPIS_SECTION,
    SECTOR_INVARIANTS_SECTION.id: SECTOR_INVARIANTS_SECTION,
    INVESTMENT_THESIS_SECTION.id: INVESTMENT_THESIS_SECTION,
    INVESTMENT_THESIS_VARIANT_VIEW_SECTION.id: INVESTMENT_THESIS_VARIANT_VIEW_SECTION,
    CATALYSTS_TIMELINE_SECTION.id: CATALYSTS_TIMELINE_SECTION,
    VALUATION_SECTION.id: VALUATION_SECTION,
    VALUATION_SUMMARY_SECTION.id: VALUATION_SUMMARY_SECTION,
    RISKS_UNDERWRITING_SECTION.id: RISKS_UNDERWRITING_SECTION,
}


def get_section(section_id: str) -> SectionSpec:
    spec = ALL_SECTIONS.get(section_id)
    if spec is None:
        raise ValueError(f"Unknown section ID: {section_id}")
    return spec


__all__ = ["SectionSpec", "ALL_SECTIONS", "get_section"]
