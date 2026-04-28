"""
Configuration for deck generation service.
Loads settings from environment variables with sensible defaults.
"""

import os
from dataclasses import dataclass, field
from typing import Optional

# Load .env file
from dotenv import load_dotenv
load_dotenv()


@dataclass
class DeckConfig:
    """Configuration settings for deck generation service."""
    
    # Flask settings
    DEBUG: bool = False
    TESTING: bool = False
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    
    # API Keys (loaded from environment)
    GEMINI_API_KEY: Optional[str] = None
    
    # Generation settings
    DECK_MAX_RETRIES: int = 2
    DECK_TIMEOUT: int = 60
    DECK_USE_CACHE: bool = True
    
    # Cache settings
    CACHE_TYPE: str = "memory"  # "memory" or "redis"
    CACHE_TTL: int = 3600  # 1 hour
    REDIS_URL: Optional[str] = None
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_DEFAULT: str = "100 per minute"
    RATE_LIMIT_GENERATE: str = "10 per minute"
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON: bool = True
    
    @classmethod
    def from_env(cls) -> "DeckConfig":
        """Load configuration from environment variables."""
        return cls(
            DEBUG=os.getenv("FLASK_DEBUG", "false").lower() == "true",
            TESTING=os.getenv("FLASK_TESTING", "false").lower() == "true",
            SECRET_KEY=os.getenv("FLASK_SECRET_KEY", cls.SECRET_KEY),
            GEMINI_API_KEY=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"),
            DECK_MAX_RETRIES=int(os.getenv("DECK_MAX_RETRIES", "2")),
            DECK_TIMEOUT=int(os.getenv("DECK_TIMEOUT", "60")),
            DECK_USE_CACHE=os.getenv("DECK_USE_CACHE", "true").lower() == "true",
            CACHE_TYPE=os.getenv("CACHE_TYPE", "memory"),
            CACHE_TTL=int(os.getenv("CACHE_TTL", "3600")),
            REDIS_URL=os.getenv("REDIS_URL"),
            RATE_LIMIT_ENABLED=os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true",
            RATE_LIMIT_DEFAULT=os.getenv("RATE_LIMIT_DEFAULT", "100 per minute"),
            RATE_LIMIT_GENERATE=os.getenv("RATE_LIMIT_GENERATE", "10 per minute"),
            LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
            LOG_JSON=os.getenv("LOG_JSON", "true").lower() == "true",
        )


# Singleton config instance
_config: Optional[DeckConfig] = None


def get_config() -> DeckConfig:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = DeckConfig.from_env()
    return _config


def init_config(config: Optional[DeckConfig] = None) -> DeckConfig:
    """Initialize configuration, optionally with a custom config."""
    global _config
    _config = config or DeckConfig.from_env()
    return _config
