"""
Z.AI GLM LLM provider implementation.
Uses the OpenAI-compatible API at https://open.bigmodel.cn/api/paas/v4.
Supports GLM-4.7-flash (free), GLM-4.7-flashx, GLM-4.7, and GLM-5.
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

ZAI_BASE_URL = "https://open.bigmodel.cn/api/paas/v4"


class GLMProvider(LLMProvider):
    """
    Z.AI GLM API provider (OpenAI-compatible).

    Thinking mode is controlled via an extra body parameter:
        thinking={"type": "enabled"} or thinking={"type": "disabled"}
    """

    PROVIDER_NAME = "zai"

    DEFAULT_MODELS = {
        "low": "glm-4.7-flash",
        "medium": "glm-4.7-flashx",
        "high": "glm-4.7",
    }

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=ZAI_BASE_URL,
                )
            except ImportError:
                raise LLMError("openai package not installed. Run: pip install openai")
        return self._client

    def get_default_model(self) -> str:
        return "glm-4.7-flash"

    def _map_reasoning_level(self, level: str) -> dict:
        configs = {
            "low": {
                "temperature": 1.0,
                "max_tokens": 4096,
                "model": self.DEFAULT_MODELS["low"],
            },
            "medium": {
                "temperature": 1.0,
                "max_tokens": 8192,
                "model": self.DEFAULT_MODELS["medium"],
            },
            "high": {
                "temperature": 1.0,
                "max_tokens": 16384,
                "model": self.DEFAULT_MODELS["high"],
            },
        }
        return configs.get(level, configs["medium"])

    def _convert_to_strict_schema(self, schema: dict) -> dict:
        import copy

        strict_schema = copy.deepcopy(schema)
        if strict_schema.get("type") == "object":
            strict_schema["additionalProperties"] = False
            if "properties" in strict_schema:
                strict_schema["required"] = list(strict_schema["properties"].keys())
        if "properties" in strict_schema:
            for key, prop in strict_schema["properties"].items():
                if isinstance(prop, dict):
                    if prop.get("type") == "object":
                        strict_schema["properties"][key] = self._convert_to_strict_schema(prop)
                    elif prop.get("type") == "array" and "items" in prop:
                        if isinstance(prop["items"], dict) and prop["items"].get("type") == "object":
                            strict_schema["properties"][key]["items"] = self._convert_to_strict_schema(prop["items"])
        return strict_schema

    def validate_api_key(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception as e:
            logger.warning(f"Z.AI API key validation failed: {e}")
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

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        strict_schema = self._convert_to_strict_schema(json_schema)

        # Build extra_body for thinking control
        extra_body: dict = {}
        thinking_enabled = options.extra.get("thinking_enabled", False)
        if thinking_enabled:
            extra_body["thinking"] = {"type": "enabled"}
        else:
            extra_body["thinking"] = {"type": "disabled"}

        try:
            start_time = time.time()
            logger.info("Calling Z.AI GLM API", extra={"model": model, "max_tokens": max_tokens})

            create_kwargs: dict = dict(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=options.timeout,
            )
            if extra_body:
                create_kwargs["extra_body"] = extra_body

            completion = client.chat.completions.create(**create_kwargs)

            latency_ms = (time.time() - start_time) * 1000
            raw_content = completion.choices[0].message.content

            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error from Z.AI GLM: {e}")
                parsed_content = sanitize_llm_output(raw_content)
                if parsed_content is None:
                    raise InvalidResponseError(
                        f"Failed to parse JSON from GLM response: {raw_content[:200]}"
                    )

            usage: dict = {}
            if completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                }

            logger.info("Z.AI GLM generation complete", extra={
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

            if "rate limit" in error_str or "rate_limit" in error_str or "quota" in error_str or "1302" in error_str:
                retry_after = None
                if hasattr(e, "response") and e.response:
                    retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(str(e), retry_after)

            if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
                raise AuthenticationError(f"Z.AI authentication failed: {e}")

            if "timeout" in error_str:
                raise TimeoutError(f"Z.AI request timed out: {e}")

            logger.error(f"Z.AI GLM API error: {e}", exc_info=True)
            raise LLMError(f"Z.AI GLM API error: {e}")
