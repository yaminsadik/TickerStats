"""
Pydantic models for the Overview section output.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class BusinessDescModule(BaseModel):
    core_value_proposition: str
    what_they_do: list[str] = Field(..., min_length=2, max_length=4)
    who_they_serve: list[str] = Field(..., min_length=1, max_length=3)
    confidence: Confidence
    notes: Optional[str] = None


class WhyNowModule(BaseModel):
    thesis_statement: str
    timing_factors: list[str] = Field(..., min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


class CatalystsModule(BaseModel):
    near_term: list[str] = Field(..., min_length=2, max_length=4)
    medium_term: list[str] = Field(default_factory=list, max_length=3)
    confidence: Confidence
    notes: Optional[str] = None


class OverviewOutput(BaseModel):
    """Top-level LLM output for the overview section."""
    business_description: BusinessDescModule
    why_now: WhyNowModule
    catalysts: CatalystsModule
    low_confidence_flag: bool = False


def get_overview_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return OverviewOutput.model_json_schema()


def get_overview_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_overview_json_schema(), indent=2)
