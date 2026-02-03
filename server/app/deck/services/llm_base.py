"""
Abstract base class for LLM providers.
Defines unified interface for JSON generation across providers.
"""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from app.deck.utils.logging import get_logger
from app.deck.utils.validation import (
    sanitize_llm_output,
    validate_json_schema,
    clamp_to_schema_limits,
)

logger = get_logger(__name__)


class LLMError(Exception):
    """Base exception for LLM operations."""
    pass


class RateLimitError(LLMError):
    """Rate limit exceeded."""
    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class AuthenticationError(LLMError):
    """Authentication failed."""
    pass


class InvalidResponseError(LLMError):
    """LLM returned invalid response."""
    pass


class TimeoutError(LLMError):
    """Request timed out."""
    pass


@dataclass
class LLMOptions:
    """Options for LLM generation."""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout: int = 60
    reasoning_level: str = "medium"  # low, medium, high
    
    # Provider-specific options
    extra: dict = field(default_factory=dict)


@dataclass
class LLMResponse:
    """Response from LLM generation."""
    content: dict  # Parsed JSON content
    raw_response: str  # Original response string
    model: str  # Model that was used
    provider: str  # Provider name
    usage: dict = field(default_factory=dict)  # Token usage stats
    latency_ms: float = 0.0
    retries: int = 0


class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    All providers must implement:
    - generate_json: Generate structured JSON output
    - validate_api_key: Check if API key is valid
    - get_default_model: Return default model for provider
    """
    
    PROVIDER_NAME: str = "base"
    
    def __init__(self, api_key: str, default_model: Optional[str] = None):
        self.api_key = api_key
        self._default_model = default_model
    
    @abstractmethod
    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        options: Optional[LLMOptions] = None,
    ) -> LLMResponse:
        """
        Generate JSON output from LLM.
        
        Args:
            system_prompt: System-level instructions
            user_prompt: User message/query
            json_schema: Expected JSON schema for output
            options: Generation options
            
        Returns:
            LLMResponse with parsed JSON content
            
        Raises:
            LLMError: On generation failure
        """
        pass
    
    @abstractmethod
    def validate_api_key(self) -> bool:
        """Validate that the API key is functional."""
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
    
    def get_model(self, requested_model: Optional[str] = None) -> str:
        """Get model to use, with fallback to default."""
        return requested_model or self._default_model or self.get_default_model()
    
    def _map_reasoning_level(self, level: str) -> dict:
        """
        Map reasoning level to provider-specific parameters.
        Override in subclasses for provider-specific behavior.
        
        Args:
            level: low, medium, high
            
        Returns:
            Dict of parameters to apply
        """
        return {
            "low": {"temperature": 0.3, "max_tokens": 2048},
            "medium": {"temperature": 0.7, "max_tokens": 4096},
            "high": {"temperature": 0.9, "max_tokens": 8192},
        }.get(level, {"temperature": 0.7, "max_tokens": 4096})
    
    def generate_with_retry(
        self,
        system_prompt: str,
        user_prompt: str,
        json_schema: dict,
        options: Optional[LLMOptions] = None,
        max_retries: int = 2,
        fix_prompt_builder: Optional[callable] = None,
    ) -> LLMResponse:
        """
        Generate JSON with automatic retry on validation failures.
        
        Args:
            system_prompt: System instructions
            user_prompt: User message
            json_schema: Expected schema
            options: Generation options
            max_retries: Maximum retry attempts
            fix_prompt_builder: Function to build fix prompt from errors
            
        Returns:
            LLMResponse with validated JSON
        """
        options = options or LLMOptions()
        last_error = None
        last_response = None
        
        for attempt in range(max_retries + 1):
            try:
                start_time = time.time()
                
                # Use fix prompt on retries
                current_prompt = user_prompt
                if attempt > 0 and last_response and fix_prompt_builder:
                    current_prompt = fix_prompt_builder(
                        last_response.raw_response,
                        last_error,
                        json_schema,
                    )
                    logger.info(f"Retry {attempt}/{max_retries} with fix prompt")
                
                response = self.generate_json(
                    system_prompt,
                    current_prompt,
                    json_schema,
                    options,
                )
                response.latency_ms = (time.time() - start_time) * 1000
                response.retries = attempt
                
                # Validate response against schema
                clamped_content = clamp_to_schema_limits(response.content, json_schema)
                if clamped_content is not response.content:
                    response.content = clamped_content
                validation = validate_json_schema(response.content, json_schema)
                if validation.valid:
                    return response
                
                # Store for potential retry
                last_error = validation.errors
                last_response = response
                logger.warning(
                    f"Schema validation failed on attempt {attempt + 1}",
                    extra={"errors": validation.errors[:3]},
                )
                
            except (RateLimitError, TimeoutError) as e:
                # Don't retry on rate limits or timeouts
                raise
            except LLMError as e:
                last_error = [str(e)]
                logger.warning(f"LLM error on attempt {attempt + 1}: {e}")
                if attempt == max_retries:
                    raise
        
        # All retries exhausted
        raise InvalidResponseError(
            f"Failed to generate valid JSON after {max_retries + 1} attempts. "
            f"Last errors: {last_error}"
        )


def get_provider(
    provider_name: str,
    api_key: str,
    model: Optional[str] = None,
) -> LLMProvider:
    """
    Factory function to get an LLM provider instance.
    
    Args:
        provider_name: "openai" or "gemini"
        api_key: API key for the provider
        model: Optional specific model
        
    Returns:
        LLMProvider instance
    """
    from app.deck.services.llm_openai import OpenAIProvider
    from app.deck.services.llm_gemini import GeminiProvider
    
    providers = {
        "openai": OpenAIProvider,
        "gemini": GeminiProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}. Supported: {list(providers.keys())}")
    
    return provider_class(api_key, model)
