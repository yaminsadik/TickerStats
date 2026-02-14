"""
Tests for LLM providers.
All tests mock API clients - no real API calls are made.
"""

import json
import pytest
from unittest.mock import MagicMock, patch, PropertyMock

from app.deck.services.llm_base import (
    LLMError,
    LLMOptions,
    LLMProvider,
    LLMResponse,
    RateLimitError,
    AuthenticationError,
    InvalidResponseError,
    get_provider,
)


class TestLLMOptions:
    """Tests for LLMOptions dataclass."""
    
    def test_default_values(self):
        options = LLMOptions()
        assert options.temperature == 0.7
        assert options.max_tokens == 4096
        assert options.timeout == 60
        assert options.reasoning_level == "medium"
    
    def test_custom_values(self):
        options = LLMOptions(
            temperature=0.5,
            max_tokens=2048,
            reasoning_level="high",
        )
        assert options.temperature == 0.5
        assert options.max_tokens == 2048
        assert options.reasoning_level == "high"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""
    
    def test_response_creation(self):
        response = LLMResponse(
            content={"key": "value"},
            raw_response='{"key": "value"}',
            model="gpt-5.2",
            provider="openai",
        )
        assert response.content == {"key": "value"}
        assert response.model == "gpt-5.2"
        assert response.provider == "openai"
        assert response.latency_ms == 0.0
        assert response.retries == 0


class TestGetProvider:
    """Tests for provider factory function."""
    
    def test_get_openai_provider(self):
        provider = get_provider("openai", "test-key")
        assert provider.PROVIDER_NAME == "openai"
    
    def test_get_gemini_provider(self):
        provider = get_provider("gemini", "test-key")
        assert provider.PROVIDER_NAME == "gemini"
    
    def test_get_deepseek_provider(self):
        provider = get_provider("deepseek", "test-key")
        assert provider.PROVIDER_NAME == "deepseek"
    
    def test_get_zai_provider(self):
        provider = get_provider("zai", "test-key")
        assert provider.PROVIDER_NAME == "zai"
    
    def test_get_anthropic_provider(self):
        provider = get_provider("anthropic", "test-key")
        assert provider.PROVIDER_NAME == "anthropic"
    
    def test_invalid_provider(self):
        with pytest.raises(ValueError) as exc_info:
            get_provider("invalid", "test-key")
        assert "Unknown provider" in str(exc_info.value)
    
    def test_case_insensitive(self):
        provider = get_provider("OpenAI", "test-key")
        assert provider.PROVIDER_NAME == "openai"


class TestOpenAIProvider:
    """Tests for OpenAI provider with mocked API client."""
    
    def test_default_model_is_gpt5_mini(self):
        """Verify default model is GPT-5 Mini."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        provider = OpenAIProvider("test-key")
        assert provider.get_default_model() == "gpt-5-mini"
    
    def test_default_models_by_level(self):
        """Verify DEFAULT_MODELS uses GPT-5 family."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        assert OpenAIProvider.DEFAULT_MODELS["low"] == "gpt-5-nano"
        assert OpenAIProvider.DEFAULT_MODELS["medium"] == "gpt-5-mini"
        assert OpenAIProvider.DEFAULT_MODELS["high"] == "gpt-5.1"
    
    def test_reasoning_effort_mapping(self):
        """Verify reasoning effort is mapped for GPT-5.2."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        provider = OpenAIProvider("test-key")
        
        low = provider._map_reasoning_level("low")
        assert low["reasoning_effort"] == "low"
        assert low["temperature"] == 1.0  # Structured Outputs best at temp=1
        
        high = provider._map_reasoning_level("high")
        assert high["reasoning_effort"] == "high"
    
    def test_strict_schema_conversion(self):
        """Test JSON schema conversion to strict format."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        provider = OpenAIProvider("test-key")
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "integer"}
                        }
                    }
                }
            }
        }
        
        strict = provider._convert_to_strict_schema(schema)
        
        # Should add additionalProperties: false
        assert strict.get("additionalProperties") is False
        # Should add required
        assert "required" in strict
        assert "name" in strict["required"]
    
    @patch("app.deck.services.llm_openai.OpenAIProvider._get_client")
    def test_generate_json_with_structured_outputs(self, mock_get_client):
        """Test that generate_json uses Structured Outputs format."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        # Mock the completion response
        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"section_id": "overview", "slides": []}'
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50
        mock_completion.usage.total_tokens = 150
        mock_completion.usage.completion_tokens_details = None
        
        mock_client.chat.completions.create.return_value = mock_completion
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider("test-key")
        response = provider.generate_json(
            system_prompt="You are an assistant",
            user_prompt="Generate content",
            json_schema={"type": "object", "properties": {"section_id": {"type": "string"}, "slides": {"type": "array"}}},
        )
        
        # Verify Structured Outputs format was used
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert "response_format" in call_kwargs
        assert call_kwargs["response_format"]["type"] == "json_schema"
        assert call_kwargs["response_format"]["json_schema"]["strict"] is True
        
        # Verify reasoning effort was passed
        assert call_kwargs["reasoning_effort"] == "medium"
        
        assert response.content == {"section_id": "overview", "slides": []}
        assert response.provider == "openai"
    
    @patch("app.deck.services.llm_openai.OpenAIProvider._get_client")
    def test_rate_limit_error_handling(self, mock_get_client):
        """Test rate limit error is properly raised."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_get_client.return_value = mock_client
        
        provider = OpenAIProvider("test-key")
        
        with pytest.raises(RateLimitError):
            provider.generate_json(
                system_prompt="test",
                user_prompt="test",
                json_schema={"type": "object"},
            )


