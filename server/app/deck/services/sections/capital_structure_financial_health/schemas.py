"""
Pydantic models for the Capital Structure & Financial Health section output.

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

CovenantType = Literal["leverage", "interest_coverage", "fixed_charge", "other"]


# ── Leverage & Interest ──────────────────────────────────────────────────────


class LeveragePoint(BaseModel):
    """A single observation of net-debt/EBITDA for a period (e.g. 'FY2021', 'TTM')."""
    period: str
    net_debt_to_ebitda: Optional[float] = None


class InterestMetric(BaseModel):
    """A labelled interest-burden metric (e.g. 'Interest coverage', 'Net interest / EBITDA')."""
    label: str
    value: str
    as_of: Optional[str] = None


class LeverageOut(BaseModel):
    leverage_series: list[LeveragePoint] = Field(default_factory=list, max_length=8)
    current_net_debt_to_ebitda: Optional[float] = None
    interest_metrics: list[InterestMetric] = Field(default_factory=list, max_length=3)
    takeaways: list[str] = Field(default_factory=list, min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


# ── Maturities & Covenants ───────────────────────────────────────────────────


class DebtMaturity(BaseModel):
    """A single maturity bucket (e.g. year or year-range)."""
    year_bucket: str
    amount: Optional[str] = None        # string like "$1.2B"
    instrument: Optional[str] = None


class Covenant(BaseModel):
    """A debt covenant (only if explicitly provided)."""
    type: CovenantType
    description: str
    headroom: Optional[str] = None      # only if provided in source data


class MaturitiesOut(BaseModel):
    ladder: list[DebtMaturity] = Field(default_factory=list, max_length=10)
    covenants: list[Covenant] = Field(default_factory=list, max_length=3)
    takeaways: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    confidence: Confidence
    notes: Optional[str] = None


# ── Liquidity ────────────────────────────────────────────────────────────────


class LiquidityMetric(BaseModel):
    """Cash, revolver availability, net liquidity, etc."""
    label: str
    value: str
    as_of: Optional[str] = None


class Runway(BaseModel):
    """Cash runway estimate — ONLY if burn rate is provided as a number."""
    basis: str          # e.g. "Based on FY burn rate"
    estimate: str       # e.g. "≈18 months"


class LiquidityOut(BaseModel):
    metrics: list[LiquidityMetric] = Field(default_factory=list, max_length=5)
    runway: Optional[Runway] = None
    takeaways: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    confidence: Confidence
    notes: Optional[str] = None


# ── Share Count ──────────────────────────────────────────────────────────────


class SharePoint(BaseModel):
    """Diluted share count for a period."""
    period: str
    diluted_shares: Optional[float] = None


class ShareCountOut(BaseModel):
    share_series: list[SharePoint] = Field(default_factory=list, max_length=8)
    buybacks: list[str] = Field(default_factory=list, max_length=3)
    dividends: list[str] = Field(default_factory=list, max_length=2)
    sbc_dilution: list[str] = Field(default_factory=list, max_length=2)
    takeaways: list[str] = Field(default_factory=list, min_length=1, max_length=3)
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────


class CapitalStructureFinancialHealthOutput(BaseModel):
    """Top-level LLM output for the capital_structure_financial_health section."""
    leverage_interest: LeverageOut
    maturities: MaturitiesOut
    liquidity: LiquidityOut
    share_count: ShareCountOut
    low_confidence_flag: bool = False


# ── JSON schema for LLM structured-output instructions ──────────────────────


def get_csfh_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return CapitalStructureFinancialHealthOutput.model_json_schema()


def get_csfh_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_csfh_json_schema(), indent=2)
