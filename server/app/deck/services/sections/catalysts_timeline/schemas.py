"""JSON schema and Pydantic model for Catalysts & Timeline output."""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


Confidence = Literal["high", "medium", "low"]


class CatalystItem(BaseModel):
    """A single catalyst in the LLM output."""

    name: str = Field(..., description="Catalyst name")
    timing: Optional[str] = Field(None, description="Expected timing window")
    mechanism: Optional[str] = Field(None, description="What changes and why market reacts")
    impact_description: Optional[str] = Field(None, description="Expected market impact")


class CatalystsTimelineOutput(BaseModel):
    """Structured LLM output for the Catalysts & Timeline section."""

    catalysts: list[CatalystItem] = Field(
        default_factory=list,
        description="Ordered list of catalysts",
    )
    confidence: Confidence = "medium"


def get_catalysts_timeline_json_schema() -> dict:
    """Return JSON schema dict for LLM output validation."""
    return {
        "type": "object",
        "required": ["catalysts"],
        "properties": {
            "catalysts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string"},
                        "timing": {"type": ["string", "null"]},
                        "mechanism": {"type": ["string", "null"]},
                        "impact_description": {"type": ["string", "null"]},
                    },
                },
                "minItems": 1,
                "maxItems": 8,
            },
            "confidence": {
                "type": "string",
                "enum": ["high", "medium", "low"],
                "default": "medium",
            },
        },
    }


def get_catalysts_timeline_json_schema_str() -> str:
    return json.dumps(get_catalysts_timeline_json_schema(), indent=2)
