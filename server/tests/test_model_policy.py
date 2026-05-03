"""
Tests for model_catalog and model_policy modules.
"""

import pytest

from app.deck.services.model_catalog import (
    MODEL_CATALOG,
    ModelDef,
    get_catalog_for_api,
    get_default_model,
    get_model_by_id,
    get_models_for_tier,
    get_price_table,
)
from app.deck.services.model_policy import ModelDecision, resolve_model


# =========================================================================
# Model Catalog tests
# =========================================================================


class TestModelCatalog:

    def test_catalog_not_empty(self):
        assert len(MODEL_CATALOG) == 1

    def test_get_models_for_free_tier(self):
        free = get_models_for_tier("free")
        assert len(free) == 1
        assert all("free" in m.tiers for m in free)
        free_ids = [m.model_id for m in free]
        assert free_ids == ["gemini-3.1-pro-preview"]

    def test_get_models_for_pro_tier(self):
        pro = get_models_for_tier("pro")
        assert len(pro) == 1
        pro_ids = [m.model_id for m in pro]
        assert pro_ids == ["gemini-3.1-pro-preview"]

    def test_enterprise_maps_to_pro(self):
        pro = get_models_for_tier("pro")
        ent = get_models_for_tier("enterprise")
        assert pro == ent

    def test_get_default_model_free(self):
        default = get_default_model("free")
        assert default.model_id == "gemini-3.1-pro-preview"

    def test_get_default_model_pro(self):
        default = get_default_model("pro")
        assert default.model_id == "gemini-3.1-pro-preview"

    def test_get_model_by_id_found(self):
        m = get_model_by_id("gemini-3.1-pro-preview")
        assert m is not None
        assert m.provider == "gemini"

    def test_get_model_by_id_not_found(self):
        m = get_model_by_id("nonexistent-model")
        assert m is None

    def test_price_table_complete(self):
        table = get_price_table()
        for m in MODEL_CATALOG:
            assert m.model_id in table
            inp, out = table[m.model_id]
            assert inp >= 0
            assert out >= 0

    def test_gemini_pro_pricing(self):
        m = get_model_by_id("gemini-3.1-pro-preview")
        assert m is not None
        assert m.input_price_per_m >= 0.0
        assert m.output_price_per_m >= 0.0

    def test_catalog_for_api(self):
        data = get_catalog_for_api("free")
        assert isinstance(data, list)
        assert all("model_id" in d for d in data)


# =========================================================================
# Model Policy tests
# =========================================================================

ALL_KEYS = {
    "gemini": "ok",
}


class TestModelPolicy:

    def test_auto_free_tier_returns_default(self):
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="auto",
            requested_model_id=None,
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        assert isinstance(decision, ModelDecision)
        assert decision.model == "gemini-3.1-pro-preview"
        assert decision.provider == "gemini"

    def test_specific_free_model(self):
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="specific",
            requested_model_id="gemini-3.1-pro-preview",
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        assert decision.model == "gemini-3.1-pro-preview"
        assert decision.provider == "gemini"

    def test_specific_free_models(self):
        free_ids = [m.model_id for m in get_models_for_tier("free")]
        for model_id in free_ids:
            decision = resolve_model(
                plan_tier="free",
                analysis_depth="medium",
                model_mode="specific",
                requested_model_id=model_id,
                thinking_requested=False,
                available_keys=ALL_KEYS,
            )
            assert decision.model == model_id

    def test_pro_tier_auto(self):
        decision = resolve_model(
            plan_tier="pro",
            analysis_depth="medium",
            model_mode="auto",
            requested_model_id=None,
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        pro_ids = {m.model_id for m in get_models_for_tier("pro")}
        assert decision.model in pro_ids

    def test_specific_pro_can_select_active_model(self):
        decision = resolve_model(
            plan_tier="pro",
            analysis_depth="medium",
            model_mode="specific",
            requested_model_id="gemini-3.1-pro-preview",
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        assert decision.model == "gemini-3.1-pro-preview"
        assert decision.provider == "gemini"

    def test_thinking_enabled_when_supported(self):
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="high",
            model_mode="specific",
            requested_model_id="gemini-3.1-pro-preview",
            thinking_requested=True,
            available_keys=ALL_KEYS,
        )
        assert decision.thinking_enabled is True
        assert decision.thinking_config is not None

    def test_inactive_specific_model_falls_through(self):
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="specific",
            requested_model_id="inactive-model",
            thinking_requested=True,
            available_keys=ALL_KEYS,
        )
        assert decision.provider == "gemini"
        assert decision.model == "gemini-3.1-pro-preview"

    def test_missing_key_excluded_from_fallback(self):
        keys = {"gemini": None}
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="auto",
            requested_model_id=None,
            thinking_requested=False,
            available_keys=keys,
        )
        # Fallback chain should only contain models whose key is available
        for m in decision.fallback_chain:
            assert keys.get(m.provider), f"Fallback includes {m.provider} but key is missing"

    def test_fallback_chain_ordered_by_cost(self):
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="auto",
            requested_model_id=None,
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        costs = [m.input_price_per_m + m.output_price_per_m for m in decision.fallback_chain]
        assert costs == sorted(costs), "Fallback chain not sorted cheapest-first"

    def test_auto_fallback_when_default_key_missing(self):
        keys = {"gemini": "ok"}
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="auto",
            requested_model_id=None,
            thinking_requested=False,
            available_keys=keys,
        )
        assert decision.provider == "gemini"

    def test_removed_flash_model_falls_through(self):
        """A user requesting the removed Flash model should fall through to auto."""
        decision = resolve_model(
            plan_tier="free",
            analysis_depth="medium",
            model_mode="specific",
            requested_model_id="gemini-3-flash-preview",
            thinking_requested=False,
            available_keys=ALL_KEYS,
        )
        assert decision.model == "gemini-3.1-pro-preview"
