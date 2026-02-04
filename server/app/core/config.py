"""
Centralized configuration constants for the TicketStats API.
"""

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
