"""
Pydantic models for the SWOT section output.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class SwotItem(BaseModel):
    point: str
    justification: str


class SWOTOutput(BaseModel):
    """Top-level LLM output for the swot section."""
    strengths: list[SwotItem] = Field(..., min_length=2, max_length=4)
    weaknesses: list[SwotItem] = Field(..., min_length=2, max_length=4)
    opportunities: list[SwotItem] = Field(..., min_length=2, max_length=4)
    threats: list[SwotItem] = Field(..., min_length=2, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


def get_swot_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return SWOTOutput.model_json_schema()


def get_swot_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_swot_json_schema(), indent=2)
