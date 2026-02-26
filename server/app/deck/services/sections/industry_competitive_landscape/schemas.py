"""
Pydantic models for the Industry & Competitive Landscape section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Shared literals ──────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]
Pressure = Literal["low", "medium", "high"]


# ── Market ───────────────────────────────────────────────────────────────────

class MarketSizing(BaseModel):
    tam_value: Optional[str] = Field(
        None,
        description='String like "$220B" only if grounded/disclosed',
    )
    tam_basis: Optional[str] = Field(
        None,
        description="What the TAM represents (e.g. global language learning)",
    )
    proxy_sizing: list[str] = Field(
        default_factory=list,
        description="0–3 proxy sizing bullets when TAM is unavailable",
        max_length=3,
    )
    growth_chart_notes: list[str] = Field(
        default_factory=list,
        description="0–3 CAGR / growth statements only if grounded",
        max_length=3,
    )


class MarketOut(BaseModel):
    market_definition: str = Field(
        ..., description="1–2 sentence market definition"
    )
    sizing: MarketSizing = Field(default_factory=MarketSizing)
    growth_drivers: list[str] = Field(
        ...,
        description="2–5 growth drivers",
        min_length=2,
        max_length=5,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Competition ──────────────────────────────────────────────────────────────

class Competitor(BaseModel):
    name: str
    type: Literal["direct", "adjacent", "substitute"]
    why_relevant: str


class PositioningAxis(BaseModel):
    x_label: str
    y_label: str
    company_position: str
    key_differentiator: str


class CompetitionOut(BaseModel):
    competitors: list[Competitor] = Field(
        ...,
        description="3–8 competitors",
        min_length=3,
        max_length=8,
    )
    positioning: PositioningAxis
    confidence: Confidence
    notes: Optional[str] = None


# ── Moat ─────────────────────────────────────────────────────────────────────

class MoatPillar(BaseModel):
    pillar: str
    mechanism: str
    evidence: Optional[str] = None


class MoatOut(BaseModel):
    pillars: list[MoatPillar] = Field(
        ...,
        description="3–5 moat pillars",
        min_length=3,
        max_length=5,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Porter's Five Forces ─────────────────────────────────────────────────────

class ForceOut(BaseModel):
    force: str
    pressure: Pressure
    because: list[str] = Field(
        ...,
        description="1–2 grounded justification bullets",
        min_length=1,
        max_length=2,
    )
    evidence: Optional[str] = None


class PortersOut(BaseModel):
    forces: list[ForceOut] = Field(
        ...,
        description="Exactly 5 Porter's forces",
        min_length=5,
        max_length=5,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level aggregate ──────────────────────────────────────────────────────

class IndustryCompetitiveOutput(BaseModel):
    """Top-level LLM output for the industry_competitive_landscape section."""

    market: MarketOut
    competition: CompetitionOut
    moat: MoatOut
    porters: PortersOut
    low_confidence_flag: bool = False


# ── JSON schema helpers for prompt embedding ─────────────────────────────────

def get_industry_competitive_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return IndustryCompetitiveOutput.model_json_schema()


def get_industry_competitive_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_industry_competitive_json_schema(), indent=2)