class TestGeminiProvider:
    """Tests for Gemini provider with mocked API client."""
    
    def test_default_model_is_gemini3_flash(self):
        """Verify default model is Gemini 3 Flash Preview."""
        from app.deck.services.llm_gemini import GeminiProvider
        
        provider = GeminiProvider("test-key")
        assert provider.get_default_model() == "gemini-3-flash-preview"
    
    def test_default_models_by_level(self):
        """Verify DEFAULT_MODELS uses Gemini 3 Flash Preview."""
        from app.deck.services.llm_gemini import GeminiProvider
        
        assert GeminiProvider.DEFAULT_MODELS["low"] == "gemini-3-flash-preview"
        assert GeminiProvider.DEFAULT_MODELS["medium"] == "gemini-3-flash-preview"
        assert GeminiProvider.DEFAULT_MODELS["high"] == "gemini-3-flash-preview"
    
    def test_reasoning_level_mapping(self):
        """Verify reasoning level config for Gemini 3."""
        from app.deck.services.llm_gemini import GeminiProvider
        
        provider = GeminiProvider("test-key")
        
        low = provider._map_reasoning_level("low")
        assert low["temperature"] == 1.0  # Structured Outputs best at temp=1
        assert low["model"] == "gemini-3-flash-preview"
        
        medium = provider._map_reasoning_level("medium")
        assert medium["model"] == "gemini-3-flash-preview"
    
    def test_schema_conversion_to_gemini_format(self):
        """Test JSON schema conversion to Gemini format."""
        from app.deck.services.llm_gemini import GeminiProvider
        
        provider = GeminiProvider("test-key")
        provider._configured = True  # Skip actual configuration
        
        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The name"},
                "count": {"type": "integer"},
            }
        }
        
        gemini_schema = provider._convert_to_gemini_schema(schema)
        
        # Should convert types to uppercase
        assert gemini_schema["type"] == "OBJECT"
        assert gemini_schema["properties"]["name"]["type"] == "STRING"
        assert gemini_schema["properties"]["count"]["type"] == "INTEGER"
    
    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_generate_json_with_response_schema(self, mock_configure, mock_model_class):
        """Test that generate_json uses response_schema for Structured Outputs."""
        from app.deck.services.llm_gemini import GeminiProvider
        
        # Mock the model and response
        mock_model = MagicMock()
        mock_model_class.return_value = mock_model
        
        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.text = '{"section_id": "overview", "slides": []}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        mock_response.usage_metadata.total_token_count = 150
        
        mock_model.generate_content.return_value = mock_response
        
        provider = GeminiProvider("test-key")
        response = provider.generate_json(
            system_prompt="You are an assistant",
            user_prompt="Generate content",
            json_schema={"type": "object", "properties": {"section_id": {"type": "string"}}},
        )
        
        # Verify GenerationConfig was called with response_schema
        call_kwargs = mock_model_class.call_args.kwargs
        assert "generation_config" in call_kwargs
        
        assert response.content == {"section_id": "overview", "slides": []}
        assert response.provider == "gemini"

    @patch("google.generativeai.GenerativeModel")
    @patch("google.generativeai.configure")
    def test_generate_json_includes_thinking_config(self, mock_configure, mock_model_class):
        from app.deck.services.llm_gemini import GeminiProvider

        mock_model = MagicMock()
        mock_model_class.return_value = mock_model

        mock_response = MagicMock()
        mock_response.candidates = [MagicMock()]
        mock_response.text = '{"section_id": "overview", "slides": []}'
        mock_response.usage_metadata = MagicMock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 15
        mock_model.generate_content.return_value = mock_response

        provider = GeminiProvider("test-key")
        provider.generate_json(
            system_prompt="You are an assistant",
            user_prompt="Generate content",
            json_schema={"type": "object", "properties": {"section_id": {"type": "string"}}},
            options=LLMOptions(extra={"thinking_level": "high"}),
        )

        call_kwargs = mock_model_class.call_args.kwargs
        assert "generation_config" in call_kwargs
        generation_config = call_kwargs["generation_config"]
        assert generation_config["thinking_config"]["thinking_level"] == "high"


