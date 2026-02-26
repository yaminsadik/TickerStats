"""
Pydantic models for the Business Model & Segments section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Enums / Literals ─────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]
SegmentsMode = Literal["tier_a", "tier_b", "tier_c"]
ProfitBasis = Literal[
    "ebit", "ebitda", "operating_income", "gross_profit", "net_income"
]


# ── Leaf value types ─────────────────────────────────────────────────────────


class FlowStep(BaseModel):
    """A single step in the revenue-generation flow."""
    step: str = Field(..., description="Short description of the flow step")
    note: Optional[str] = Field(
        None, description="Optional clarifying note for this step"
    )


class SegmentItem(BaseModel):
    name: str
    revenue_mix_pct: Optional[float] = None
    profit_mix_pct: Optional[float] = None
    profit_basis: Optional[ProfitBasis] = None
    one_liner: str
    drivers: list[str] = Field(..., min_length=2, max_length=4)


class UnitMetric(BaseModel):
    label: str
    value: str
    as_of: Optional[str] = None


# ── Module outputs ───────────────────────────────────────────────────────────


class BusinessModelOut(BaseModel):
    what_they_sell: list[str] = Field(..., min_length=2, max_length=5)
    who_they_sell_to: list[str] = Field(..., min_length=2, max_length=5)
    revenue_flow: list[FlowStep] = Field(..., min_length=4, max_length=6)
    pricing_contract_notes: list[str] = Field(
        default_factory=list, min_length=0, max_length=3
    )
    confidence: Confidence
    notes: Optional[str] = None


class SegmentsOut(BaseModel):
    mode: SegmentsMode
    items: list[SegmentItem] = Field(..., min_length=2, max_length=6)
    confidence: Confidence
    notes: Optional[str] = None


class UnitEconomicsOut(BaseModel):
    applicable: bool
    metrics: list[UnitMetric] = Field(
        default_factory=list, min_length=0, max_length=6
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────


class BusinessModelSegmentsOutput(BaseModel):
    """Top-level LLM output for the business_model_segments section."""
    business_model: BusinessModelOut
    segments: SegmentsOut
    unit_economics: UnitEconomicsOut
    low_confidence_flag: bool = False


# ── JSON schema for LLM structured-output instructions ──────────────────────


def get_business_model_segments_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return BusinessModelSegmentsOutput.model_json_schema()


def get_business_model_segments_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_business_model_segments_json_schema(), indent=2)
