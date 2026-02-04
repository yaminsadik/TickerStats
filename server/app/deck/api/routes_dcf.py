"""
Flask Blueprint for DCF valuation API routes.
Provides endpoint for deterministic DCF target price calculation.
"""

from functools import wraps
from typing import Any, Optional

from flask import Blueprint, g, jsonify, request
from pydantic import BaseModel, Field, field_validator

from app.deck.services.dcf_calculator import calculate_dcf
from app.deck.utils.logging import (
    clear_request_context,
    get_logger,
    set_request_context,
)

logger = get_logger(__name__)

# Create Blueprint
dcf_bp = Blueprint("dcf", __name__, url_prefix="/api/v1/valuation")


# =============================================================================
# REQUEST/RESPONSE SCHEMAS
# =============================================================================

class DCFAssumptionsSchema(BaseModel):
    """User-editable DCF assumptions."""
    forecastYears: int = Field(default=5, ge=5, le=10, description="Number of forecast years (5-10)")
    fcfGrowthRate: float = Field(default=0.08, ge=-0.5, le=1.0, description="FCF growth rate (-50% to 100%)")
    terminalGrowthRate: float = Field(default=0.025, ge=0, le=0.05, description="Terminal growth rate (0-5%)")
    wacc: float = Field(default=0.09, gt=0, le=0.3, description="WACC (must be > terminalGrowthRate)")


class DCFOverridesSchema(BaseModel):
    """Manual overrides for DCF inputs (null = use yfinance data)."""
    sharesOutstanding: Optional[float] = Field(None, description="Override shares outstanding")
    cash: Optional[float] = Field(None, description="Override cash position")
    debt: Optional[float] = Field(None, description="Override total debt")
    fcf0: Optional[float] = Field(None, description="Override base FCF")
    marketPrice: Optional[float] = Field(None, description="Override market price")


class DCFRequest(BaseModel):
    """Request schema for POST /api/v1/valuation/dcf."""
    ticker: str = Field(
        ...,
        description="Stock ticker symbol",
        min_length=1,
        max_length=10,
    )
    assumptions: Optional[DCFAssumptionsSchema] = Field(
        default=None,
        description="DCF assumptions (uses defaults if not provided)",
    )
    overrides: Optional[DCFOverridesSchema] = Field(
        default=None,
        description="Manual overrides for inputs (null values use yfinance)",
    )

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        """Ensure ticker is uppercase."""
        if isinstance(v, str):
            return v.upper().strip()
        return v


# =============================================================================
# MIDDLEWARE / DECORATORS
# =============================================================================

def request_context():
    """Decorator to set up request context for logging."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            import uuid
            request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
            set_request_context(request_id=request_id)
            g.request_id = request_id
            try:
                return f(*args, **kwargs)
            finally:
                clear_request_context()
        return wrapper
    return decorator


def validate_json():
    """Decorator to validate that request has JSON body."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not request.is_json:
                return jsonify({
                    "error": "Content-Type must be application/json",
                    "request_id": getattr(g, "request_id", None),
                }), 400
            return f(*args, **kwargs)
        return wrapper
    return decorator


