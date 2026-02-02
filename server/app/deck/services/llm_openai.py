"""
OpenAI LLM provider implementation.
Supports GPT-5.2 with Structured Outputs for guaranteed schema-conformant JSON.
"""

import json
import time
from typing import Any, Optional

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


class OpenAIProvider(LLMProvider):
    """
    OpenAI API provider with Structured Outputs support.
    Uses GPT-5.2 with native JSON Schema enforcement.
    """
    
    PROVIDER_NAME = "openai"
    
    # Default models by reasoning level - GPT-5 family
    DEFAULT_MODELS = {
        "low": "gpt-5-nano",
        "medium": "gpt-5-mini",
        "high": "gpt-5.1",
    }
    
    # Reasoning effort mapping for GPT-5.2
    REASONING_EFFORT = {
        "low": "low",
        "medium": "medium",
        "high": "high",
    }
    
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._client = None
    
    def _get_client(self):
        """Lazy initialize OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise LLMError("openai package not installed. Run: pip install openai")
        return self._client
    
    def get_default_model(self) -> str:
        return "gpt-5-mini"
    
    def _map_reasoning_level(self, level: str) -> dict:
        """Map reasoning level to OpenAI-specific parameters."""
        configs = {
            "low": {
                "temperature": 1.0,  # Structured Outputs work best with temperature=1
                "max_tokens": 4096,
                "model": self.DEFAULT_MODELS["low"],
                "reasoning_effort": self.REASONING_EFFORT["low"],
            },
            "medium": {
                "temperature": 1.0,
                "max_tokens": 8192,
                "model": self.DEFAULT_MODELS["medium"],
                "reasoning_effort": self.REASONING_EFFORT["medium"],
            },
            "high": {
                "temperature": 1.0,
                "max_tokens": 16384,
                "model": self.DEFAULT_MODELS["high"],
                "reasoning_effort": self.REASONING_EFFORT["high"],
            },
        }
        return configs.get(level, configs["medium"])
    
    def _convert_to_strict_schema(self, schema: dict) -> dict:
        """
        Convert a JSON schema to OpenAI's strict schema format.
        Ensures additionalProperties: false and all properties required.
        """
        import copy
        strict_schema = copy.deepcopy(schema)
        
        if strict_schema.get("type") == "object":
            strict_schema["additionalProperties"] = False
            # Make all properties required for strict mode
            if "properties" in strict_schema:
                strict_schema["required"] = list(strict_schema["properties"].keys())
        
        # Recursively handle nested structures
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
        """Validate OpenAI API key by making a simple request."""
        try:
            client = self._get_client()
            # Use models.list as a lightweight validation
            client.models.list()
            return True
        except Exception as e:
            logger.warning(f"OpenAI API key validation failed: {e}")
            return False
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        options: Optional[LLMOptions] = None,
    ) -> LLMResponse:
        """
        Generate JSON using OpenAI API with Structured Outputs.
        Uses response_format with json_schema for guaranteed schema compliance.
        """
        options = options or LLMOptions()
        client = self._get_client()
        
        # Apply reasoning level settings
        level_config = self._map_reasoning_level(options.reasoning_level)
        
        # Determine model
        model = self.get_model(options.extra.get("model"))
        if not model or model == self.get_default_model():
            model = level_config.get("model", self.get_default_model())
        
        max_tokens = options.max_tokens or level_config.get("max_tokens", 8192)
        reasoning_effort = level_config.get("reasoning_effort", "medium")
        
        # Build messages - no need to include schema in prompt with Structured Outputs
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        # Prepare strict schema for Structured Outputs
        strict_schema = self._convert_to_strict_schema(json_schema)
        
        try:
            start_time = time.time()
            
            logger.info(f"Calling OpenAI API with Structured Outputs", extra={
                "model": model,
                "max_tokens": max_tokens,
                "reasoning_effort": reasoning_effort,
            })
            
            # Use Structured Outputs with json_schema response format
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=max_tokens,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "deck_section",
                        "strict": True,
                        "schema": strict_schema,
                    },
                },
                timeout=options.timeout,
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract response - Structured Outputs guarantees valid JSON
            raw_content = completion.choices[0].message.content
            
            # Parse JSON (should never fail with Structured Outputs)
            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError as e:
                # This should be extremely rare with Structured Outputs
                logger.error(f"JSON parse error despite Structured Outputs: {e}")
                parsed_content = sanitize_llm_output(raw_content)
                if parsed_content is None:
                    raise InvalidResponseError(
                        f"Failed to parse JSON from OpenAI response: {raw_content[:200]}"
                    )
            
            # Build usage stats
            usage = {}
            if completion.usage:
                usage = {
                    "prompt_tokens": completion.usage.prompt_tokens,
                    "completion_tokens": completion.usage.completion_tokens,
                    "total_tokens": completion.usage.total_tokens,
                }
                # Include reasoning tokens if available
                if hasattr(completion.usage, "completion_tokens_details"):
                    details = completion.usage.completion_tokens_details
                    if hasattr(details, "reasoning_tokens"):
                        usage["reasoning_tokens"] = details.reasoning_tokens
            
            logger.info(f"OpenAI generation complete", extra={
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
            
        except ImportError:
            raise LLMError("openai package not installed")
        except Exception as e:
            error_str = str(e).lower()
            
            # Map to specific error types
            if "rate limit" in error_str or "rate_limit" in error_str:
                # Try to extract retry-after
                retry_after = None
                if hasattr(e, "response") and e.response:
                    retry_after = e.response.headers.get("retry-after")
                raise RateLimitError(str(e), retry_after)
            
            if "authentication" in error_str or "api key" in error_str or "unauthorized" in error_str:
                raise AuthenticationError(f"OpenAI authentication failed: {e}")
            
            if "timeout" in error_str:
                raise TimeoutError(f"OpenAI request timed out: {e}")
            
            # Generic error
            logger.error(f"OpenAI API error: {e}", exc_info=True)
            raise LLMError(f"OpenAI API error: {e}")
