"""
Pydantic models for the Risks & Underwriting section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Type aliases ─────────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]
QualRank = Literal["high", "medium", "low", "not_provided"]


# ── Risk item ────────────────────────────────────────────────────────────────

class RiskOut(BaseModel):
    """A single risk in the output register."""
    risk: str
    impact: QualRank = "not_provided"
    probability: QualRank = "not_provided"
    leading_indicator: Optional[str] = None
    mitigant: Optional[str] = None
    rank_score: int = Field(default=0, description="Deterministic score for ordering")
    confidence: Confidence = "low"
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────

class RisksUnderwritingOutput(BaseModel):
    """Top-level LLM output for the risks_underwriting section."""
    ticker: str
    risks: list[RiskOut] = Field(default_factory=list, max_length=8)
    break_thesis_line: Optional[str] = None
    confidence: Confidence = "low"
    low_confidence_flag: bool = True
    notes: Optional[str] = None


# ── JSON schema for LLM structured-output instructions ──────────────────────

def get_risks_underwriting_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return RisksUnderwritingOutput.model_json_schema()


def get_risks_underwriting_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_risks_underwriting_json_schema(), indent=2)
