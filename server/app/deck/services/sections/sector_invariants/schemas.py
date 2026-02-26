"""
Pydantic v2 models for the Sector Invariants section output.

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

Sector = Literal["tech_software", "other"]

ModuleId = Literal[
    "revenue_quality_gtm",
    "platform_dependencies_risk",
    "security_reliability",
]


# ── Leaf types ───────────────────────────────────────────────────────────────

class KPIItem(BaseModel):
    """A single KPI data point."""
    label: str
    value: Optional[str] = None
    as_of: Optional[str] = None
    source_note: Optional[str] = None


class ModuleOut(BaseModel):
    """Output for a single invariant module."""
    id: ModuleId
    title: str
    bullets: list[str] = Field(..., min_length=2, max_length=6)
    kpis: list[KPIItem] = Field(default_factory=list, max_length=8)
    failure_modes: list[str] = Field(default_factory=list, max_length=4)
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level output ─────────────────────────────────────────────────────────

class SectorInvariantsOutput(BaseModel):
    """Top-level LLM output for the sector_invariants section."""
    sector_class: Sector
    included_modules: list[ModuleId]
    modules: list[ModuleOut]
    low_confidence_flag: bool = False
    notes: Optional[str] = None

    @model_validator(mode="after")
    def _validate_modules(self) -> "SectorInvariantsOutput":
        # modules length must match included_modules length
        if len(self.modules) != len(self.included_modules):
            raise ValueError(
                f"modules length ({len(self.modules)}) must match "
                f"included_modules length ({len(self.included_modules)})"
            )
        # each ModuleOut.id must be unique
        ids = [m.id for m in self.modules]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate module IDs in modules list")
        # each module id must be in included_modules
        for m in self.modules:
            if m.id not in self.included_modules:
                raise ValueError(
                    f"Module '{m.id}' not in included_modules"
                )
        return self


# ── JSON schema helpers ──────────────────────────────────────────────────────

def get_sector_invariants_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return SectorInvariantsOutput.model_json_schema()


def get_sector_invariants_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_sector_invariants_json_schema(), indent=2)
