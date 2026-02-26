"""JSON schema and Pydantic model for Investment Thesis output."""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class InvestmentThesisOutput(BaseModel):
    """Structured LLM output for the Investment Thesis section."""

    thesis_sentence: Optional[str] = Field(
        None,
        description="One-sentence thesis: why the market is wrong and what reprices it",
    )
    market_view: Optional[str] = Field(
        None,
        description="What consensus / the market currently believes",
    )
    variant_view: Optional[str] = Field(
        None,
        description="User's (or analyst's) contrarian view",
    )
    pillars: list[str] = Field(
        default_factory=list,
        description="2-5 supporting thesis pillars",
    )
    what_changes_mind: list[str] = Field(
        default_factory=list,
        description="1-2 conditions that would invalidate the thesis",
    )
    confidence: Confidence = "medium"


def get_investment_thesis_json_schema() -> dict:
    """Return JSON schema dict for LLM output validation."""
    return {
        "type": "object",
        "required": ["thesis_sentence", "pillars"],
        "properties": {
            "thesis_sentence": {"type": ["string", "null"]},
            "market_view": {"type": ["string", "null"]},
            "variant_view": {"type": ["string", "null"]},
            "pillars": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5,
            },
            "what_changes_mind": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 2,
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "default": "medium",
            },
        },
    }


def get_investment_thesis_json_schema_str() -> str:
    return json.dumps(get_investment_thesis_json_schema(), indent=2)
