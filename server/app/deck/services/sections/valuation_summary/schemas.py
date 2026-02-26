"""Pydantic models and JSON schema for Valuation Summary section output."""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]
TrustMode = Literal["user_only", "user_auto_fetch", "narrative_only"]


class MethodSummary(BaseModel):
    """Summary of a single valuation method."""

    method: str = Field(..., description="Method name, e.g. DCF, Relative, SOTP")
    provided_inputs: list[str] = Field(
        default_factory=list,
        description="Input keys the user provided for this method",
    )
    notes: Optional[str] = None


class DcfResultOut(BaseModel):
    """Deterministic DCF output block."""

    included: bool = False
    value_per_share: Optional[str] = None
    upside_downside: Optional[str] = None
    key_assumptions: list[str] = Field(default_factory=list, max_length=5)
    source_note: Optional[str] = None
    notes: Optional[str] = None


class ValuationSummaryOutput(BaseModel):
    """Top-level structured output for the Valuation Summary section."""

    ticker: str
    trust_mode: TrustMode
    methods: list[MethodSummary] = Field(default_factory=list)
    peer_set: list[str] = Field(default_factory=list, max_length=10)
    user_targets: list[str] = Field(default_factory=list, max_length=3)
    dcf: DcfResultOut = Field(default_factory=DcfResultOut)
    sensitivities: list[str] = Field(default_factory=list, min_length=2, max_length=3)
    confidence: Confidence = "low"
    low_confidence_flag: bool = False
    notes: Optional[str] = None


def get_valuation_summary_json_schema() -> dict:
    """Return JSON schema dict for LLM output validation.

    This section is deterministic (Option A), so the schema is permissive.
    The actual validation happens in postprocess via Pydantic.
    """
    return {"type": "object"}


def get_valuation_summary_json_schema_str() -> str:
    """Return JSON schema as a formatted string for prompt embedding."""
    return json.dumps(get_valuation_summary_json_schema(), indent=2)
