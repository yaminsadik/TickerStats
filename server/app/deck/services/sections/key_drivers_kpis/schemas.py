"""
Pydantic models for the Key Drivers & KPIs section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ── Enums / Literals ─────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]

SourceType = Literal[
    "10-K",
    "10-Q",
    "earnings_release",
    "earnings_deck",
    "investor_presentation",
    "other",
    "not_provided",
]


# ── Leaf models ──────────────────────────────────────────────────────────────

class DisclosureRef(BaseModel):
    """Where a KPI appears in filings / investor materials."""
    source_type: SourceType
    description: Optional[str] = Field(
        None,
        description="e.g. 'MD&A, Business Overview', 'Quarterly press release'",
    )
    page_or_section: Optional[str] = Field(
        None,
        description="Only if explicitly provided in inputs",
    )
    link_label: Optional[str] = Field(
        None,
        description="Optional label for a hyperlink, if supported",
    )


class KPI(BaseModel):
    """A single value-driving KPI."""
    name: str = Field(..., description="KPI name, e.g. 'Net Revenue Retention'")
    why_it_moves_value: str = Field(
        ...,
        description="1-sentence causal explanation of why this metric drives value",
    )
    definition: str = Field(
        ...,
        description="1-2 sentence operational definition",
    )
    unit: Optional[str] = Field(
        None,
        description="e.g. '%', '$/user/month', 'hours', 'bps'",
    )
    typical_direction: Optional[Literal["up_is_good", "down_is_good", "depends"]] = None
    disclosure: DisclosureRef = Field(default_factory=lambda: DisclosureRef(source_type="not_provided"))
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────

class KeyDriversKpisOutput(BaseModel):
    """Top-level LLM output for the key_drivers_kpis section."""
    kpis: list[KPI] = Field(..., min_length=1, max_length=5)
    overall_takeaways: list[str] = Field(..., min_length=1, max_length=3)
    confidence: Confidence
    low_confidence_flag: bool = False
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_kpi_count(self) -> "KeyDriversKpisOutput":
        """Warn but accept 1-2 KPIs (low confidence); hard reject 0 or >5."""
        # Pydantic min_length/max_length already enforce 1..5
        # We flag low confidence for <3 in postprocess, not here
        return self


# ── JSON schema helpers ──────────────────────────────────────────────────────

def get_key_drivers_kpis_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return KeyDriversKpisOutput.model_json_schema()


def get_key_drivers_kpis_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_key_drivers_kpis_json_schema(), indent=2)
