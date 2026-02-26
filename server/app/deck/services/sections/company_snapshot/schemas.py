"""
Pydantic models for the Company Snapshot section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Confidence literal ───────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]


# ── Leaf value types ─────────────────────────────────────────────────────────

class QuickStat(BaseModel):
    label: str
    value: str
    as_of: Optional[str] = None


class SegmentItem(BaseModel):
    name: str
    mix_pct: Optional[float] = None
    one_liner: str


class KpiItem(BaseModel):
    label: str
    value: str
    as_of: Optional[str] = None


# ── Header ───────────────────────────────────────────────────────────────────

class SnapshotHeader(BaseModel):
    company_name: str
    ticker: str
    sector: Optional[str] = None
    industry: Optional[str] = None
    positioning_sentence: str
    quick_stats: list[QuickStat] = Field(default_factory=list, max_length=6)
    low_confidence_flag: bool = False


# ── Modules ──────────────────────────────────────────────────────────────────

class PositioningModule(BaseModel):
    bullets: list[str] = Field(..., min_length=3, max_length=6)
    confidence: Confidence
    notes: Optional[str] = None


class SegmentsModule(BaseModel):
    mode: Literal["tier_a", "tier_b", "tier_c"]
    mix_basis: Optional[Literal["revenue", "ebitda"]] = None
    items: list[SegmentItem] = Field(default_factory=list)
    confidence: Confidence
    notes: Optional[str] = None


class MoneyModelModule(BaseModel):
    pricing_unit: str
    contract_structure: str
    recurrence: str
    cost_drivers: list[str] = Field(..., min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


class CustomersModule(BaseModel):
    types: list[str] = Field(..., min_length=2, max_length=5)
    concentration: str
    credit_quality: Optional[str] = None
    confidence: Confidence
    notes: Optional[str] = None


class FootprintModule(BaseModel):
    regions: list[str] = Field(..., min_length=1, max_length=5)
    why_it_matters: Optional[str] = None
    confidence: Confidence
    notes: Optional[str] = None


class ProofPointsModule(BaseModel):
    kpis: list[KpiItem] = Field(..., min_length=3, max_length=6)
    confidence: Confidence
    notes: Optional[str] = None


# ── Aggregate ────────────────────────────────────────────────────────────────

class ModulesOutput(BaseModel):
    positioning: PositioningModule
    segments: SegmentsModule
    money_model: MoneyModelModule
    customers: CustomersModule
    footprint: FootprintModule
    proof_points: ProofPointsModule


class CompanySnapshotOutput(BaseModel):
    """Top-level LLM output for the company_snapshot section."""
    header: SnapshotHeader
    modules: ModulesOutput


# ── JSON schema for LLM structured-output instructions ──────────────────────

def get_company_snapshot_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return CompanySnapshotOutput.model_json_schema()


def get_company_snapshot_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_company_snapshot_json_schema(), indent=2)