class TestNumbersGate:
    """Tests for the strict numbers gate."""
    
    def test_has_unverified_numbers_detects_money(self):
        """Test detection of monetary values."""
        from app.deck.utils.validation import has_unverified_numbers
        
        # Without computed inputs, any number is unverified
        assert has_unverified_numbers("Revenue of $5 billion") is True
        assert has_unverified_numbers("Market cap is $50M") is True
    
    def test_has_unverified_numbers_allows_computed_data(self):
        """Test that numbers from computed_inputs are allowed."""
        from app.deck.utils.validation import has_unverified_numbers
        
        computed = {"revenue": 5000000000, "market_cap": "50M"}
        
        # These numbers match computed inputs
        assert has_unverified_numbers("Revenue of $5,000,000,000", computed) is False
    
    def test_has_unverified_numbers_allows_years(self):
        """Test that year references are detected as numeric content."""
        from app.deck.utils.validation import has_unverified_numbers
        
        # Years are detected as numeric content (intentional - better to flag for verification)
        assert has_unverified_numbers("Founded in 2015") is True
    
    def test_flag_numeric_content(self):
        """Test bullet flagging for numeric content."""
        from app.deck.utils.validation import flag_numeric_content
        
        bullets = [
            {"text": "Revenue grew 50% YoY", "source_needed": False},
            {"text": "Strong market position", "source_needed": False},
        ]
        
        # Without computed inputs, numeric bullet should be flagged
        flagged = flag_numeric_content(bullets, None)
        
        assert flagged[0]["source_needed"] is True  # Has percentage
        assert flagged[1]["source_needed"] is False  # No numbers


class TestDeepSeekProvider:
    """Tests for DeepSeek provider with mocked API client."""

    def test_default_model(self):
        from app.deck.services.llm_deepseek import DeepSeekProvider

        provider = DeepSeekProvider("test-key")
        assert provider.get_default_model() == "deepseek-chat"

    def test_default_models_by_level(self):
        from app.deck.services.llm_deepseek import DeepSeekProvider

        assert DeepSeekProvider.DEFAULT_MODELS["low"] == "deepseek-chat"
        assert DeepSeekProvider.DEFAULT_MODELS["medium"] == "deepseek-chat"
        assert DeepSeekProvider.DEFAULT_MODELS["high"] == "deepseek-reasoner"

    @patch("app.deck.services.llm_deepseek.DeepSeekProvider._get_client")
    def test_generate_json_structured_output(self, mock_get_client):
        from app.deck.services.llm_deepseek import DeepSeekProvider

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"section_id": "overview", "slides": []}'
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50
        mock_completion.usage.total_tokens = 150
        mock_completion.usage.completion_tokens_details = None
        mock_client.chat.completions.create.return_value = mock_completion
        mock_get_client.return_value = mock_client

        provider = DeepSeekProvider("test-key")
        response = provider.generate_json(
            system_prompt="test",
            user_prompt="test",
            json_schema={"type": "object", "properties": {"section_id": {"type": "string"}, "slides": {"type": "array"}}},
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["response_format"]["type"] == "json_object"
        assert response.provider == "deepseek"

    @patch("app.deck.services.llm_deepseek.DeepSeekProvider._get_client")
    def test_rate_limit_error(self, mock_get_client):
        from app.deck.services.llm_deepseek import DeepSeekProvider

        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
        mock_get_client.return_value = mock_client

        provider = DeepSeekProvider("test-key")
        with pytest.raises(RateLimitError):
            provider.generate_json("test", "test", {"type": "object"})


class TestGLMProvider:
    """Tests for Z.AI GLM provider with mocked API client."""

    def test_default_model(self):
        from app.deck.services.llm_glm import GLMProvider

        provider = GLMProvider("test-key")
        assert provider.get_default_model() == "glm-4.7-flash"

    def test_default_models_by_level(self):
        from app.deck.services.llm_glm import GLMProvider

        assert GLMProvider.DEFAULT_MODELS["low"] == "glm-4.7-flash"
        assert GLMProvider.DEFAULT_MODELS["medium"] == "glm-4.7-flashx"
        assert GLMProvider.DEFAULT_MODELS["high"] == "glm-4.7"

    @patch("app.deck.services.llm_glm.GLMProvider._get_client")
    def test_thinking_toggle_in_extra_body(self, mock_get_client):
        from app.deck.services.llm_glm import GLMProvider

        mock_client = MagicMock()
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock()]
        mock_completion.choices[0].message.content = '{"section_id": "test", "slides": []}'
        mock_completion.usage = MagicMock()
        mock_completion.usage.prompt_tokens = 50
        mock_completion.usage.completion_tokens = 30
        mock_completion.usage.total_tokens = 80
        mock_client.chat.completions.create.return_value = mock_completion
        mock_get_client.return_value = mock_client

        provider = GLMProvider("test-key")
        options = LLMOptions(extra={"thinking_enabled": True})
        provider.generate_json(
            "test", "test",
            {"type": "object", "properties": {"section_id": {"type": "string"}, "slides": {"type": "array"}}},
            options=options,
        )

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["extra_body"]["thinking"]["type"] == "enabled"


