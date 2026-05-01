"""
Centralized configuration constants for the TickerStats API.
"""
import json
import os
from pathlib import Path
from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    DATABASE_URL: str = Field(
        default="postgresql://tickerstats:tickerstats@localhost:5432/ticketstats",
        validation_alias=AliasChoices("DATABASE_URL"),
    )
    ASYNC_DATABASE_URL: str = Field(
        default="postgresql+asyncpg://tickerstats:tickerstats@localhost:5432/ticketstats",
        validation_alias=AliasChoices("ASYNC_DATABASE_URL"),
    )

    # Auth0
    AUTH0_DOMAIN: str = Field(
        default="",
        validation_alias=AliasChoices("AUTH0_DOMAIN"),
    )
    AUTH0_API_AUDIENCE: str = Field(
        default="",
        validation_alias=AliasChoices("AUTH0_API_AUDIENCE", "AUTH0_AUDIENCE"),
    )
    AUTH0_ALGORITHMS: list[str] = Field(
        default_factory=lambda: ["RS256"],
        validation_alias=AliasChoices("AUTH0_ALGORITHMS"),
    )
    AUTH0_JWKS_CACHE_TTL_SECONDS: int = Field(
        default=3600,
        validation_alias=AliasChoices("AUTH0_JWKS_CACHE_TTL_SECONDS"),
    )
    AUTH0_ISSUER: str = ""  # Will be set in __init__

    # Application
    DEBUG: bool = Field(
        default=False,
        validation_alias=AliasChoices("DEBUG"),
    )
    ENVIRONMENT: str = Field(
        default="development",
        validation_alias=AliasChoices("ENVIRONMENT"),
    )

    # Claude Skills export
    ANTHROPIC_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("ANTHROPIC_API_KEY"),
    )
    CLAUDE_EXPORT_MODEL: str = Field(
        default="claude-sonnet-4-5",
        validation_alias=AliasChoices("CLAUDE_EXPORT_MODEL"),
    )
    CLAUDE_EXPORT_CACHE_DIR: str = Field(
        default="/tmp/tickerstats_deck_exports",
        validation_alias=AliasChoices("CLAUDE_EXPORT_CACHE_DIR"),
    )
    CLAUDE_EXPORT_MAX_SLIDES: int = Field(
        default=30,
        validation_alias=AliasChoices("CLAUDE_EXPORT_MAX_SLIDES"),
    )
    CLAUDE_EXPORT_MAX_TOKENS: int = Field(
        default=16000,
        validation_alias=AliasChoices("CLAUDE_EXPORT_MAX_TOKENS"),
    )
    CLAUDE_EXPORT_TIMEOUT_SECONDS: float = Field(
        default=360.0,
        validation_alias=AliasChoices("CLAUDE_EXPORT_TIMEOUT_SECONDS"),
    )
    CLAUDE_EXPORT_ALLOW_FREE: bool = Field(
        default=False,
        validation_alias=AliasChoices("CLAUDE_EXPORT_ALLOW_FREE"),
    )

    # Google Gemini on Vertex AI
    GOOGLE_GENAI_USE_VERTEXAI: bool = Field(
        default=False,
        validation_alias=AliasChoices("GOOGLE_GENAI_USE_VERTEXAI"),
    )
    GOOGLE_CLOUD_PROJECT: str = Field(
        default="",
        validation_alias=AliasChoices("GOOGLE_CLOUD_PROJECT"),
    )
    GOOGLE_CLOUD_LOCATION: str = Field(
        default="us-central1",
        validation_alias=AliasChoices("GOOGLE_CLOUD_LOCATION"),
    )
    VERTEX_GEMINI_DEFAULT_MODEL: str = Field(
        default="gemini-3-flash-preview",
        validation_alias=AliasChoices("VERTEX_GEMINI_DEFAULT_MODEL"),
    )

    # Stripe
    STRIPE_SECRET_KEY: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_SECRET_KEY"),
    )
    STRIPE_WEBHOOK_SECRET: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_WEBHOOK_SECRET"),
    )
    STRIPE_PRICE_ID_PRO: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_PRO"),
    )
    STRIPE_PRICE_ID_ENTERPRISE: str = Field(
        default="",
        validation_alias=AliasChoices("STRIPE_PRICE_ID_ENTERPRISE"),
    )
    FRONTEND_URL: str = Field(
        default="http://localhost:3000",
        validation_alias=AliasChoices("FRONTEND_URL"),
    )

    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        case_sensitive=True,
        extra="ignore",
    )

    @field_validator("AUTH0_ALGORITHMS", mode="before")
    @classmethod
    def _parse_auth0_algorithms(cls, value):
        if value is None:
            return ["RS256"]
        if isinstance(value, list):
            return [str(v).strip() for v in value if str(v).strip()]
        if isinstance(value, str):
            parsed = value.strip()
            if not parsed:
                return ["RS256"]
            if parsed.startswith("[") and parsed.endswith("]"):
                try:
                    decoded = json.loads(parsed)
                    if isinstance(decoded, list):
                        cleaned = [str(v).strip() for v in decoded if str(v).strip()]
                        return cleaned or ["RS256"]
                except json.JSONDecodeError:
                    pass
            cleaned = [item.strip() for item in parsed.split(",") if item.strip()]
            return cleaned or ["RS256"]
        return ["RS256"]

    def model_post_init(self, __context):
        if self.AUTH0_DOMAIN:
            self.AUTH0_ISSUER = f"https://{self.AUTH0_DOMAIN}/"


