"""
Tests for provider-aware reasoning option mapping in DeckGenerator.
"""

from app.deck.services.deck_generator import DeckGenerator


class TestProviderReasoningMapping:
    def setup_method(self):
        self.generator = DeckGenerator()

    def test_openai_maps_reasoning_effort(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="openai",
            model="gpt-5.2",
            reasoning_level="high",
        )
        assert extra["model"] == "gpt-5.2"
        assert extra["reasoning_effort"] == "high"

    def test_gemini_pro_maps_medium_to_high(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="gemini",
            model="gemini-3-pro",
            reasoning_level="medium",
        )
        assert extra["thinking_level"] == "high"

    def test_gemini_flash_keeps_medium(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="gemini",
            model="gemini-3-flash-preview",
            reasoning_level="medium",
        )
        assert extra["thinking_level"] == "medium"

    def test_deepseek_uses_model_only(self):
        extra = self.generator._build_provider_options_extra(
            provider_name="deepseek",
            model="deepseek-reasoner",
            reasoning_level="high",
        )
        assert extra == {"model": "deepseek-reasoner"}

    def test_zai_toggles_thinking(self):
        low_extra = self.generator._build_provider_options_extra(
            provider_name="zai",
            model="glm-4.7-flashx",
            reasoning_level="low",
        )
        high_extra = self.generator._build_provider_options_extra(
            provider_name="zai",
            model="glm-4.7-flashx",
            reasoning_level="high",
        )
        assert low_extra["thinking_enabled"] is False
        assert high_extra["thinking_enabled"] is True

    def test_anthropic_budget_by_level(self):
        medium_extra = self.generator._build_provider_options_extra(
            provider_name="anthropic",
            model="claude-sonnet-4-5",
            reasoning_level="medium",
        )
        high_extra = self.generator._build_provider_options_extra(
            provider_name="anthropic",
            model="claude-sonnet-4-5",
            reasoning_level="high",
        )
        assert medium_extra["thinking_enabled"] is True
        assert medium_extra["thinking_budget_tokens"] == 4_000
        assert high_extra["thinking_budget_tokens"] == 10_000
