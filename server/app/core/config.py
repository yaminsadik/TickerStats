"""
Centralized configuration constants for the TicketStats API.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://ticketstats:ticketstats@localhost:5432/ticketstats"
    )
    ASYNC_DATABASE_URL: str = os.getenv(
        "ASYNC_DATABASE_URL",
        "postgresql+asyncpg://ticketstats:ticketstats@localhost:5432/ticketstats"
    )
    
    # Auth0
    AUTH0_DOMAIN: str = os.getenv("AUTH0_DOMAIN", "")
    AUTH0_API_AUDIENCE: str = os.getenv("AUTH0_API_AUDIENCE", "")
    AUTH0_ALGORITHMS: list[str] = ["RS256"]
    AUTH0_ISSUER: str = ""  # Will be set in __init__
    
    # Application
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env file
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