settings = Settings()

# Request limits
MAX_SYMBOLS_PER_REQUEST = 100  # Increased from 30 to support larger relative tables

# Cache TTL in seconds
CACHE_TTL_SECONDS = 120

# Snapshot field allowlist with yfinance mappings (fallback order)
SNAPSHOT_FIELDS_ALLOWLIST = {
    "sharePrice": ["currentPrice", "regularMarketPrice"],  # fallback order
    "marketCap": ["marketCap"],
    "enterpriseValue": ["enterpriseValue"],
    "forwardPE": ["forwardPE"],
    "priceSales": ["priceToSalesTrailing12Months"],
    "priceBook": ["priceToBook"],
    "evEbitda": ["enterpriseToEbitda"],
    "evRevenue": ["enterpriseToRevenue"],
    "profitMargin": ["profitMargins"],
    "roa": ["returnOnAssets"],
    "roe": ["returnOnEquity"],
    "debtEquity": ["debtToEquity"],
    "beta": ["beta"],
}

# Default snapshot fields (order matters for table display)
DEFAULT_SNAPSHOT_FIELDS = [
    "sharePrice",
    "marketCap",
    "enterpriseValue",
    "forwardPE",
    "priceSales",
    "priceBook",
    "evEbitda",
    "evRevenue",
    "profitMargin",
    "roa",
    "roe",
    "debtEquity",
    "beta",
]

# Performance metrics allowlist
PERF_METRICS_ALLOWLIST = ["return", "volatility", "maxDrawdown"]

# DCF metrics
DCF_METRICS = ["dcfPrice", "dcfUpside"]

# Valid performance periods
VALID_PERF_PERIODS = ["1mo", "3mo", "6mo", "ytd", "1y", "2y", "5y", "10y", "max"]

# Thread pool settings
MAX_WORKERS = 10
FETCH_TIMEOUT_SECONDS = 30

# yfinance concurrency limiter (per process)
# Prevents yfinance throttling under concurrent load.
YFINANCE_MAX_CONCURRENCY = int(os.getenv("YFINANCE_MAX_CONCURRENCY", "6"))

# API version
API_VERSION = "1.0.0"

# Units metadata for each metric (frontend formatting hints)
UNITS_METADATA = {
    # Snapshot fields
    "sharePrice": "currency",
    "marketCap": "currency",
    "enterpriseValue": "currency",
    "forwardPE": "ratio",
    "priceSales": "ratio",
    "priceBook": "ratio",
    "evEbitda": "ratio",
    "evRevenue": "ratio",
    "profitMargin": "decimal",
    "roa": "decimal",
    "roe": "decimal",
    "debtEquity": "ratio",
    "beta": "ratio",
    # Performance metrics
    "return": "decimal",
    "volatility": "decimal",
    "maxDrawdown": "decimal",
    # DCF metrics
    "dcfPrice": "currency",
    "dcfUpside": "ratio",  # Already in percentage form (e.g., -40.65 = -40.65%)
}
