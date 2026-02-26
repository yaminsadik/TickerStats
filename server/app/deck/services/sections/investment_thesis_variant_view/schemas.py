"""
Pydantic models for the Investment Thesis Variant View section output.

Defines the LLM output schema. After generation, ``spec.postprocess`` converts
this into the standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]
Position = Literal["long", "short", "not_specified"]


class ThesisHeader(BaseModel):
    ticker: str
    company_name: Optional[str] = None
    position: Position = "not_specified"
    time_horizon: Optional[str] = None


class VariantDelta(BaseModel):
    market_believes: str
    we_believe: str


class InvestmentThesisVariantViewOutput(BaseModel):
    """Top-level LLM output for the investment_thesis_variant_view section."""

    header: ThesisHeader
    thesis_sentence: Optional[str] = Field(
        None,
        description="One-sentence thesis edge — preserve user meaning, allow light polish",
    )
    thesis_pillars: list[str] = Field(
        default_factory=list,
        description="2-5 thesis pillars supporting the view",
    )
    variant_deltas: list[VariantDelta] = Field(
        default_factory=list,
        description="1-3 market-vs-us deltas",
    )
    key_debates: list[str] = Field(
        default_factory=list,
        description="0-3 key debates derived ONLY from user text",
    )
    flip_conditions: list[str] = Field(
        default_factory=list,
        description="0-2 conditions that would invalidate the thesis",
    )
    confidence: Confidence = "medium"
    low_confidence_flag: bool = False
    notes: Optional[str] = None


def get_investment_thesis_variant_view_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return InvestmentThesisVariantViewOutput.model_json_schema()


def get_investment_thesis_variant_view_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_investment_thesis_variant_view_json_schema(), indent=2)
