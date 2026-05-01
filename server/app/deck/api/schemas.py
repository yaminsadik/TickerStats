"""
JSON Schemas and Pydantic models for deck generation API.
Defines request/response structures and validation rules.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class Provider(str, Enum):
    """Active LLM provider."""
    GEMINI = "gemini"


class PlanTier(str, Enum):
    """Subscription plan tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class ModelMode(str, Enum):
    """Model selection mode."""
    AUTO = "auto"
    SPECIFIC = "specific"


class AnalysisDepth(str, Enum):
    """High-level depth setting (maps to reasoning level)."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReasoningLevel(str, Enum):
    """Reasoning intensity levels for LLM generation."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DataTrustMode(str, Enum):
    """Controls which sections can introduce numbers."""
    USER_ONLY = "user_only"            # Model cannot introduce numbers
    USER_AUTO_FETCH = "user_auto_fetch" # Numbers from user or auto-fetched sources
    NARRATIVE_ONLY = "narrative_only"   # No numbers except identity facts


class Position(str, Enum):
    """Investment position direction."""
    LONG = "long"
    SHORT = "short"


class DeckLength(str, Enum):
    """Target deck length / slide count."""
    SHORT = "short"        # 6-8 slides
    STANDARD = "standard"  # 10-14 slides
    DEEP = "deep"          # 15-20 slides


class SectionId(str, Enum):
    """Valid deck section identifiers."""
    COMPANY_SNAPSHOT = "company_snapshot"
    OVERVIEW = "overview"
    HISTORY = "history"
    BUSINESS_MODEL_SEGMENTS = "business_model_segments"
    INDUSTRY_COMPETITIVE_LANDSCAPE = "industry_competitive_landscape"
    HISTORICAL_PERFORMANCE_CURRENT_SETUP = "historical_performance_current_setup"
    MANAGEMENT_OWNERSHIP_GOVERNANCE = "management_ownership_governance"
    CAPITAL_STRUCTURE_FINANCIAL_HEALTH = "capital_structure_financial_health"
    SWOT = "swot"
    KEY_DRIVERS_KPIS = "key_drivers_kpis"
    SECTOR_INVARIANTS = "sector_invariants"
    INVESTMENT_THESIS = "investment_thesis"
    INVESTMENT_THESIS_VARIANT_VIEW = "investment_thesis_variant_view"
    CATALYSTS_TIMELINE = "catalysts_timeline"
    VALUATION = "valuation"
    VALUATION_SUMMARY = "valuation_summary"
    RISKS_UNDERWRITING = "risks_underwriting"


# =============================================================================
# Section Metadata
# =============================================================================

