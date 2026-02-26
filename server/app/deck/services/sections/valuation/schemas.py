"""JSON schema and Pydantic model for Valuation output."""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class ValuationPoint(BaseModel):
    """A single valuation method / approach result."""

    method: str = Field(..., description="Valuation method name")
    description: str = Field(..., description="Brief description of approach and result")
    implied_range: Optional[str] = Field(
        None, description="Implied value range (e.g., '$150-$170')",
    )


class ValuationOutput(BaseModel):
    """Structured LLM output for the Valuation section."""

    methodology_summary: Optional[str] = Field(
        None,
        description="One-sentence summary of the valuation approach",
    )
    valuation_points: list[ValuationPoint] = Field(
        default_factory=list,
        description="Individual valuation method results",
    )
    price_target_summary: Optional[str] = Field(
        None,
        description="Synthesised price target or range with rationale",
    )
    confidence: Confidence = "medium"


def get_valuation_json_schema() -> dict:
    """Return JSON schema dict for LLM output validation."""
    return {
        "type": "object",
        "required": ["valuation_points"],
        "properties": {
            "methodology_summary": {"type": ["string", "null"]},
            "valuation_points": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["method", "description"],
                    "properties": {
                        "method": {"type": "string"},
                        "description": {"type": "string"},
                        "implied_range": {"type": ["string", "null"]},
                    },
                },
                "minItems": 1,
                "maxItems": 6,
            },
            "price_target_summary": {"type": ["string", "null"]},
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "default": "medium",
            },
        },
    }


def get_valuation_json_schema_str() -> str:
    return json.dumps(get_valuation_json_schema(), indent=2)
