"""
Flask Blueprint for deck generation API routes.
Provides endpoints for generating investment pitch deck sections.
"""

import os
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import ValidationError

from app.deck.api.schemas import (
    SECTION_METADATA,
    DeckGenerateRequest,
    DeckPlanRequest,
    SectionId,
    SectionInfo,
    SectionsResponse,
)
from app.deck.services.deck_generator import DeckGenerator, DeckGeneratorConfig
from app.deck.utils.logging import (
    clear_request_context,
    get_logger,
    set_request_context,
)
from app.deck.utils.ticker_info import enrich_request_with_ticker_info

logger = get_logger(__name__)

# Create Blueprint
deck_bp = Blueprint("deck", __name__, url_prefix="/api/v1")


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
            except ValidationError as e:
                logger.warning(f"Validation error: {e}")
                return jsonify({
                    "error": "Validation error",
                    "details": e.errors(),
                    "request_id": getattr(g, "request_id", None),
                }), 400
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
                    "message": str(e) if current_app.debug else "An unexpected error occurred",
                    "request_id": getattr(g, "request_id", None),
                }), 500
        return wrapper
    return decorator


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_deck_generator() -> DeckGenerator:
    """Get or create the deck generator instance."""
    if not hasattr(g, "deck_generator"):
        config = DeckGeneratorConfig(
            max_retries=int(os.getenv("DECK_MAX_RETRIES", "2")),
            timeout=int(os.getenv("DECK_TIMEOUT", "60")),
            use_cache=os.getenv("DECK_USE_CACHE", "true").lower() == "true",
        )
        g.deck_generator = DeckGenerator(config)
    return g.deck_generator


def get_api_keys() -> tuple[str | None, str | None]:
    """Get API keys from headers or environment."""
    # Check headers first (for per-request keys)
    openai_key = request.headers.get("X-OpenAI-API-Key") or os.getenv("OPENAI_API_KEY")
    gemini_key = (
        request.headers.get("X-Gemini-API-Key") or
        os.getenv("GEMINI_API_KEY") or
        os.getenv("GOOGLE_API_KEY")
    )
    return openai_key, gemini_key


# =============================================================================
# ROUTES
# =============================================================================

@deck_bp.route("/sections", methods=["GET"])
@request_context()
@handle_errors()
def get_sections():
    """
    Get available deck sections.
    
    Returns list of all sections that can be generated.
    
    ---
    responses:
      200:
        description: List of available sections
        content:
          application/json:
            schema:
              type: object
              properties:
                sections:
                  type: array
                  items:
                    type: object
                    properties:
                      id: {type: string}
                      label: {type: string}
                      description: {type: string}
    """
    sections = []
    for section_id in SectionId:
        meta = SECTION_METADATA.get(section_id, {})
        sections.append(SectionInfo(
            id=section_id.value,
            label=meta.get("label", section_id.value),
            description=meta.get("description"),
        ))
    
    response = SectionsResponse(sections=sections)
    return jsonify(response.model_dump())