SECTION_METADATA = {
    SectionId.COMPANY_SNAPSHOT: {
        "id": "company_snapshot",
        "label": "Company Snapshot",
        "description": "Institutional-quality identity slide with positioning, segments, money model, customers, footprint, and proof points",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.OVERVIEW: {
        "id": "overview",
        "label": "Company Overview",
        "description": "Core business, why now thesis, and near/medium-term catalysts",
        "min_slides": 1,
        "max_slides": 3,
    },
    SectionId.HISTORY: {
        "id": "history",
        "label": "Company History (Draft)",
        "description": "Key company milestones and timeline context (requires verification)",
        "min_slides": 1,
        "max_slides": 2,
        "requires_verification": True,
    },
    SectionId.BUSINESS_MODEL_SEGMENTS: {
        "id": "business_model_segments",
        "label": "Business Model & Segments",
        "description": "What they sell, who they sell to, revenue flow, segment breakdown with mix, and unit economics where disclosed",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.INDUSTRY_COMPETITIVE_LANDSCAPE: {
        "id": "industry_competitive_landscape",
        "label": "Industry & Competitive Landscape",
        "description": "Market definition, sizing, growth drivers, competitive set, positioning, moat drivers, and Porter's Five Forces",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.HISTORICAL_PERFORMANCE_CURRENT_SETUP: {
        "id": "historical_performance_current_setup",
        "label": "Historical Performance & Current Setup",
        "description": "3-5 year revenue, profitability, and cash flow trends plus current stock vs benchmark and/or valuation rerating context with recent event timeline",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.MANAGEMENT_OWNERSHIP_GOVERNANCE: {
        "id": "management_ownership_governance",
        "label": "Management & Ownership",
        "description": "Management track record and incentives, ownership overview, and governance flags",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.CAPITAL_STRUCTURE_FINANCIAL_HEALTH: {
        "id": "capital_structure_financial_health",
        "label": "Capital Structure & Financial Health",
        "description": "Leverage, maturities, liquidity, and share-count/dilution dynamics with risk takeaways",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.SWOT: {
        "id": "swot",
        "label": "SWOT Analysis",
        "description": "Internal strengths/weaknesses and external opportunities/threats with investor relevance",
        "min_slides": 1,
        "max_slides": 3,
    },
    SectionId.KEY_DRIVERS_KPIS: {
        "id": "key_drivers_kpis",
        "label": "Key Drivers & KPIs",
        "description": "Value-driving metrics, definitions, and where they are disclosed",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.SECTOR_INVARIANTS: {
        "id": "sector_invariants",
        "label": "Sector Invariants",
        "description": "Sector-specific value drivers, dependencies, and failure modes",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.INVESTMENT_THESIS: {
        "id": "investment_thesis",
        "label": "Investment Thesis & Variant View",
        "description": "User-defined thesis, market consensus vs variant view, and thesis pillars",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
    SectionId.CATALYSTS_TIMELINE: {
        "id": "catalysts_timeline",
        "label": "Catalysts & Timeline",
        "description": "Specific catalysts with timing windows, mechanisms, and evidence",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
    SectionId.VALUATION: {
        "id": "valuation",
        "label": "Valuation",
        "description": "Valuation framework with user-selected methods, comparables, and price target",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
    SectionId.INVESTMENT_THESIS_VARIANT_VIEW: {
        "id": "investment_thesis_variant_view",
        "label": "Investment Thesis",
        "description": "User-locked thesis, variant view, and disconfirming conditions",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
    SectionId.RISKS_UNDERWRITING: {
        "id": "risks_underwriting",
        "label": "Risks & Underwriting",
        "description": "Ranked risks with leading indicators and mitigants",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
    SectionId.VALUATION_SUMMARY: {
        "id": "valuation_summary",
        "label": "Valuation Summary",
        "description": "Valuation methods selected, key inputs, and deterministic DCF output when available",
        "min_slides": 1,
        "max_slides": 2,
        "requires_user_input": True,
    },
}


# =============================================================================
# Request Models
# =============================================================================

class FundConstraints(BaseModel):
    """Investment fund constraints for generation context."""
    time_horizon: str = Field(
        ...,
        description="Investment time horizon (e.g., '12-24 months')",
        min_length=1,
        max_length=100,
    )
    risk_profile: str = Field(
        ...,
        description="Risk tolerance level (e.g., 'moderate', 'aggressive', 'conservative')",
        min_length=1,
        max_length=50,
    )
    portfolio_context: Optional[str] = Field(
        None,
        description="Optional additional portfolio context",
        max_length=1000,
    )
    style: str = Field(
        default="student investment fund pitch deck",
        description="Presentation style/audience",
        max_length=200,
    )


class ThesisInput(BaseModel):
    """User-provided investment thesis for the pitch."""
    thesis_sentence: Optional[str] = Field(
        None,
        description="Structured thesis: 'Market is wrong because ___; it reprices when ___.'",
        max_length=500,
    )
    market_believes: Optional[str] = Field(
        None,
        description="What consensus / the market currently believes",
        max_length=1000,
    )
    we_believe: Optional[str] = Field(
        None,
        description="User's variant view — what they believe instead",
        max_length=1000,
    )
    pillars: list[str] = Field(
        default_factory=list,
        description="2-5 thesis pillars supporting the view",
        max_length=5,
    )
    what_changes_mind: list[str] = Field(
        default_factory=list,
        description="1-2 conditions that would invalidate the thesis",
        max_length=2,
    )


class CatalystInput(BaseModel):
    """A single catalyst event with timing."""
    name: str = Field(..., description="Catalyst name", max_length=200)
    timing_window: Optional[str] = Field(
        None,
        description="Expected timing (e.g., 'Q2 2025', 'H1 2025')",
        max_length=50,
    )
    mechanism: Optional[str] = Field(
        None,
        description="What changes and why the market reacts",
        max_length=500,
    )
    evidence: Optional[str] = Field(
        None,
        description="Supporting evidence or data paste",
        max_length=2000,
    )


class ValuationInput(BaseModel):
    """User-provided valuation approach and assumptions."""
    methods: list[str] = Field(
        default_factory=list,
        description="Selected valuation methods (relative, dcf, sotp, nav, unit_econ, yield)",
        max_length=6,
    )
    peer_tickers: list[str] = Field(
        default_factory=list,
        description="Comparable company tickers for relative valuation",
        max_length=20,
    )
    target_multiple_range: Optional[str] = Field(
        None,
        description="Target multiple range (e.g., '15-18x EV/EBITDA')",
        max_length=200,
    )
    dcf_assumptions: Optional[str] = Field(
        None,
        description="DCF assumptions: WACC, terminal growth, margin path",
        max_length=2000,
    )
    price_target: Optional[str] = Field(
        None,
        description="User's price target or range",
        max_length=100,
    )


class RiskInput(BaseModel):
    """A single risk factor with monitoring details."""
    risk: str = Field(..., description="Risk description", max_length=300)
    impact: Optional[str] = Field(
        None,
        description="Impact severity: high, medium, or low",
        max_length=20,
    )
    probability: Optional[str] = Field(
        None,
        description="Probability: high, medium, or low",
        max_length=20,
    )
    leading_indicator: Optional[str] = Field(
        None,
        description="How to monitor this risk",
        max_length=300,
    )
    mitigant: Optional[str] = Field(
        None,
        description="Mitigant or hedge approach",
        max_length=500,
    )


class DataBlocks(BaseModel):
    """User-pasted data blocks for accuracy."""
    kpi_table: Optional[str] = Field(
        None, description="KPI table (ARR/NRR/churn/backlog/etc.)", max_length=5000,
    )
    segment_mix: Optional[str] = Field(
        None, description="Segment revenue mix table", max_length=5000,
    )
    debt_maturities: Optional[str] = Field(
        None, description="Debt maturity schedule", max_length=5000,
    )
    ownership_notes: Optional[str] = Field(
        None, description="Ownership/governance notes", max_length=5000,
    )
    filing_excerpts: Optional[str] = Field(
        None, description="Filing excerpts or other source data", max_length=10000,
    )


class UserConstraints(BaseModel):
    """Portfolio-level constraints that gate content."""
    liquidity_floor: Optional[str] = Field(
        None, description="Minimum liquidity requirement", max_length=200,
    )
    leverage_ceiling: Optional[str] = Field(
        None, description="Maximum leverage tolerance", max_length=200,
    )
    esg_constraints: Optional[str] = Field(
        None, description="ESG screen or exclusion criteria", max_length=500,
    )
    exclude_peers: list[str] = Field(
        default_factory=list,
        description="Peer groups or industries to exclude",
        max_length=20,
    )


class DeckGenerateRequest(BaseModel):
    """Request schema for POST /api/v1/deck/generate."""
    ticker: str = Field(
        ...,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z0-9.\-]+$",
    )
    company_name: Optional[str] = Field(
        None,
        description="Full company name (auto-fetched from ticker if not provided)",
        min_length=1,
        max_length=200,
    )
    sector: Optional[str] = Field(
        None,
        description="Industry sector (auto-fetched from ticker if not provided)",
        min_length=1,
        max_length=100,
    )
    fund_constraints: FundConstraints
    sections: list[str] = Field(
        ...,
        description="List of section IDs to generate",
        min_length=1,
    )
    plan_tier: Optional[PlanTier] = Field(
        None,
        description="Plan tier (free/pro/enterprise). Server may override.",
    )
    model_mode: Optional[ModelMode] = Field(
        None,
        description="Model selection mode (auto or specific).",
    )
    analysis_depth: Optional[AnalysisDepth] = Field(
        None,
        description="High-level depth setting (low/medium/high).",
    )
    provider: Provider = Field(
        ...,
        description="LLM provider to use",
    )
    model: Optional[str] = Field(
        None,
        description="Specific model to use (provider-dependent)",
        max_length=100,
    )
    reasoning_level: ReasoningLevel = Field(
        default=ReasoningLevel.MEDIUM,
        description="Reasoning intensity for generation",
    )
    include_comps: bool = Field(
        default=False,
        description="Include comparables table from yfinance",
    )
    comp_tickers: Optional[list[str]] = Field(
        None,
        description="Optional explicit list of comparable tickers (auto-selected by sector if not provided)",
        max_length=50,
    )
    include_dcf: bool = Field(
        default=True,
        description="Include DCF target price calculation (deterministic)",
    )
    # --- Intake redesign fields (all optional for backward compatibility) ---
    position: Optional[Position] = Field(
        None,
        description="Investment position direction (long/short)",
    )
    deck_length: Optional[DeckLength] = Field(
        DeckLength.STANDARD,
        description="Target deck length (short/standard/deep)",
    )
    data_trust_mode: Optional[DataTrustMode] = Field(
        DataTrustMode.USER_AUTO_FETCH,
        description="Controls whether the model may introduce numbers",
    )
    thesis: Optional[ThesisInput] = Field(
        None,
        description="User-provided investment thesis and variant view",
    )
    catalysts: list[CatalystInput] = Field(
        default_factory=list,
        description="User-provided catalyst events with timing",
    )
    valuation_input: Optional[ValuationInput] = Field(
        None,
        description="User-provided valuation approach and assumptions",
    )
    risks: list[RiskInput] = Field(
        default_factory=list,
        description="User-provided risk factors",
    )
    data_blocks: Optional[DataBlocks] = Field(
        None,
        description="User-pasted data blocks (KPIs, segments, debt, etc.)",
    )
    user_constraints: Optional[UserConstraints] = Field(
        None,
        description="Portfolio-level constraints",
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        """Ensure ticker is uppercase."""
        if isinstance(v, str):
            return v.upper().strip()
        return v

    @field_validator("sections", mode="after")
    @classmethod
    def validate_sections(cls, v: list[str]) -> list[str]:
        """Validate all sections are known."""
        valid_ids = {s.value for s in SectionId}
        invalid = [s for s in v if s not in valid_ids]
        if invalid:
            raise ValueError(f"Invalid section IDs: {invalid}. Valid: {list(valid_ids)}")
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for s in v:
            if s not in seen:
                seen.add(s)
                result.append(s)
        return result


class DeckPlanRequest(BaseModel):
    """Request schema for POST /api/v1/deck/plan."""
    ticker: str = Field(
        ...,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10,
        pattern=r"^[A-Z0-9.\-]+$",
    )
    company_name: Optional[str] = Field(
        None,
        description="Full company name (optional, will be fetched if missing)",
        max_length=200,
    )
    sector: str = Field(
        ...,
        description="Industry sector",
        min_length=1,
        max_length=100,
    )
    fund_constraints: FundConstraints
    provider: Provider = Field(
        default=Provider.GEMINI,
        description="LLM provider to use for planning",
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        if isinstance(v, str):
            return v.upper().strip()
        return v


# =============================================================================
# Response Models - Slide Components
# =============================================================================

class BulletPoint(BaseModel):
    """Single bullet point in a slide."""
    text: str = Field(..., description="Bullet text content", max_length=500)
    source_needed: bool = Field(
        default=False,
        description="Whether this bullet requires source verification",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="List of source citations/URLs for this bullet (empty if none)",
    )


class LayoutHints(BaseModel):
    """Layout guidance for slide rendering."""
    style: str = Field(
        default="bullets",
        description="Slide style: bullets, two_column, table, etc.",
    )
    max_bullets: int = Field(
        default=4,
        description="Maximum number of bullets allowed",
        ge=1,
        le=6,
    )
    suggested_visual: Optional[str] = Field(
        None,
        description="Suggested visual element (chart, timeline, etc.)",
    )


class SlideFlags(BaseModel):
    """Flags for slide content validation."""
    needs_sources: bool = Field(
        default=False,
        description="Whether slide contains claims needing sources",
    )
    contains_numbers: bool = Field(
        default=False,
        description="Whether slide contains numeric claims",
    )
    is_draft: bool = Field(
        default=False,
        description="Whether content is draft requiring review",
    )


class Slide(BaseModel):
    """Single slide in a deck section."""
    slide_id: str = Field(..., description="Unique slide identifier")
    title: str = Field(..., description="Slide title", max_length=200)
    bullets: list[BulletPoint] = Field(
        ...,
        description="Bullet points (max 4)",
        max_length=4,
    )
    speaker_notes: str = Field(
        default="",
        description="Presenter notes for this slide",
        max_length=5000,
    )
    layout_hints: LayoutHints = Field(default_factory=LayoutHints)
    flags: SlideFlags = Field(default_factory=SlideFlags)

    @field_validator("bullets", mode="after")
    @classmethod
    def validate_bullets_count(cls, v: list[BulletPoint]) -> list[BulletPoint]:
        if len(v) > 4:
            raise ValueError("Maximum 4 bullets per slide")
        return v


class SectionResult(BaseModel):
    """Result for a single deck section."""
    section_id: str = Field(..., description="Section identifier")
    section_name: str = Field(..., description="Human-readable section name")
    slides: list[Slide] = Field(..., description="Generated slides")
    needs_verification: bool = Field(
        default=False,
        description="Whether section requires fact verification",
    )
    verification_notes: list[str] = Field(
        default_factory=list,
        description="Specific items requiring verification",
    )
    citations: list[str] = Field(
        default_factory=list,
        description="Collected citations/sources for this section (empty by default)",
    )
    generation_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Generation stats and debugging info",
    )


class ProviderInfo(BaseModel):
    """Information about the LLM provider used."""
    provider: str
    model: str
    reasoning_level: str


class ComputedInputs(BaseModel):
    """Computed inputs used for generation."""
    comps_table: Optional[dict[str, Any]] = Field(
        None,
        description="Comparables table from yfinance",
    )
    dcf_valuation: Optional[dict[str, Any]] = Field(
        None,
        description="DCF valuation breakdown (deterministic, from yfinance data)",
    )


class GenerationError(BaseModel):
    """Error information for failed generations."""
    section_id: str
    error_type: str
    message: str
    retries_attempted: int = 0


class DeckGenerateResponse(BaseModel):
    """Response schema for POST /api/v1/deck/generate."""
    ticker: str
    company_name: str = Field(..., description="Company name for the ticker")
    plan_tier: Optional[PlanTier] = None
    model_mode: Optional[ModelMode] = None
    analysis_depth: Optional[AnalysisDepth] = None
    provider_used: ProviderInfo
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    computed_inputs: ComputedInputs = Field(default_factory=ComputedInputs)
    results: list[SectionResult] = Field(default_factory=list)
    errors: list[GenerationError] = Field(default_factory=list)
    request_id: str = Field(..., description="Unique request identifier for tracing")


class ClaudeExportFormat(str, Enum):
    """Supported Claude Skills export formats."""
    PPTX = "pptx"
    PDF = "pdf"
    BOTH = "both"


class DeckClaudeExportRequest(BaseModel):
    """Request schema for Claude Skills-powered deck export."""
    deck: dict[str, Any] = Field(
        ...,
        description="Canonical DeckGenerateResponse JSON, or compatible saved draft content.",
    )
    export_format: ClaudeExportFormat = Field(
        default=ClaudeExportFormat.PPTX,
        description="Document format to generate.",
    )
    title: Optional[str] = Field(
        None,
        description="Optional export title used for the generated filename and cover slide.",
        max_length=200,
    )

    @model_validator(mode="after")
    def validate_deck_payload(self) -> "DeckClaudeExportRequest":
        sections = self.deck.get("results") or self.deck.get("sections") or []
        if not isinstance(sections, list) or not sections:
            raise ValueError("deck must include a non-empty results or sections array")

        slide_count = 0
        for section in sections:
            if not isinstance(section, dict):
                raise ValueError("each deck section must be an object")
            slides = section.get("slides") or []
            if not isinstance(slides, list):
                raise ValueError("each deck section must include a slides array")
            slide_count += len(slides)

        if slide_count <= 0:
            raise ValueError("deck must include at least one slide")

        return self


# =============================================================================
# Section List Response
# =============================================================================

class SectionInfo(BaseModel):
    """Information about an available section."""
    id: str
    label: str
    description: Optional[str] = None
    default: bool = Field(default=True, description="Whether this section is selected by default")
    requires_user_input: bool = Field(
        default=False,
        description="Whether this section needs user-provided data to generate",
    )


class SectionsResponse(BaseModel):
    """Response schema for GET /api/v1/sections."""
    sections: list[SectionInfo]


# =============================================================================
# Plan Response
# =============================================================================

class SuggestedSection(BaseModel):
    """A suggested section with ordering and rationale."""
    id: str
    label: str
    priority: int = Field(..., description="Suggested order priority (1=first)")
    rationale: str = Field(..., description="Why this section is suggested")
    estimated_slides: int = Field(default=2, ge=1, le=3)


class DeckPlanResponse(BaseModel):
    """Response schema for POST /api/v1/deck/plan."""
    ticker: str
    company_name: str
    suggested_sections: list[SuggestedSection]
    recommended_order: list[str] = Field(
        ...,
        description="Section IDs in recommended order",
    )
    notes: str = Field(
        default="",
        description="Additional planning notes",
    )
    request_id: str


# =============================================================================
# JSON Schema Definitions (for LLM output validation)
# =============================================================================

SLIDE_JSON_SCHEMA = {
    "type": "object",
    "required": ["slide_id", "title", "bullets"],
    "properties": {
        "slide_id": {"type": "string"},
        "title": {"type": "string", "maxLength": 200},
        "bullets": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text"],
                "properties": {
                    "text": {"type": "string", "maxLength": 500},
                    "source_needed": {"type": "boolean", "default": False},
                },
            },
            "maxItems": 4,
        },
        "speaker_notes": {"type": "string", "maxLength": 2000, "default": ""},
        "layout_hints": {
            "type": "object",
            "properties": {
                "style": {"type": "string", "default": "bullets"},
                "max_bullets": {"type": "integer", "default": 4, "minimum": 1, "maximum": 6},
                "suggested_visual": {"type": ["string", "null"]},
            },
        },
        "flags": {
            "type": "object",
            "properties": {
                "needs_sources": {"type": "boolean", "default": False},
                "contains_numbers": {"type": "boolean", "default": False},
                "is_draft": {"type": "boolean", "default": False},
            },
        },
    },
}

SECTION_OUTPUT_SCHEMA = {
    "type": "object",
    "required": ["section_id", "slides"],
    "properties": {
        "section_id": {"type": "string"},
        "slides": {
            "type": "array",
            "items": SLIDE_JSON_SCHEMA,
            "minItems": 1,
            "maxItems": 3,
        },
        "needs_verification": {"type": "boolean", "default": False},
        "verification_notes": {
            "type": "array",
            "items": {"type": "string"},
            "default": [],
        },
    },
}


def get_section_schema(section_id: str) -> dict:
    """Get the JSON schema for a specific section's output."""
    schema = SECTION_OUTPUT_SCHEMA.copy()
    schema = dict(schema)
    schema["properties"] = dict(schema["properties"])
    
    # Customize based on section
    if section_id == SectionId.HISTORY.value:
        schema["required"] = ["section_id", "slides", "needs_verification", "verification_notes"]
        schema["properties"]["needs_verification"] = {"type": "boolean", "const": True}
    elif section_id == SectionId.COMPANY_SNAPSHOT.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.BUSINESS_MODEL_SEGMENTS.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.INDUSTRY_COMPETITIVE_LANDSCAPE.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.HISTORICAL_PERFORMANCE_CURRENT_SETUP.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.MANAGEMENT_OWNERSHIP_GOVERNANCE.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.CAPITAL_STRUCTURE_FINANCIAL_HEALTH.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.KEY_DRIVERS_KPIS.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.SECTOR_INVARIANTS.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.INVESTMENT_THESIS.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.CATALYSTS_TIMELINE.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.VALUATION.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.INVESTMENT_THESIS_VARIANT_VIEW.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.RISKS_UNDERWRITING.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.VALUATION_SUMMARY.value:
        schema["properties"]["slides"]["maxItems"] = 2

    return schema


def get_section_metadata(section_id: str) -> dict[str, Any]:
    """Get section metadata by string ID."""
    try:
        return SECTION_METADATA[SectionId(section_id)]
    except ValueError:
        return {}
