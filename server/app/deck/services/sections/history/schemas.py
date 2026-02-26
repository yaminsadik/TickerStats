"""
Pydantic models for the History section output.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class MilestoneItem(BaseModel):
    year: Optional[str] = None  # Can be "early 2010s" or "2015"
    event: str
    why_it_matters: str
    needs_verification: bool = True


class HistoryOutput(BaseModel):
    """Top-level LLM output for the history section."""
    milestones: list[MilestoneItem] = Field(..., min_length=4, max_length=8)
    confidence: Confidence
    notes: Optional[str] = None
    verification_items: list[str] = Field(..., min_length=1)


def get_history_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return HistoryOutput.model_json_schema()


def get_history_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_history_json_schema(), indent=2)
