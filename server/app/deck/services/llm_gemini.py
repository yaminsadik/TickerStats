"""
Google Gemini LLM provider implementation.
Supports Gemini through the official Google Gen AI SDK. In production this is
intended to run against Vertex AI so usage bills through the configured Google
Cloud project instead of the Gemini Developer API / AI Studio quota path.
"""

import copy
import json
import time
from typing import Any, Optional

from app.core.config import settings
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


class GeminiProvider(LLMProvider):
    """
    Google Gemini provider with Structured Outputs support.

    When GOOGLE_GENAI_USE_VERTEXAI=true, authentication is handled by
    Application Default Credentials / service account identity and no Gemini API
    key is required. If Vertex mode is disabled, this can still use a Developer
    API key as a legacy fallback.
    """
    
    PROVIDER_NAME = "gemini"
    
    # Default models by reasoning level - Vertex AI Gemini 2.5 family
    DEFAULT_MODELS = {
        "low": "gemini-3-flash-preview",
        "medium": "gemini-3.1-pro-preview",
        "high": "gemini-3.1-pro-preview",
    }
    
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._client = None

    def _use_vertex(self) -> bool:
        return bool(settings.GOOGLE_GENAI_USE_VERTEXAI)

    def _get_client(self):
        """Create the Gen AI client for Vertex AI or legacy API-key mode."""
        if self._client is not None:
            return self._client

        try:
            from google import genai
        except ImportError:
            raise LLMError(
                "google-genai package not installed. Run: pip install google-genai"
            )

        if self._use_vertex():
            if not settings.GOOGLE_CLOUD_PROJECT or not settings.GOOGLE_CLOUD_LOCATION:
                raise AuthenticationError(
                    "Vertex Gemini requires GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION"
                )
            self._client = genai.Client(
                vertexai=True,
                project=settings.GOOGLE_CLOUD_PROJECT,
                location=settings.GOOGLE_CLOUD_LOCATION,
            )
        else:
            if not self.api_key:
                raise AuthenticationError(
                    "Gemini Developer API mode requires GEMINI_API_KEY or GOOGLE_API_KEY"
                )
            self._client = genai.Client(api_key=self.api_key)

        return self._client
    
    def get_default_model(self) -> str:
        return settings.VERTEX_GEMINI_DEFAULT_MODEL or "gemini-3-flash-preview"
    
    def _map_reasoning_level(self, level: str) -> dict:
        """Map reasoning level to Gemini-specific parameters."""
        configs = {
            "low": {
                "temperature": 1.0,  # Structured Outputs work best with temperature=1
                "max_output_tokens": 8192,  # Increased from 4096 to avoid truncation
                "model": self.DEFAULT_MODELS["low"],
            },
            "medium": {
                "temperature": 1.0,
                "max_output_tokens": 16384,  # Increased from 8192 to avoid truncation
                "model": self.DEFAULT_MODELS["medium"],
            },
            "high": {
                "temperature": 1.0,
                "max_output_tokens": 32768,  # Increased from 16384 to avoid truncation
                "model": self.DEFAULT_MODELS["high"],
            },
        }
        return configs.get(level, configs["medium"])
    
    def validate_api_key(self) -> bool:
        """Validate Gemini connectivity."""
        try:
            client = self._get_client()
            client.models.generate_content(
                model=self.get_default_model(),
                contents="Return ok.",
                config={"max_output_tokens": 8},
            )
            return True
        except Exception as e:
            logger.warning(f"Gemini validation failed: {e}")
            return False
    
    def _convert_to_gemini_schema(self, json_schema: dict) -> dict:
        """
        Convert JSON schema to Gemini's response_schema format.
        Gemini uses a similar but slightly different schema format.
        """
        type_mapping = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }

        defs = json_schema.get("$defs", {}) if isinstance(json_schema, dict) else {}
        normalized_root = self._normalize_schema_node(json_schema, defs, set())

        def convert_type(prop: dict) -> dict:
            prop = self._normalize_schema_node(prop, defs, set())
            prop_type = self._infer_json_type(prop)

            result: dict[str, Any] = {
                "type": type_mapping.get(prop_type, "STRING")
            }

            if "description" in prop:
                result["description"] = prop["description"]

            if "enum" in prop and isinstance(prop["enum"], list):
                result["enum"] = prop["enum"]

            if prop_type == "array":
                items = prop.get("items", {"type": "string"})
                result["items"] = convert_type(items if isinstance(items, dict) else {"type": "string"})

            if prop_type == "object":
                properties = prop.get("properties", {})
                if isinstance(properties, dict):
                    result["properties"] = {
                        key: convert_type(value if isinstance(value, dict) else {"type": "string"})
                        for key, value in properties.items()
                    }
                    required = prop.get("required")
                    if isinstance(required, list):
                        result["required"] = required
                    else:
                        # Gemini SDK may reject object schemas without required.
                        result["required"] = list(properties.keys())
                else:
                    result["properties"] = {}
                    result["required"] = []

            return result

        return convert_type(normalized_root)

    def _resolve_schema_refs(
        self,
        node: Any,
        defs: dict[str, Any],
        visited: set[str],
    ) -> Any:
        """Resolve local #/$defs refs recursively."""
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                def_name = ref.split("/")[-1]
                if def_name in visited:
                    # Defensive break for recursive definitions.
                    return {"type": "object", "properties": {}, "required": []}
                target = defs.get(def_name)
                if isinstance(target, dict):
                    merged = copy.deepcopy(target)
                    for key, value in node.items():
                        if key != "$ref":
                            merged[key] = value
                    return self._resolve_schema_refs(merged, defs, visited | {def_name})
            return {
                key: self._resolve_schema_refs(value, defs, visited)
                for key, value in node.items()
                if key != "$defs"
            }
        if isinstance(node, list):
            return [self._resolve_schema_refs(item, defs, visited) for item in node]
        return node

    def _collapse_schema_combinators(self, node: dict[str, Any]) -> dict[str, Any]:
        """Collapse common anyOf/oneOf/allOf patterns into a concrete schema."""
        normalized = copy.deepcopy(node)

        if "allOf" in normalized and isinstance(normalized["allOf"], list):
            merged: dict[str, Any] = {}
            for item in normalized["allOf"]:
                if isinstance(item, dict):
                    merged.update(self._collapse_schema_combinators(item))
            for key, value in normalized.items():
                if key != "allOf":
                    merged[key] = value
            normalized = merged

        for key in ("anyOf", "oneOf"):
            choices = normalized.get(key)
            if not isinstance(choices, list):
                continue
            non_null = []
            for choice in choices:
                if isinstance(choice, dict) and choice.get("type") == "null":
                    continue
                non_null.append(choice)
            if len(non_null) == 1 and isinstance(non_null[0], dict):
                chosen = self._collapse_schema_combinators(non_null[0])
                for merge_key, merge_value in normalized.items():
                    if merge_key != key and merge_key not in chosen:
                        chosen[merge_key] = merge_value
                normalized = chosen

        return normalized

    def _normalize_schema_node(
        self,
        node: Any,
        defs: dict[str, Any],
        visited: set[str],
    ) -> dict[str, Any]:
        """Normalize schema node by resolving refs and common combinators."""
        if not isinstance(node, dict):
            return {"type": "string"}

        resolved = self._resolve_schema_refs(node, defs, visited)
        if not isinstance(resolved, dict):
            return {"type": "string"}

        resolved = self._collapse_schema_combinators(resolved)
        node_type = resolved.get("type")
        if isinstance(node_type, list):
            non_null = [item for item in node_type if item != "null"]
            if non_null:
                resolved["type"] = non_null[0]
            else:
                resolved["type"] = "string"
        return resolved

    def _infer_json_type(self, schema: dict[str, Any]) -> str:
        """Infer concrete type when schema omits explicit `type`."""
        schema_type = schema.get("type")
        if isinstance(schema_type, str):
            return schema_type
        if isinstance(schema_type, list):
            non_null = [item for item in schema_type if item != "null"]
            if non_null:
                return str(non_null[0])
        if isinstance(schema.get("properties"), dict):
            return "object"
        if "items" in schema:
            return "array"
        if isinstance(schema.get("enum"), list) and schema["enum"]:
            enum_value = schema["enum"][0]
            if isinstance(enum_value, bool):
                return "boolean"
            if isinstance(enum_value, int):
                return "integer"
            if isinstance(enum_value, float):
                return "number"
            return "string"
        return "string"

    def _normalize_finish_reason(self, finish_reason: Any) -> str:
        """Normalize Gemini finish reason values across SDK versions."""
        int_map = {
            0: "UNSPECIFIED",
            1: "STOP",
            2: "MAX_TOKENS",
            3: "SAFETY",
            4: "RECITATION",
        }
        if isinstance(finish_reason, int):
            return int_map.get(finish_reason, str(finish_reason))
        if hasattr(finish_reason, "name"):
            return str(finish_reason.name).upper()
        text = str(finish_reason or "").strip()
        if text.isdigit():
            return int_map.get(int(text), text)
        return text.upper()

    def _extract_response_text(self, response: Any, candidate: Any) -> str:
        """Extract response text robustly across Gemini SDK response shapes."""
        text = getattr(response, "text", None)
        if isinstance(text, str) and text.strip():
            return text

        parts = getattr(getattr(candidate, "content", None), "parts", None)
        if isinstance(parts, list):
            chunks: list[str] = []
            for part in parts:
                chunk = getattr(part, "text", None)
                if isinstance(chunk, str) and chunk.strip():
                    chunks.append(chunk)
            if chunks:
                return "\n".join(chunks)
        return ""

    def _get_model_output_cap(self, model_name: str) -> int:
        """Get provider catalog max output tokens for the selected Gemini model."""
        try:
            from app.deck.services.model_catalog import get_model_by_id

            model_def = get_model_by_id(model_name)
            if model_def and model_def.max_output:
                return int(model_def.max_output)
        except Exception:
            pass
        return 65_536
    
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        options: Optional[LLMOptions] = None,
    ) -> LLMResponse:
        """
        Generate JSON using Gemini API with Structured Outputs.
        Uses response_schema for guaranteed schema compliance.
        """
        client = self._get_client()
        
        options = options or LLMOptions()
        
        # Apply reasoning level settings
        level_config = self._map_reasoning_level(options.reasoning_level)
        
        # Determine model
        model_name = self.get_model(options.extra.get("model"))
        if not model_name or model_name == self.get_default_model():
            model_name = level_config.get("model", self.get_default_model())
        
        # Keep Gemini output budget at least at the provider's reasoning default.
        # LLMOptions.max_tokens currently defaults to 4096 for compatibility, which
        # is too low for many section schemas on Gemini.
        level_max_tokens = int(level_config.get("max_output_tokens", 8192))
        requested_max_tokens = int(options.max_tokens or 0)
        model_output_cap = self._get_model_output_cap(model_name)
        max_tokens = min(max(level_max_tokens, requested_max_tokens), model_output_cap)
        thinking_level = options.extra.get("thinking_level")
        active_thinking_level = str(thinking_level).lower() if thinking_level else None
        
        # Convert JSON schema to Gemini format
        gemini_schema = self._convert_to_gemini_schema(json_schema)
        
        # Build prompt without schema instructions (schema is enforced by API)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        try:
            start_time = time.time()
            response: Any = None
            raw_content = ""
            parsed_content: Any = None
            finish_reason = ""
            current_max_tokens = max_tokens
            max_internal_attempts = 3  # escalate budget up to model cap on truncation

            for attempt in range(max_internal_attempts):
                generation_config: dict[str, Any] = {
                    "temperature": 1.0,  # Structured Outputs work best with temp=1
                    "max_output_tokens": current_max_tokens,
                    "response_mime_type": "application/json",
                    "response_json_schema": gemini_schema,  # Native Structured Outputs
                }

                logger.info("Calling Gemini API with Structured Outputs", extra={
                    "model": model_name,
                    "max_tokens": current_max_tokens,
                    "thinking_level": active_thinking_level,
                    "attempt": attempt + 1,
                    "vertex": self._use_vertex(),
                })

                response = client.models.generate_content(
                    model=model_name,
                    contents=full_prompt,
                    config=generation_config,
                )

                if not response.candidates:
                    raise InvalidResponseError("No candidates in Gemini response")

                candidate = response.candidates[0]
                finish_reason = self._normalize_finish_reason(
                    getattr(candidate, "finish_reason", None)
                )

                if finish_reason == "SAFETY":
                    raise InvalidResponseError("Gemini blocked response due to safety filters")
                if finish_reason == "RECITATION":
                    logger.warning(
                        "Gemini flagged response as RECITATION; attempting parse of partial content"
                    )

                raw_content = self._extract_response_text(response, candidate)
                if not raw_content.strip():
                    if attempt < (max_internal_attempts - 1):
                        next_tokens = min(
                            model_output_cap,
                            max(current_max_tokens * 2, current_max_tokens + 4096),
                        )
                        logger.warning(
                            "Gemini returned empty content; retrying structured-output request",
                            extra={
                                "finish_reason": finish_reason,
                                "current_max_tokens": current_max_tokens,
                                "next_max_tokens": next_tokens,
                            },
                        )
                        current_max_tokens = next_tokens
                        if active_thinking_level in {"high", "medium"}:
                            active_thinking_level = "low"
                        continue
                    raise InvalidResponseError(
                        "Gemini returned empty content despite structured-output request "
                        f"(finish_reason={finish_reason or 'unknown'})"
                    )

                # Parse JSON (should rarely fail with structured outputs).
                try:
                    parsed_content = json.loads(raw_content)
                except json.JSONDecodeError:
                    parsed_content = sanitize_llm_output(raw_content)
                    if parsed_content is None:
                        can_retry_for_tokens = (
                            finish_reason == "MAX_TOKENS"
                            and attempt < (max_internal_attempts - 1)
                            and current_max_tokens < model_output_cap
                        )
                        if can_retry_for_tokens:
                            next_tokens = min(
                                model_output_cap,
                                max(current_max_tokens * 2, current_max_tokens + 4096),
                            )
                            logger.warning(
                                "Gemini returned incomplete JSON at token limit; retrying with larger budget",
                                extra={
                                    "current_max_tokens": current_max_tokens,
                                    "next_max_tokens": next_tokens,
                                },
                            )
                            current_max_tokens = next_tokens
                            if active_thinking_level in {"high", "medium"}:
                                active_thinking_level = "low"
                            continue
                        if finish_reason == "MAX_TOKENS":
                            raise InvalidResponseError(
                                "Gemini hit token limit and produced incomplete JSON."
                            )
                        raise InvalidResponseError(
                            f"Failed to parse JSON from Gemini response: {raw_content[:200]}"
                        )

                # Even if parse succeeded, MAX_TOKENS can still indicate clipped output.
                can_retry_for_tokens = (
                    finish_reason == "MAX_TOKENS"
                    and attempt < (max_internal_attempts - 1)
                    and current_max_tokens < model_output_cap
                )
                if can_retry_for_tokens:
                    next_tokens = min(
                        model_output_cap,
                        max(current_max_tokens * 2, current_max_tokens + 4096),
                    )
                    logger.warning(
                        "Gemini ended with MAX_TOKENS; retrying once with larger output budget",
                        extra={
                            "current_max_tokens": current_max_tokens,
                            "next_max_tokens": next_tokens,
                        },
                    )
                    current_max_tokens = next_tokens
                    if active_thinking_level in {"high", "medium"}:
                        active_thinking_level = "low"
                    continue

                # Successful parse + acceptable finish reason.
                break

            latency_ms = (time.time() - start_time) * 1000

            if parsed_content is None:
                raise InvalidResponseError(
                    "Gemini did not return parseable JSON after retry."
                )

            usage = {}
            if response is not None and hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = {
                    "prompt_tokens": getattr(response.usage_metadata, "prompt_token_count", 0),
                    "completion_tokens": getattr(response.usage_metadata, "candidates_token_count", 0),
                    "total_tokens": getattr(response.usage_metadata, "total_token_count", 0),
                }
            
            logger.info(f"Gemini generation complete", extra={
                "model": model_name,
                "latency_ms": round(latency_ms, 2),
                "tokens": usage.get("total_tokens"),
            })
            
            return LLMResponse(
                content=parsed_content,
                raw_response=raw_content,
                model=model_name,
                provider=self.PROVIDER_NAME,
                usage=usage,
                latency_ms=latency_ms,
            )
            
        except Exception as e:
            if isinstance(e, LLMError):
                raise

            error_str = str(e).lower()
            
            # Map to specific error types
            if "quota" in error_str or "rate" in error_str or "resource exhausted" in error_str:
                raise RateLimitError(str(e))
            
            if "api key" in error_str or "authentication" in error_str or "permission" in error_str:
                raise AuthenticationError(f"Gemini authentication failed: {e}")
            
            if "timeout" in error_str or "deadline" in error_str:
                raise TimeoutError(f"Gemini request timed out: {e}")
            
            # Check for safety blocks
            if "blocked" in error_str or "safety" in error_str:
                raise InvalidResponseError(f"Gemini content blocked by safety filters: {e}")
            
            # Generic error
            logger.error(f"Gemini API error: {e}", exc_info=True)
            raise LLMError(f"Gemini API error: {e}")
