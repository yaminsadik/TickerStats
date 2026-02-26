"""
Config-driven model catalog — single source of truth for all LLM model
definitions, pricing, thinking configs, and tier assignments.

To add / remove / rename a model, edit THIS FILE ONLY.
Provider implementations, the policy module, and the client API all read
from the helpers exported here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Thinking-config type constants (used by provider implementations)
# ---------------------------------------------------------------------------

THINKING_REASONING_EFFORT = "reasoning_effort"  # OpenAI: reasoning={"effort": …}
THINKING_LEVEL = "thinking_level"               # Gemini: thinking_level="HIGH"|"LOW"
THINKING_MODEL_SWITCH = "model_switch"           # DeepSeek: pick deepseek-reasoner
THINKING_TYPE = "thinking_type"                  # Z.AI: thinking={"type": "enabled"|"disabled"}
THINKING_BUDGET_TOKENS = "budget_tokens"         # Anthropic: thinking={"type":"enabled","budget_tokens":N}


# ---------------------------------------------------------------------------
# ModelDef — frozen dataclass representing one model entry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ModelDef:
    provider: str                       # "openai" | "gemini" | "deepseek" | "zai" | "anthropic"
    model_id: str                       # API model name, e.g. "gpt-5-mini"
    display_name: str                   # UI label, e.g. "GPT-5 Mini"
    tiers: tuple[str, ...]              # ("free",) or ("pro",) or ("free","pro")
    thinking_supported: bool            # can this model think?
    thinking_config_type: Optional[str] # one of the THINKING_* constants above, or None
    input_price_per_m: float            # $ per 1 M input tokens  (0.0 = free)
    output_price_per_m: float           # $ per 1 M output tokens (0.0 = free)
    context_window: int                 # max context length in tokens
    max_output: int                     # max output tokens
    is_default: dict[str, bool] = field(default_factory=dict)  # e.g. {"free": True}


# ============================================================================
# FREE TIER MODELS
# ============================================================================

GPT_5_MINI = ModelDef(
    provider="openai",
    model_id="gpt-5-mini",
    display_name="GPT-5 Mini",
    tiers=("free",),
    thinking_supported=True,
    thinking_config_type=THINKING_REASONING_EFFORT,
    input_price_per_m=0.15,
    output_price_per_m=0.60,
    context_window=128_000,
    max_output=8_192,
    is_default={"free": True},
)

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
)

DEEPSEEK_CHAT = ModelDef(
    provider="deepseek",
    model_id="deepseek-chat",
    display_name="DeepSeek V3.2",
    tiers=("free",),
    thinking_supported=False,
    thinking_config_type=None,
    input_price_per_m=0.28,
    output_price_per_m=0.42,
    context_window=128_000,
    max_output=8_192,
)

DEEPSEEK_REASONER = ModelDef(
    provider="deepseek",
    model_id="deepseek-reasoner",
    display_name="DeepSeek V3.2 Reasoner",
    tiers=("free",),
    thinking_supported=True,
    thinking_config_type=THINKING_MODEL_SWITCH,
    input_price_per_m=0.28,
    output_price_per_m=0.42,
    context_window=128_000,
    max_output=65_536,
)

GLM_47_FLASH = ModelDef(
    provider="zai",
    model_id="glm-4.7-flash",
    display_name="GLM-4.7 Flash (Free)",
    tiers=("free",),
    thinking_supported=True,
    thinking_config_type=THINKING_TYPE,
    input_price_per_m=0.0,
    output_price_per_m=0.0,
    context_window=200_000,
    max_output=128_000,
)

GLM_47_FLASHX = ModelDef(
    provider="zai",
    model_id="glm-4.7-flashx",
    display_name="GLM-4.7 FlashX",
    tiers=("free",),
    thinking_supported=True,
    thinking_config_type=THINKING_TYPE,
    input_price_per_m=0.07,
    output_price_per_m=0.40,
    context_window=200_000,
    max_output=128_000,
)

CLAUDE_HAIKU_45 = ModelDef(
    provider="anthropic",
    model_id="claude-haiku-4-5",
    display_name="Claude Haiku 4.5",
    tiers=("free", "pro"),
    thinking_supported=True,
    thinking_config_type=THINKING_BUDGET_TOKENS,
    input_price_per_m=0.80,
    output_price_per_m=4.00,
    context_window=200_000,
    max_output=128_000,
)

# ============================================================================
# PRO TIER MODELS
# ============================================================================

GPT_52 = ModelDef(
    provider="openai",
    model_id="gpt-5.2",
    display_name="GPT-5.2",
    tiers=("pro",),
    thinking_supported=True,
    thinking_config_type=THINKING_REASONING_EFFORT,
    input_price_per_m=2.50,
    output_price_per_m=10.00,
    context_window=128_000,
    max_output=32_768,
)

GEMINI_3_PRO = ModelDef(
    provider="gemini",
    model_id="gemini-3-pro-preview",
    display_name="Gemini 3 Pro",
    tiers=("pro",),
    thinking_supported=True,
    thinking_config_type=THINKING_LEVEL,
    input_price_per_m=2.00,
    output_price_per_m=8.00,
    context_window=1_000_000,
    max_output=65_536,
)

CLAUDE_SONNET_45 = ModelDef(
    provider="anthropic",
    model_id="claude-sonnet-4-5",
    display_name="Claude Sonnet 4.5",
    tiers=("pro",),
    thinking_supported=True,
    thinking_config_type=THINKING_BUDGET_TOKENS,
    input_price_per_m=3.00,
    output_price_per_m=15.00,
    context_window=200_000,
    max_output=128_000,
)

GLM_5 = ModelDef(
    provider="zai",
    model_id="glm-5",
    display_name="GLM-5",
    tiers=("pro",),
    thinking_supported=True,
    thinking_config_type=THINKING_TYPE,
    input_price_per_m=1.00,
    output_price_per_m=3.20,
    context_window=200_000,
    max_output=128_000,
)


# ============================================================================
# COLLECTED CATALOG
# ============================================================================

MODEL_CATALOG: list[ModelDef] = [
    # Free tier
    GPT_5_MINI,
    GEMINI_3_FLASH,
    DEEPSEEK_CHAT,
    DEEPSEEK_REASONER,
    GLM_47_FLASH,
    GLM_47_FLASHX,
    CLAUDE_HAIKU_45,
    # Pro tier
    GPT_52,
    GEMINI_3_PRO,
    CLAUDE_SONNET_45,
    GLM_5,
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
