"""
JSON Schemas and Pydantic models for deck generation API.
Defines request/response structures and validation rules.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# =============================================================================
# Enums
# =============================================================================

class Provider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
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


class SectionId(str, Enum):
    """Valid deck section identifiers."""
    OVERVIEW = "overview"
    HISTORY = "history"
    SWOT = "swot"
    PORTERS_FIVE = "porters_five"
    BULL_CASE = "bull_case"
    BEAR_CASE = "bear_case"
    RELATIVE_HEATMAP = "relative_heatmap"
    VALUATION = "valuation"
    REBUTTALS = "rebuttals"
    LAYOUT = "layout"


# =============================================================================
# Section Metadata
# =============================================================================

SECTION_METADATA = {
    SectionId.OVERVIEW: {
        "id": "overview",
        "label": "Company Overview + Catalysts",
        "description": "What the business does, segments, 'why now', and catalysts",
        "min_slides": 1,
        "max_slides": 3,
    },
    SectionId.HISTORY: {
        "id": "history",
        "label": "History Timeline (Draft)",
        "description": "Key milestones, founding, IPO, major acquisitions (requires verification)",
        "min_slides": 1,
        "max_slides": 2,
        "requires_verification": True,
    },
    SectionId.SWOT: {
        "id": "swot",
        "label": "SWOT",
        "description": "Strengths, Weaknesses, Opportunities, Threats with bullet justification",
        "min_slides": 1,
        "max_slides": 3,
    },
    SectionId.PORTERS_FIVE: {
        "id": "porters_five",
        "label": "Porter's Five Forces",
        "description": "Category-level competitive analysis and rationale",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.BULL_CASE: {
        "id": "bull_case",
        "label": "Bull Case",
        "description": "Upside scenario with growth catalysts, multiple expansion, and price target",
        "min_slides": 2,
        "max_slides": 3,
    },
    SectionId.BEAR_CASE: {
        "id": "bear_case",
        "label": "Bear Case",
        "description": "Downside risks, margin compression scenarios, and bear price target",
        "min_slides": 2,
        "max_slides": 3,
    },
    SectionId.RELATIVE_HEATMAP: {
        "id": "relative_heatmap",
        "label": "Relative Valuation",
        "description": "Comparative metrics table showing target vs peers across key fundamentals",
        "min_slides": 1,
        "max_slides": 1,
        "requires_comps": True,
    },
    SectionId.VALUATION: {
        "id": "valuation",
        "label": "DCF Valuation",
        "description": "Deterministic DCF target price calculation with full breakdown",
        "min_slides": 1,
        "max_slides": 2,
        "requires_dcf": True,
    },
    SectionId.REBUTTALS: {
        "id": "rebuttals",
        "label": "Rebuttals / Q&A",
        "description": "Common objections and responses for Q&A preparation",
        "min_slides": 1,
        "max_slides": 2,
    },
    SectionId.LAYOUT: {
        "id": "layout",
        "label": "Layout Decisions",
        "description": "Slide layout guidance, structure, bullet limits, presenter notes",
        "min_slides": 1,
        "max_slides": 1,
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
        default=Provider.OPENAI,
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
        max_length=2000,
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
        default_factory=lambda: datetime.utcnow().isoformat() + "Z",
    )
    computed_inputs: ComputedInputs = Field(default_factory=ComputedInputs)
    results: list[SectionResult] = Field(default_factory=list)
    errors: list[GenerationError] = Field(default_factory=list)
    request_id: str = Field(..., description="Unique request identifier for tracing")


# =============================================================================
# Section List Response
# =============================================================================

class SectionInfo(BaseModel):
    """Information about an available section."""
    id: str
    label: str
    description: Optional[str] = None


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
    elif section_id == SectionId.REBUTTALS.value:
        schema["properties"]["slides"]["maxItems"] = 2
    elif section_id == SectionId.BULL_CASE.value:
        schema["properties"]["slides"]["maxItems"] = 3
    elif section_id == SectionId.BEAR_CASE.value:
        schema["properties"]["slides"]["maxItems"] = 3
    
    return schema
