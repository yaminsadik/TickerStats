"""
Model routing policy — tier-aware model selection, thinking toggle,
and fallback chain construction.

All model look-ups go through :mod:`model_catalog`; this module never
hard-codes model IDs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.deck.services.model_catalog import (
    THINKING_BUDGET_TOKENS,
    THINKING_LEVEL,
    THINKING_MODEL_SWITCH,
    THINKING_REASONING_EFFORT,
    THINKING_TYPE,
    ModelDef,
    get_default_model,
    get_model_by_id,
    get_models_for_tier,
    is_model_available_for_tier,
)


# ---------------------------------------------------------------------------
# Decision output
# ---------------------------------------------------------------------------

@dataclass
class ModelDecision:
    provider: str
    model: str
    thinking_enabled: bool
    thinking_config: Optional[dict]        # provider-specific thinking params
    analysis_depth: str
    fallback_chain: list[ModelDef] = field(default_factory=list)
    reason: str = ""


# ---------------------------------------------------------------------------
# Thinking-config builders (one per thinking_config_type)
# ---------------------------------------------------------------------------

def _build_thinking_config(model_def: ModelDef, thinking_requested: bool) -> tuple[bool, Optional[dict]]:
    """Return (thinking_enabled, provider-specific config dict | None)."""
    if not thinking_requested or not model_def.thinking_supported:
        return False, None

    cfg_type = model_def.thinking_config_type

    if cfg_type == THINKING_REASONING_EFFORT:
        return True, {"effort": "high"}

    if cfg_type == THINKING_LEVEL:
        return True, {"thinking_level": "HIGH"}

    if cfg_type == THINKING_MODEL_SWITCH:
        # For DeepSeek the thinking is implicit in model selection; no extra
        # config is needed — the caller already picks deepseek-reasoner.
        return True, None

    if cfg_type == THINKING_TYPE:
        return True, {"type": "enabled"}

    if cfg_type == THINKING_BUDGET_TOKENS:
        return True, {"type": "enabled", "budget_tokens": 10_000}

    return False, None


# ---------------------------------------------------------------------------
# Fallback chain builder
# ---------------------------------------------------------------------------

def _build_fallback_chain(
    primary: ModelDef,
    tier: str,
    available_keys: dict[str, Optional[str]],
) -> list[ModelDef]:
    """Other models in the same tier with valid keys, ordered cheapest first."""
    candidates = [
        m
        for m in get_models_for_tier(tier)
        if m.model_id != primary.model_id and available_keys.get(m.provider)
    ]
    # Sort by total estimated cost (input + output) ascending
    candidates.sort(key=lambda m: m.input_price_per_m + m.output_price_per_m)
    return candidates


# ---------------------------------------------------------------------------
# Main resolver
# ---------------------------------------------------------------------------

def resolve_model(
    plan_tier: str,
    analysis_depth: str,
    model_mode: str,                          # "auto" | "specific"
    requested_model_id: Optional[str],
    thinking_requested: bool,
    available_keys: dict[str, Optional[str]],
    usage_stats: Optional[dict] = None,
) -> ModelDecision:
    """Choose a provider / model based on tier, user preference, and key availability.

    Parameters
    ----------
    plan_tier : str
        ``"free"`` | ``"pro"`` | ``"enterprise"``
    analysis_depth : str
        ``"low"`` | ``"medium"`` | ``"high"``
    model_mode : str
        ``"auto"`` — let the policy decide; ``"specific"`` — honour the user's choice.
    requested_model_id : str | None
        If *model_mode* is ``"specific"``, this is the user's chosen ``model_id``.
    thinking_requested : bool
        Whether the user toggled thinking / high reasoning.
    available_keys : dict
        ``{provider_name: api_key_or_None}``.
    usage_stats : dict | None
        Reserved for future budget-aware routing.

    Returns
    -------
    ModelDecision
    """

    # --- specific mode: honour user choice -----------------------------------
    if model_mode == "specific" and requested_model_id:
        model_def = get_model_by_id(requested_model_id)
        if model_def is not None:
            # Verify the user's tier grants access
            if is_model_available_for_tier(model_def, plan_tier):
                # Verify we actually have the key
                if available_keys.get(model_def.provider):
                    thinking_on, thinking_cfg = _build_thinking_config(model_def, thinking_requested)
                    return ModelDecision(
                        provider=model_def.provider,
                        model=model_def.model_id,
                        thinking_enabled=thinking_on,
                        thinking_config=thinking_cfg,
                        analysis_depth=analysis_depth,
                        fallback_chain=_build_fallback_chain(model_def, plan_tier, available_keys),
                        reason=f"User selected {model_def.display_name}",
                    )
        # Fall through to auto if the requested model is invalid / inaccessible

    # --- auto mode: pick best available model --------------------------------
    default = get_default_model(plan_tier)

    # If the default provider's key is available, use it
    if available_keys.get(default.provider):
        chosen = default
        reason = f"Auto: tier default {default.display_name}"
    else:
        # Walk the tier's models to find the first one with a valid key
        chosen = None
        for m in get_models_for_tier(plan_tier):
            if available_keys.get(m.provider):
                chosen = m
                reason = f"Auto: fallback to {m.display_name} (default provider key missing)"
                break

        if chosen is None:
            # Absolute fallback — return the default even though the key is
            # missing; the caller will raise a proper 400 error.
            chosen = default
            reason = "Auto: no provider keys available, returning default (will error)"

    thinking_on, thinking_cfg = _build_thinking_config(chosen, thinking_requested)

    return ModelDecision(
        provider=chosen.provider,
        model=chosen.model_id,
        thinking_enabled=thinking_on,
        thinking_config=thinking_cfg,
        analysis_depth=analysis_depth,
        fallback_chain=_build_fallback_chain(chosen, plan_tier, available_keys),
        reason=reason,
    )