class TestAnthropicProvider:
    """Tests for Anthropic provider with mocked API client."""

    def test_default_model(self):
        from app.deck.services.llm_anthropic import AnthropicProvider

        provider = AnthropicProvider("test-key")
        assert provider.get_default_model() == "claude-sonnet-4-5"

    @patch("app.deck.services.llm_anthropic.AnthropicProvider._get_client")
    def test_tool_use_structured_output(self, mock_get_client):
        from app.deck.services.llm_anthropic import AnthropicProvider

        mock_client = MagicMock()
        # Simulate tool_use response block
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "deck_section"
        tool_block.input = {"section_id": "overview", "slides": []}

        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 50
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        provider = AnthropicProvider("test-key")
        response = provider.generate_json(
            "test", "test",
            {"type": "object", "properties": {"section_id": {"type": "string"}, "slides": {"type": "array"}}},
        )

        assert response.content == {"section_id": "overview", "slides": []}
        assert response.provider == "anthropic"

    @patch("app.deck.services.llm_anthropic.AnthropicProvider._get_client")
    def test_extended_thinking_config(self, mock_get_client):
        from app.deck.services.llm_anthropic import AnthropicProvider

        mock_client = MagicMock()
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "deck_section"
        tool_block.input = {"section_id": "test", "slides": []}
        mock_response = MagicMock()
        mock_response.content = [tool_block]
        mock_response.usage = MagicMock()
        mock_response.usage.input_tokens = 100
        mock_response.usage.output_tokens = 80
        mock_client.messages.create.return_value = mock_response
        mock_get_client.return_value = mock_client

        provider = AnthropicProvider("test-key")
        options = LLMOptions(extra={"thinking_enabled": True, "thinking_budget_tokens": 5000})
        provider.generate_json(
            "test", "test",
            {"type": "object", "properties": {"section_id": {"type": "string"}, "slides": {"type": "array"}}},
            options=options,
        )

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["thinking"]["type"] == "enabled"
        assert call_kwargs["thinking"]["budget_tokens"] == 5000


class TestProviderRetry:
    """Tests for retry logic with mocked providers."""
    
    def test_retry_on_validation_error(self):
        """Test retry logic when validation fails."""
        from app.deck.services.llm_openai import OpenAIProvider
        
        provider = OpenAIProvider("test-key")
        
        # Mock generate_json to return invalid then valid
        call_count = [0]
        
        def mock_generate(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                # First call - invalid response
                return LLMResponse(
                    content={"wrong": "schema"},
                    raw_response='{"wrong": "schema"}',
                    model="gpt-5.2",
                    provider="openai",
                )
            else:
                # Second call - valid response
                return LLMResponse(
                    content={"section_id": "test", "slides": []},
                    raw_response='{"section_id": "test", "slides": []}',
                    model="gpt-5.2",
                    provider="openai",
                )
        
        provider.generate_json = mock_generate
        
        schema = {
            "type": "object",
            "required": ["section_id", "slides"],
            "properties": {
                "section_id": {"type": "string"},
                "slides": {"type": "array"},
            },
        }
        
        response = provider.generate_with_retry(
            system_prompt="test",
            user_prompt="test",
            json_schema=schema,
            max_retries=2,
        )
        
        assert response.content == {"section_id": "test", "slides": []}
        assert call_count[0] == 2  # Retried once
        assert call_count[0] == 2
