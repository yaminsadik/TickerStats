"""
Pydantic models for the Historical Performance & Current Setup section output.

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

Period = Literal["fy-5", "fy-4", "fy-3", "fy-2", "fy-1", "ttm", "fy0"]

MetricId = Literal[
    "revenue",
    "gross_margin",
    "operating_margin",
    "ebitda_margin",
    "fcf",
    "fcf_conversion",
    "roic",
    "roe",
    "sector_proxy",
]

SetupMode = Literal["price_vs_benchmark", "valuation_rerating", "both"]

EventType = Literal[
    "earnings",
    "guidance",
    "mna",
    "macro",
    "regulatory",
    "product",
    "pricing",
    "cycle",
    "capital_allocation",
    "other",
]


# ── Fundamentals ─────────────────────────────────────────────────────────────


class SeriesPoint(BaseModel):
    period: Period
    value: Optional[float] = None


class MetricSeries(BaseModel):
    metric: MetricId
    label: str
    unit: str
    points: list[SeriesPoint] = Field(..., min_length=3, max_length=7)


class FundamentalsOut(BaseModel):
    window_years: int = Field(..., ge=3, le=5)
    series: list[MetricSeries] = Field(default_factory=list)
    highlights: list[str] = Field(..., min_length=3, max_length=6)
    confidence: Confidence
    notes: Optional[str] = None


# ── Stock vs Benchmark ───────────────────────────────────────────────────────


class PricePoint(BaseModel):
    date: str
    value: float


class PriceSeries(BaseModel):
    name: str
    points: list[PricePoint] = Field(default_factory=list)


class StockOut(BaseModel):
    benchmark_name: Optional[str] = None
    series: list[PriceSeries] = Field(default_factory=list, max_length=2)
    takeaways: list[str] = Field(default_factory=list, min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


# ── Valuation Rerating ───────────────────────────────────────────────────────


class MultiplePoint(BaseModel):
    date: Optional[str] = None
    period: Optional[Period] = None
    value: Optional[float] = None


class MultipleSeries(BaseModel):
    multiple_name: str
    points: list[MultiplePoint] = Field(default_factory=list)


class ReratingOut(BaseModel):
    current_vs_median: list[str] = Field(
        default_factory=list, max_length=3,
    )
    peer_context: list[str] = Field(
        default_factory=list, max_length=3,
    )
    series: list[MultipleSeries] = Field(default_factory=list, max_length=2)
    takeaways: list[str] = Field(default_factory=list, min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


# ── What Changed ─────────────────────────────────────────────────────────────


class RecentEvent(BaseModel):
    date: Optional[str] = None
    type: EventType
    headline: str
    why_it_matters: str
    sentiment_effect: Literal["positive", "negative", "mixed", "unclear"]
    evidence: Optional[str] = None


class WhatChangedOut(BaseModel):
    events: list[RecentEvent] = Field(default_factory=list, max_length=6)
    current_sentiment_summary: str
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────


class HistoricalPerfCurrentSetupOutput(BaseModel):
    """Top-level LLM output for the historical_performance_current_setup section."""
    setup_mode: SetupMode
    fundamentals: FundamentalsOut
    stock: StockOut
    rerating: ReratingOut
    what_changed: WhatChangedOut
    low_confidence_flag: bool = False


# ── JSON schema for LLM structured-output instructions ──────────────────────


def get_hpcs_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return HistoricalPerfCurrentSetupOutput.model_json_schema()


def get_hpcs_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_hpcs_json_schema(), indent=2)