def handle_errors():
    """Decorator to handle exceptions and return proper error responses."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                return f(*args, **kwargs)
            except ValueError as e:
                logger.warning(f"Value error: {e}")
                return jsonify({
                    "error": str(e),
                    "request_id": getattr(g, "request_id", None),
                }), 400
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
                return jsonify({
                    "error": "Internal server error",
                    "message": str(e),
                    "request_id": getattr(g, "request_id", None),
                }), 500
        return wrapper
    return decorator


# =============================================================================
# ROUTES
# =============================================================================

@dcf_bp.route("/dcf", methods=["POST"])
@request_context()
@validate_json()
@handle_errors()
def calculate_dcf_valuation():
    """
    Calculate DCF target price.
    
    Uses yfinance data for inputs and explicit formulas for calculation.
    All intermediate steps are returned for verification.
    
    ---
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [ticker]
            properties:
              ticker: {type: string, description: Stock ticker symbol}
              assumptions:
                type: object
                properties:
                  forecastYears: {type: integer, default: 5, minimum: 5, maximum: 10}
                  fcfGrowthRate: {type: number, default: 0.08}
                  terminalGrowthRate: {type: number, default: 0.025}
                  wacc: {type: number, default: 0.09}
              overrides:
                type: object
                properties:
                  sharesOutstanding: {type: number, nullable: true}
                  cash: {type: number, nullable: true}
                  debt: {type: number, nullable: true}
                  fcf0: {type: number, nullable: true}
                  marketPrice: {type: number, nullable: true}
    responses:
      200:
        description: DCF valuation result with full breakdown
        content:
          application/json:
            schema:
              type: object
              properties:
                meta:
                  type: object
                  properties:
                    ticker: {type: string}
                    asOf: {type: string}
                    currency: {type: string}
                    provider: {type: string}
                inputs:
                  type: object
                  description: Normalized inputs used
                assumptions:
                  type: object
                  description: Assumptions applied
                valuation:
                  type: object
                  properties:
                    targetPrice: {type: number}
                    marketPrice: {type: number}
                    upsidePct: {type: number}
                calculationBreakdown:
                  type: object
                  description: Step-by-step calculation details
                warnings:
                  type: array
                  items: {type: string}
                sources:
                  type: object
                  description: Source attribution for each input
                error:
                  type: string
                  nullable: true
      400:
        description: Validation error or missing required inputs
      500:
        description: Server error
    """
    # Parse request
    data = request.get_json()
    
    try:
        dcf_request = DCFRequest(**data)
    except Exception as e:
        return jsonify({
            "error": f"Invalid request: {e}",
            "request_id": g.request_id,
        }), 400
    
    # Convert to dict for calculator
    assumptions_dict = None
    if dcf_request.assumptions:
        assumptions_dict = dcf_request.assumptions.model_dump()
    
    overrides_dict = None
    if dcf_request.overrides:
        overrides_dict = dcf_request.overrides.model_dump()
    
    # Calculate DCF
    logger.info(f"Calculating DCF for {dcf_request.ticker}")
    result = calculate_dcf(
        ticker=dcf_request.ticker,
        assumptions=assumptions_dict,
        overrides=overrides_dict,
    )
    
    # Log outcome
    if result.get("error"):
        logger.warning(f"DCF calculation error: {result['error']}")
    else:
        valuation = result.get("valuation", {})
        logger.info(
            f"DCF result for {dcf_request.ticker}: "
            f"target=${valuation.get('targetPrice')}, "
            f"market=${valuation.get('marketPrice')}, "
            f"upside={valuation.get('upsidePct', 0)*100:.1f}%"
        )
    
    return jsonify(result)


@dcf_bp.route("/dcf/inputs/<ticker>", methods=["GET"])
@request_context()
@handle_errors()
def get_dcf_inputs(ticker: str):
    """
    Get DCF inputs for a ticker without calculating valuation.
    
    Useful for pre-populating the form and showing what data is available.
    
    ---
    parameters:
      - name: ticker
        in: path
        required: true
        schema:
          type: string
    responses:
      200:
        description: DCF inputs from yfinance
      404:
        description: Ticker not found or no data available
    """
    from app.deck.services.dcf_data_provider import get_dcf_data_provider
    
    ticker = ticker.upper().strip()
    provider = get_dcf_data_provider()
    inputs, sources, warnings = provider.get_inputs(ticker)
    
    return jsonify({
        "ticker": ticker,
        "inputs": inputs.to_dict(),
        "sources": sources.to_dict(),
        "warnings": warnings,
    })


@dcf_bp.route("/dcf/health", methods=["GET"])
def dcf_health():
    """Health check endpoint for DCF service."""
    return jsonify({
        "status": "ok",
        "service": "dcf-calculator",
        "version": "1.0.0",
    })