@deck_bp.route("/deck/generate", methods=["POST"])
@request_context()
@validate_json()
@handle_errors()
def generate_deck():
    """
    Generate pitch deck sections.
    
    Accepts ticker, company info, fund constraints, and selected sections.
    Returns generated slide content as structured JSON.
    
    ---
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [ticker, company_name, sector, fund_constraints, sections, provider]
            properties:
              ticker: {type: string}
              company_name: {type: string}
              sector: {type: string}
              fund_constraints:
                type: object
                required: [time_horizon, risk_profile]
                properties:
                  time_horizon: {type: string}
                  risk_profile: {type: string}
                  portfolio_context: {type: string}
                  style: {type: string}
              sections: {type: array, items: {type: string}}
              provider: {type: string, enum: [openai, gemini]}
              model: {type: string}
              reasoning_level: {type: string, enum: [low, medium, high]}
              include_comps: {type: boolean}
    responses:
      200:
        description: Generated deck sections
      400:
        description: Validation error
      500:
        description: Generation error
    """
    # Parse and validate request
    data = request.get_json()
    deck_request = DeckGenerateRequest(**data)
    
    # Auto-fetch company name and sector if not provided
    try:
        company_name, sector = enrich_request_with_ticker_info(
            ticker=deck_request.ticker,
            company_name=deck_request.company_name,
            sector=deck_request.sector,
        )
        # Update the request object
        deck_request.company_name = company_name
        deck_request.sector = sector
        
        logger.info(
            f"Request enriched: {deck_request.ticker} -> {company_name} ({sector})"
        )
    except ValueError as e:
        return jsonify({
            "error": str(e),
            "request_id": g.request_id,
        }), 400
    
    # Get API keys
    openai_key, gemini_key = get_api_keys()
    
    # Validate we have the required key
    if deck_request.provider.value == "openai" and not openai_key:
        return jsonify({
            "error": "OpenAI API key required. Set OPENAI_API_KEY env var or X-OpenAI-API-Key header.",
            "request_id": g.request_id,
        }), 400
    
    if deck_request.provider.value == "gemini" and not gemini_key:
        return jsonify({
            "error": "Gemini API key required. Set GEMINI_API_KEY env var or X-Gemini-API-Key header.",
            "request_id": g.request_id,
        }), 400
    
    # Generate deck
    generator = get_deck_generator()
    response = generator.generate_deck(
        request=deck_request,
        openai_api_key=openai_key,
        gemini_api_key=gemini_key,
    )
    
    # Return response
    return jsonify(response.model_dump())


@deck_bp.route("/deck/plan", methods=["POST"])
@request_context()
@validate_json()
@handle_errors()
def plan_deck():
    """
    Generate a deck plan with suggested sections.
    
    Returns recommended sections and ordering without generating full slides.
    
    ---
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [ticker, sector, fund_constraints]
            properties:
              ticker: {type: string}
              company_name: {type: string}
              sector: {type: string}
              fund_constraints:
                type: object
                required: [time_horizon, risk_profile]
              provider: {type: string, enum: [openai, gemini]}
    responses:
      200:
        description: Deck plan with suggested sections
      400:
        description: Validation error
    """
    # Parse and validate request
    data = request.get_json()
    plan_request = DeckPlanRequest(**data)
    
    # Get API keys
    openai_key, gemini_key = get_api_keys()
    
    # Generate plan
    generator = get_deck_generator()
    response = generator.plan_deck(
        request=plan_request,
        openai_api_key=openai_key,
        gemini_api_key=gemini_key,
    )
    
    return jsonify(response.model_dump())


@deck_bp.route("/health", methods=["GET"])
def deck_health():
    """Health check endpoint for deck service."""
    return jsonify({
        "status": "ok",
        "service": "deck-generator",
        "version": "1.0.0",
    })


# =============================================================================
# ERROR HANDLERS
# =============================================================================

@deck_bp.errorhandler(400)
def bad_request(e):
    return jsonify({
        "error": "Bad request",
        "message": str(e),
        "request_id": getattr(g, "request_id", None),
    }), 400


@deck_bp.errorhandler(404)
def not_found(e):
    return jsonify({
        "error": "Not found",
        "message": str(e),
        "request_id": getattr(g, "request_id", None),
    }), 404


@deck_bp.errorhandler(429)
def rate_limited(e):
    return jsonify({
        "error": "Rate limit exceeded",
        "message": "Too many requests. Please try again later.",
        "request_id": getattr(g, "request_id", None),
    }), 429


@deck_bp.errorhandler(500)
def internal_error(e):
    logger.error(f"Internal server error: {e}", exc_info=True)
    return jsonify({
        "error": "Internal server error",
        "message": "An unexpected error occurred",
        "request_id": getattr(g, "request_id", None),
    }), 500
