"""
Pydantic models for the Management, Ownership & Governance section output.

These define the *LLM* output schema — the structured JSON that the model must
produce.  After generation, ``spec.postprocess`` converts this into the
standard ``{section_id, slides[]}`` shape the pipeline expects.
"""

from __future__ import annotations

import json
from typing import Literal, Optional

from pydantic import BaseModel, Field


# ── Shared literals ──────────────────────────────────────────────────────────

Confidence = Literal["high", "medium", "low"]
HolderType = Literal["institution", "insider", "activist", "other"]
FlagSeverity = Literal["low", "medium", "high"]
GovFlagType = Literal[
    "dual_class",
    "classified_board",
    "related_party",
    "auditor_change",
    "poison_pill",
    "supermajority_vote",
    "insider_control",
    "capital_allocation",
    "other",
]


# ── Management ───────────────────────────────────────────────────────────────

class Executive(BaseModel):
    name: Optional[str] = Field(None, description="Executive name — null when not provided")
    role: Optional[str] = Field(None, description="Title / role")
    since: Optional[str] = Field(None, description="Year or YYYY-MM if provided")
    equity_ownership: Optional[str] = Field(
        None, description='e.g. "2.1% of shares" ONLY if provided',
    )
    notes: Optional[str] = None


class Incentive(BaseModel):
    component: str = Field(..., description='e.g. "Annual bonus", "LTIP/RSUs", "Options"')
    metric_link: Optional[str] = Field(
        None, description='e.g. "EPS, FCF, ROIC" ONLY if provided',
    )
    weight: Optional[str] = Field(
        None, description='e.g. "60% LT" ONLY if provided',
    )


class ManagementOut(BaseModel):
    executives: list[Executive] = Field(
        default_factory=list,
        description="0–6 executives",
        max_length=6,
    )
    track_record: list[str] = Field(
        ...,
        description="2–5 factual bullets, no hype",
        min_length=2,
        max_length=5,
    )
    incentives: list[Incentive] = Field(
        default_factory=list,
        description="0–5 incentive components",
        max_length=5,
    )
    alignment_summary: list[str] = Field(
        ...,
        description="2–4 bullets; if limited data, say so",
        min_length=2,
        max_length=4,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Ownership ────────────────────────────────────────────────────────────────

class Holder(BaseModel):
    name: str = Field(..., description="Must come from inputs")
    holder_type: HolderType
    stake: Optional[str] = Field(
        None, description='"x%" or "$x" only if provided',
    )
    comment: Optional[str] = Field(
        None, description='e.g. "top 5 holder", "activist campaign"',
    )


class OwnershipOut(BaseModel):
    top_holders: list[Holder] = Field(
        default_factory=list,
        description="0–10 holders",
        max_length=10,
    )
    insider_ownership_summary: Optional[str] = Field(
        None, description='e.g. "insiders own ~x%" only if provided',
    )
    activist_presence: Optional[str] = Field(
        None, description="Only if provided",
    )
    takeaways: list[str] = Field(
        ...,
        description="1–3 ownership takeaways",
        min_length=1,
        max_length=3,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Governance ───────────────────────────────────────────────────────────────

class GovernanceFlag(BaseModel):
    flag_type: GovFlagType
    severity: FlagSeverity
    fact: str = Field(..., description="Factual statement from inputs")
    why_it_matters: str = Field(..., description="Neutral 1-liner")


class GovernanceOut(BaseModel):
    flags: list[GovernanceFlag] = Field(
        default_factory=list,
        description="0–8 governance flags",
        max_length=8,
    )
    takeaways: list[str] = Field(
        ...,
        description="1–3 governance takeaways",
        min_length=1,
        max_length=3,
    )
    confidence: Confidence
    notes: Optional[str] = None


# ── Top-level aggregate ──────────────────────────────────────────────────────

class ManagementOwnershipGovernanceOutput(BaseModel):
    """Top-level LLM output for the management_ownership_governance section."""

    management: ManagementOut
    ownership: OwnershipOut
    governance: GovernanceOut
    low_confidence_flag: bool = False


# ── JSON schema helpers for prompt embedding ─────────────────────────────────

def get_mog_json_schema() -> dict:
    """Return the JSON Schema derived from the Pydantic model."""
    return ManagementOwnershipGovernanceOutput.model_json_schema()


def get_mog_json_schema_str() -> str:
    """Pretty-printed JSON schema string (for embedding in prompts)."""
    return json.dumps(get_mog_json_schema(), indent=2)
