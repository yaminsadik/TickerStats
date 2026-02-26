"""
DeepSeek LLM provider implementation.
Uses the OpenAI-compatible API at https://api.deepseek.com.
Supports DeepSeek V3.2 via deepseek-chat (non-thinking) and deepseek-reasoner (thinking).
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

DEEPSEEK_BASE_URL = "https://api.deepseek.com"


class DeepSeekProvider(LLMProvider):
    """
    DeepSeek API provider (OpenAI-compatible).

    Thinking mode is model-level:
    - deepseek-chat  = V3.2 non-thinking
    - deepseek-reasoner = V3.2 thinking
    """

    PROVIDER_NAME = "deepseek"

    DEFAULT_MODELS = {
        "low": "deepseek-chat",
        "medium": "deepseek-chat",  # prefer chat (faster) over reasoner for medium
        "high": "deepseek-reasoner",
    }

    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._client = None

    def _get_client(self):
        """Lazy-initialise OpenAI client pointed at DeepSeek."""
        if self._client is None:
            try:
                from openai import OpenAI

                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=DEEPSEEK_BASE_URL,
                )
            except ImportError:
                raise LLMError("openai package not installed. Run: pip install openai")
        return self._client

    def get_default_model(self) -> str:
        return "deepseek-chat"

    def _map_reasoning_level(self, level: str) -> dict:
        configs = {
            "low": {
                "temperature": 1.0,
                "max_tokens": 4096,
                "model": self.DEFAULT_MODELS["low"],
            },
            "medium": {
                "temperature": 1.0,
                "max_tokens": 6144,
                "model": self.DEFAULT_MODELS["medium"],
            },
            "high": {
                "temperature": 1.0,
                "max_tokens": 16384,
                "model": self.DEFAULT_MODELS["high"],
            },
        }
        return configs.get(level, configs["medium"])

    # ------------------------------------------------------------------
    # Schema helpers (same strict-schema approach as OpenAI)
    # ------------------------------------------------------------------

    def _convert_to_strict_schema(self, schema: dict) -> dict:
        """
        Convert schema to strict format with additionalProperties: false
        at ALL levels including $defs.
        """
        import copy

        strict_schema = copy.deepcopy(schema)
        
        # Process $defs first (Pydantic puts reusable schemas here)
        if "$defs" in strict_schema:
            for def_name, def_schema in strict_schema["$defs"].items():
                if isinstance(def_schema, dict):
                    strict_schema["$defs"][def_name] = self._process_schema_node(def_schema)
        
        # Process the root schema
        return self._process_schema_node(strict_schema)
    
    def _process_schema_node(self, node: dict) -> dict:
        """
        Recursively process a schema node to add additionalProperties: false
        at every object level.
        """
        import copy
        processed = copy.deepcopy(node)
        
        # Add additionalProperties: false to all objects
        if processed.get("type") == "object":
            processed["additionalProperties"] = False
            # Make all properties required for strict mode
            if "properties" in processed:
                processed["required"] = list(processed["properties"].keys())
        
        # Recursively process nested structures
        if "properties" in processed:
            for key, prop in processed["properties"].items():
                if isinstance(prop, dict) and "$ref" not in prop:
                    processed["properties"][key] = self._process_schema_node(prop)
        
        # Process array items
        if "items" in processed and isinstance(processed["items"], dict):
            if "$ref" not in processed["items"]:
                processed["items"] = self._process_schema_node(processed["items"])
        
        # Process anyOf, allOf, oneOf constructs
        for key in ["anyOf", "allOf", "oneOf"]:
            if key in processed and isinstance(processed[key], list):
                processed[key] = [
                    self._process_schema_node(item) if isinstance(item, dict) and "$ref" not in item else item
                    for item in processed[key]
                ]
        
        return processed

    def _build_response_format(self, schema: dict) -> dict:
        """DeepSeek currently supports ``json_object`` reliably.

        Some DeepSeek accounts reject ``json_schema`` with:
        "This response_format type is unavailable now".
        We keep strict schema validation on our side via generate_with_retry.
        """
        _ = schema  # retained for interface symmetry / future use
        return {"type": "json_object"}

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def validate_api_key(self) -> bool:
        try:
            client = self._get_client()
            client.models.list()
            return True
        except Exception as e:
            logger.warning(f"DeepSeek API key validation failed: {e}")
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

        try:
            start_time = time.time()
            logger.info("Calling DeepSeek API", extra={"model": model, "max_tokens": max_tokens})

            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
                response_format=self._build_response_format(strict_schema),
                timeout=options.timeout,
            )

            latency_ms = (time.time() - start_time) * 1000
            raw_content = completion.choices[0].message.content

            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError as e:
                logger.error(f"JSON parse error from DeepSeek: {e}")
                parsed_content = sanitize_llm_output(raw_content)
                if parsed_content is None:
                    raise InvalidResponseError(
                        f"Failed to parse JSON from DeepSeek response: {raw_content[:200]}"
                    )

            usage: dict = {}
            if completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                }
                if hasattr(completion.usage, "completion_tokens_details"):
                    details = completion.usage.completion_tokens_details
                    if details and hasattr(details, "reasoning_tokens"):
                        usage["reasoning_tokens"] = details.reasoning_tokens

            logger.info("DeepSeek generation complete", extra={
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

            if "rate limit" in error_str or "rate_limit" in error_str:
                retry_after = None
                if hasattr(e, "response") and e.response:
                    retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(str(e), retry_after)

            if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
                raise AuthenticationError(f"DeepSeek authentication failed: {e}")

            if "timeout" in error_str:
                raise TimeoutError(f"DeepSeek request timed out: {e}")

            logger.error(f"DeepSeek API error: {e}", exc_info=True)
            raise LLMError(f"DeepSeek API error: {e}")
