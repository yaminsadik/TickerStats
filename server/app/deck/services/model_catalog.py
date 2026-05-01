"""
Config-driven model catalog for the currently active Gemini-only model
surface.

To add / remove / rename a model, edit THIS FILE ONLY.
Provider implementations remain available, but policy and API helpers only
expose models listed in ``MODEL_CATALOG``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Thinking-config type constants (used by active model policy)
# ---------------------------------------------------------------------------

THINKING_LEVEL = "thinking_level"  # Gemini: thinking_level="HIGH"|"LOW"


# ---------------------------------------------------------------------------
# ModelDef — frozen dataclass representing one model entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelDef:
    provider: str                       # active provider is "gemini"
    model_id: str                       # API model name, e.g. "gemini-3-flash-preview"
    display_name: str                   # UI label, e.g. "Gemini 3 Flash"
    tiers: tuple[str, ...]              # ("free",) or ("pro",) or ("free","pro")
    thinking_supported: bool            # can this model think?
    thinking_config_type: Optional[str] # one of the THINKING_* constants above, or None
    input_price_per_m: float            # $ per 1 M input tokens  (0.0 = free)
    output_price_per_m: float           # $ per 1 M output tokens (0.0 = free)
    context_window: int                 # max context length in tokens
    max_output: int                     # max output tokens
    is_default: dict[str, bool] = field(default_factory=dict)  # e.g. {"free": True}


# ============================================================================
# FREE TIER MODEL
# ============================================================================

GEMINI_3_FLASH = ModelDef(
    provider="gemini",
    model_id="gemini-3-flash-preview",
    display_name="Gemini 3 Flash",
    tiers=("free",),
    thinking_supported=True,
    thinking_config_type=THINKING_LEVEL,
    input_price_per_m=0.075,
    output_price_per_m=0.30,
    context_window=1_000_000,
    max_output=65_536,
    is_default={"free": True},
)

# ============================================================================
# PRO TIER MODEL
# ============================================================================

GEMINI_3_1_PRO = ModelDef(
    provider="gemini",
    model_id="gemini-3.1-pro-preview",
    display_name="Gemini 3.1 Pro",
    tiers=("pro",),
    thinking_supported=True,
    thinking_config_type=THINKING_LEVEL,
    input_price_per_m=2.00,
    output_price_per_m=8.00,
    context_window=1_000_000,
    max_output=65_536,
    is_default={"pro": True},
)

# ============================================================================
# COLLECTED CATALOG
# ============================================================================

MODEL_CATALOG: list[ModelDef] = [
    GEMINI_3_FLASH,
    GEMINI_3_1_PRO,
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _effective_tier(tier: str) -> str:
    return "pro" if tier == "enterprise" else tier


def is_model_available_for_tier(model_def: ModelDef, tier: str) -> bool:
    """Return whether a model is available for the given plan tier.

    Rules:
    - Free users: free models only
    - Pro / Enterprise users: pro + free models
    """
    effective = _effective_tier(tier)
    if effective == "free":
        return "free" in model_def.tiers
    if effective == "pro":
        return "pro" in model_def.tiers or "free" in model_def.tiers
    return False


def get_models_for_tier(tier: str) -> list[ModelDef]:
    """Return all models available to a given tier.

    Enterprise users inherit pro-tier access, which includes both pro
    and free models. Returned order for paid tiers is:
    1) pro models
    2) free models
    """
    effective = _effective_tier(tier)
    models = [m for m in MODEL_CATALOG if is_model_available_for_tier(m, tier)]

    # Keep paid plans ordered as: paid models first, then free models.
    if effective == "pro":
        catalog_order = {m.model_id: i for i, m in enumerate(MODEL_CATALOG)}
        models.sort(
            key=lambda m: (
                0 if ("pro" in m.tiers and "free" not in m.tiers) else 1,
                catalog_order[m.model_id],
            )
        )
    return models


def get_default_model(tier: str) -> ModelDef:
    """Return the default model for a tier (the one with is_default[tier]=True)."""
    effective = _effective_tier(tier)
    for m in MODEL_CATALOG:
        if effective in m.tiers and m.is_default.get(effective):
            return m
    # Fallback: first model in the tier
    tier_models = get_models_for_tier(tier)
    if tier_models:
        return tier_models[0]
    raise ValueError(f"No models available for tier: {tier}")


def get_model_by_id(model_id: str) -> Optional[ModelDef]:
    """Look up a model by its API model_id string."""
    for m in MODEL_CATALOG:
        if m.model_id == model_id:
            return m
    return None


def get_price_table() -> dict[str, tuple[float, float]]:
    """Return {model_id: (input_price_per_m, output_price_per_m)} for cost estimation."""
    return {m.model_id: (m.input_price_per_m, m.output_price_per_m) for m in MODEL_CATALOG}


def get_catalog_for_api(tier: str) -> list[dict]:
    """Return a JSON-serialisable list of model defs for the /models endpoint."""
    return [
        {
            "provider": m.provider,
            "model_id": m.model_id,
            "display_name": m.display_name,
            "thinking_supported": m.thinking_supported,
            "input_price_per_m": m.input_price_per_m,
            "output_price_per_m": m.output_price_per_m,
            "context_window": m.context_window,
            "max_output": m.max_output,
        }
        for m in get_models_for_tier(tier)
    ]
