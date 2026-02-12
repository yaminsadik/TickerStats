"""
Pydantic v2 schemas for request validation and response typing.
"""

from typing import Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"


class PerfRequest(BaseModel):
    """Performance request details in response."""

    period: str
    metrics: list[str]


class SnapshotData(BaseModel):
    """Snapshot fundamentals/valuation metrics."""

    sharePrice: Optional[float] = None
    marketCap: Optional[float] = None
    enterpriseValue: Optional[float] = None
    forwardPE: Optional[float] = None
    priceSales: Optional[float] = None
    priceBook: Optional[float] = None
    evEbitda: Optional[float] = None
    evRevenue: Optional[float] = None
    profitMargin: Optional[float] = None
    roa: Optional[float] = None
    roe: Optional[float] = None
    debtEquity: Optional[float] = None
    beta: Optional[float] = None


class PerformanceData(BaseModel):
    """Performance metrics computed from price history."""

    return_: Optional[float] = Field(default=None, alias="return")
    volatility: Optional[float] = None
    maxDrawdown: Optional[float] = None

    model_config = {"populate_by_name": True}


class DcfData(BaseModel):
    """DCF valuation metrics."""

    dcfPrice: Optional[float] = Field(default=None, description="DCF fair value per share")
    dcfUpside: Optional[float] = Field(default=None, description="Upside/downside percentage vs current price")


class RequestedParams(BaseModel):
    """Echoed request parameters."""

    symbols: list[str]
    fields: list[str]
    perf: Optional[PerfRequest] = None
    dcf: bool = False


class RowData(BaseModel):
    """Single row in the relative table response."""

    symbol: str
    snapshot: dict[str, Optional[float]]
    performance: Optional[dict[str, Optional[float]]] = None
    dcf: Optional[dict[str, Optional[float]]] = None
    missingFields: list[str] = Field(default_factory=list)
    missingPerf: Optional[list[str]] = None
    error: Optional[str] = None


class RelativeTableResponse(BaseModel):
    """Full response for /api/relative endpoint."""

    asOf: str
    requested: RequestedParams
    units: dict[str, str]
    rows: list[RowData]


class ErrorResponse(BaseModel):
    """Standard error response."""

    detail: str


class LandingMarketRow(BaseModel):
    """Public landing snapshot row (real market metrics only)."""

    symbol: str
    sharePrice: Optional[float] = None
    marketCap: Optional[float] = None
    return1mo: Optional[float] = None
    volatility1mo: Optional[float] = None
    beta: Optional[float] = None
    profitMargin: Optional[float] = None
    error: Optional[str] = None


class LandingMarketResponse(BaseModel):
    """Public landing response for the hero market terminal."""

    asOf: str
    period: str
    source: str
    delayDisclaimer: str
    rows: list[LandingMarketRow]
