"""
Google Gemini LLM provider implementation.
Supports Gemini 3 Flash Preview with Structured Outputs for guaranteed schema-conformant JSON.
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


class GeminiProvider(LLMProvider):
    """
    Google Gemini API provider with Structured Outputs support.
    Uses Gemini 3 Flash Preview with native JSON Schema enforcement.
    """
    
    PROVIDER_NAME = "gemini"
    
    # Default models by reasoning level - Gemini 3 family
    DEFAULT_MODELS = {
        "low": "gemini-3-flash-preview",
        "medium": "gemini-3-flash-preview",
        "high": "gemini-3-flash-preview",
    }
    
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        super().__init__(api_key, default_model)
        self._configured = False
    
    def _configure(self):
        """Configure the Gemini API."""
        if self._configured:
            return
        
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self._configured = True
        except ImportError:
            raise LLMError(
                "google-generativeai package not installed. "
                "Run: pip install google-generativeai"
            )
    
    def get_default_model(self) -> str:
        return "gemini-3-flash-preview"
    
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
        """Validate Gemini API key."""
        try:
            self._configure()
            import google.generativeai as genai
            
            # Try listing models as a simple validation
            list(genai.list_models())
            return True
        except Exception as e:
            logger.warning(f"Gemini API key validation failed: {e}")
            return False
    
    def _convert_to_gemini_schema(self, json_schema: dict) -> dict:
        """
        Convert JSON schema to Gemini's response_schema format.
        Gemini uses a similar but slightly different schema format.
        """
        # Gemini requires explicit type mappings
        type_mapping = {
            "string": "STRING",
            "number": "NUMBER",
            "integer": "INTEGER",
            "boolean": "BOOLEAN",
            "array": "ARRAY",
            "object": "OBJECT",
        }
        
        def convert_type(prop: dict) -> dict:
            result = {}
            prop_type = prop.get("type", "string")
            if isinstance(prop_type, list):
                # Prefer non-null type when schema uses unions like ["string", "null"]
                non_null = [t for t in prop_type if t != "null"]
                prop_type = non_null[0] if non_null else "string"
            result["type"] = type_mapping.get(prop_type, "STRING")
            
            if "description" in prop:
                result["description"] = prop["description"]
            
            if prop_type == "array" and "items" in prop:
                result["items"] = convert_type(prop["items"])
            
            if prop_type == "object" and "properties" in prop:
                result["properties"] = {
                    k: convert_type(v) for k, v in prop["properties"].items()
                }
                if "required" in prop:
                    result["required"] = prop["required"]
            
            if "enum" in prop:
                result["enum"] = prop["enum"]
            
            return result
        
        return convert_type(json_schema)
    
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
        self._configure()
        
        try:
            import google.generativeai as genai
            from google.generativeai.types import GenerationConfig
        except ImportError:
            raise LLMError("google-generativeai package not installed")
        
        options = options or LLMOptions()
        
        # Apply reasoning level settings
        level_config = self._map_reasoning_level(options.reasoning_level)
        
        # Determine model
        model_name = self.get_model(options.extra.get("model"))
        if not model_name or model_name == self.get_default_model():
            model_name = level_config.get("model", self.get_default_model())
        
        max_tokens = options.max_tokens or level_config.get("max_output_tokens", 8192)
        
        # Convert JSON schema to Gemini format
        gemini_schema = self._convert_to_gemini_schema(json_schema)
        
        # Build prompt without schema instructions (schema is enforced by API)
        full_prompt = f"{system_prompt}\n\n{user_prompt}"
        
        try:
            start_time = time.time()
            
            # Create model instance with Structured Outputs
            model = genai.GenerativeModel(
                model_name=model_name,
                generation_config=GenerationConfig(
                    temperature=1.0,  # Structured Outputs work best with temp=1
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_schema=gemini_schema,  # Native Structured Outputs
                ),
            )
            
            logger.info(f"Calling Gemini API with Structured Outputs", extra={
                "model": model_name,
                "max_tokens": max_tokens,
            })
            
            # Generate response
            response = model.generate_content(
                full_prompt,
                request_options={"timeout": options.timeout},
            )
            
            latency_ms = (time.time() - start_time) * 1000
            
            # Extract response text
            if not response.candidates:
                raise InvalidResponseError("No candidates in Gemini response")
            
            # Check finish reason before accessing text
            candidate = response.candidates[0]
            finish_reason = getattr(candidate, "finish_reason", None)
            
            # Handle problematic finish reasons
            if finish_reason == 4:  # RECITATION (copyrighted material)
                logger.warning(f"Gemini flagged content as copyrighted (finish_reason=4), attempting to extract partial response")
                # Try to get partial content if available
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts") and candidate.content.parts:
                    try:
                        raw_content = candidate.content.parts[0].text
                    except:
                        raise InvalidResponseError("Gemini blocked response due to potential copyright material. Try regenerating with different parameters.")
                else:
                    raise InvalidResponseError("Gemini blocked response due to potential copyright material. Try regenerating with different parameters.")
            elif finish_reason == 3:  # SAFETY
                raise InvalidResponseError("Gemini blocked response due to safety filters")
            elif finish_reason == 2:  # MAX_TOKENS
                logger.warning(f"Gemini hit max_tokens limit, response may be incomplete")
                raw_content = response.text
            else:
                # Normal completion (finish_reason == 1 or 0)
                raw_content = response.text
            
            # Parse JSON (should never fail with Structured Outputs)
            try:
                parsed_content = json.loads(raw_content)
            except json.JSONDecodeError as e:
                # This should be extremely rare with Structured Outputs
                logger.error(f"JSON parse error despite Structured Outputs: {e}")
                logger.error(f"Raw content length: {len(raw_content)} chars, finish_reason: {finish_reason}")
                logger.error(f"Raw content preview: {raw_content[:500]}")
                
                # Try sanitization
                parsed_content = sanitize_llm_output(raw_content)
                if parsed_content is None:
                    # If finish_reason was MAX_TOKENS, give more context
                    if finish_reason == 2:
                        raise InvalidResponseError(
                            f"Gemini hit token limit and produced incomplete JSON. Consider using 'high' reasoning level or reducing prompt length."
                        )
                    raise InvalidResponseError(
                        f"Failed to parse JSON from Gemini response: {raw_content[:200]}"
                    )
            
            # Build usage stats
            usage = {}
            if hasattr(response, "usage_metadata") and response.usage_metadata:
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
