"""
Anthropic LLM provider implementation.
Supports Claude Sonnet 4.5 with extended thinking via the Anthropic SDK.
"""

import json
import time
from typing import Optional

from app.deck.services.llm_base import (
    AuthenticationError,
    InvalidResponseError,
    LLMError,
    LLMOptions,
    LLMProvider,
    LLMResponse,
    RateLimitError,
    TimeoutError,
)
from app.deck.utils.logging import get_logger
from app.deck.utils.validation import sanitize_llm_output

logger = get_logger(__name__)


class AnthropicProvider(LLMProvider):
    """
    Anthropic API provider using the native anthropic SDK.

    Structured output is achieved via tool_use with a single tool whose
    input_schema matches the desired JSON schema (standard Anthropic pattern).

    Extended thinking is enabled via:
        thinking={"type": "enabled", "budget_tokens": N}
    """

    PROVIDER_NAME = "anthropic"

    DEFAULT_MODELS = {
        "low": "claude-sonnet-4-5",
        "medium": "claude-sonnet-4-5",
        "high": "claude-sonnet-4-5",
    }

    # Default thinking budget for extended thinking mode
    DEFAULT_THINKING_BUDGET = 10_000

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import anthropic

                self._client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise LLMError("anthropic package not installed. Run: pip install anthropic")
        return self._client

    def get_default_model(self) -> str:
        return "claude-sonnet-4-5"

    def _map_reasoning_level(self, level: str) -> dict:
        configs = {
            "low": {
                "max_tokens": 4096,
                "model": self.DEFAULT_MODELS["low"],
            },
            "medium": {
                "max_tokens": 8192,
                "model": self.DEFAULT_MODELS["medium"],
            },
            "high": {
                "max_tokens": 16384,
                "model": self.DEFAULT_MODELS["high"],
            },
        }
        return configs.get(level, configs["medium"])

    def _convert_to_tool_schema(self, json_schema: dict) -> dict:
        """Convert a JSON schema to an Anthropic tool input_schema.

        Anthropic's tool_use expects a standard JSON Schema in ``input_schema``.
        We add ``additionalProperties: false`` and fill in ``required`` fields so
        the response is as strict as possible.
        """
        import copy

        schema = copy.deepcopy(json_schema)
        if schema.get("type") == "object":
            schema["additionalProperties"] = False
            if "properties" in schema:
                schema["required"] = list(schema["properties"].keys())
        if "properties" in schema:
            for key, prop in schema["properties"].items():
                if isinstance(prop, dict):
                    if prop.get("type") == "object":
                        schema["properties"][key] = self._convert_to_tool_schema(prop)
                    elif prop.get("type") == "array" and "items" in prop:
                        items = prop["items"]
                        if isinstance(items, dict) and items.get("type") == "object":
                            schema["properties"][key]["items"] = self._convert_to_tool_schema(items)
        return schema

    def validate_api_key(self) -> bool:
        try:
            client = self._get_client()
            # Lightweight validation: count tokens on a tiny message
            client.messages.count_tokens(
                model="claude-sonnet-4-5",
                messages=[{"role": "user", "content": "hi"}],
            )
            return True
        except Exception as e:
            logger.warning(f"Anthropic API key validation failed: {e}")
            return False

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        options: Optional[LLMOptions] = None,
    ) -> LLMResponse:
        options = options or LLMOptions()
        client = self._get_client()

        level_config = self._map_reasoning_level(options.reasoning_level)
        model = self.get_model(options.extra.get("model"))
        if not model or model == self.get_default_model():
            model = level_config.get("model", self.get_default_model())

        max_tokens = options.max_tokens or level_config.get("max_tokens", 8192)
        tool_schema = self._convert_to_tool_schema(json_schema)

        # Build the single-tool for structured output
        tools = [
            {
                "name": "deck_section",
                "description": "Return the generated deck section as structured JSON.",
                "input_schema": tool_schema,
            }
        ]

        # Optionally enable extended thinking
        thinking_config = None
        thinking_enabled = options.extra.get("thinking_enabled", False)
        budget = options.extra.get("thinking_budget_tokens", self.DEFAULT_THINKING_BUDGET)
        if thinking_enabled:
            thinking_config = {"type": "enabled", "budget_tokens": budget}
            # Anthropic requires max_tokens >= budget_tokens
            max_tokens = max(max_tokens, budget + 2048)

        try:
            start_time = time.time()
            logger.info("Calling Anthropic API", extra={
                "model": model,
                "max_tokens": max_tokens,
                "thinking": thinking_enabled,
            })

            create_kwargs: dict = dict(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=tools,
            )
            if thinking_config:
                create_kwargs["thinking"] = thinking_config
                # With extended thinking, Anthropic requires temp=1
                create_kwargs["temperature"] = 1.0
                # Anthropic forbids forced tool_choice with thinking;
                # use "auto" so the model still tends to call the tool.
                create_kwargs["tool_choice"] = {"type": "auto"}
            else:
                # Without thinking we can safely force the tool
                create_kwargs["tool_choice"] = {"type": "tool", "name": "deck_section"}

            response = client.messages.create(**create_kwargs)

            latency_ms = (time.time() - start_time) * 1000

            # Extract the tool_use block
            parsed_content = None
            raw_content = ""
            for block in response.content:
                if getattr(block, "type", None) == "tool_use" and block.name == "deck_section":
                    parsed_content = block.input
                    raw_content = json.dumps(parsed_content)
                    break

            if parsed_content is None:
                # Fallback: try to parse text blocks
                text_parts = [
                    b.text for b in response.content if getattr(b, "type", None) == "text"
                ]
                raw_content = "\n".join(text_parts)
                try:
                    parsed_content = json.loads(raw_content)
                except (json.JSONDecodeError, ValueError):
                    parsed_content = sanitize_llm_output(raw_content)
                    if parsed_content is None:
                        raise InvalidResponseError(
                            f"Anthropic did not return tool_use block: {raw_content[:200]}"
                        )

            # Build usage stats
            usage: dict = {}
            if response.usage:
                usage = {
                    "prompt_tokens": response.usage.input_tokens,
                    "completion_tokens": response.usage.output_tokens,
                    "total_tokens": response.usage.input_tokens + response.usage.output_tokens,
                }

            logger.info("Anthropic generation complete", extra={
                "model": model,
                "latency_ms": round(latency_ms, 2),
                "tokens": usage.get("total_tokens"),
            })

            return LLMResponse(
                content=parsed_content,
                raw_response=raw_content,
                model=model,
                provider=self.PROVIDER_NAME,
                usage=usage,
                latency_ms=latency_ms,
            )

        except Exception as e:
            error_str = str(e).lower()

            if "rate limit" in error_str or "rate_limit" in error_str or "overloaded" in error_str:
                retry_after = None
                if hasattr(e, "response") and e.response:
                    retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(str(e), retry_after)

            if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
                raise AuthenticationError(f"Anthropic authentication failed: {e}")

            if "timeout" in error_str:
                raise TimeoutError(f"Anthropic request timed out: {e}")

            logger.error(f"Anthropic API error: {e}", exc_info=True)
            raise LLMError(f"Anthropic API error: {e}")
