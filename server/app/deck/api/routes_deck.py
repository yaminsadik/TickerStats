"""
Flask Blueprint for deck generation API routes.
Provides endpoints for generating investment pitch deck sections.
"""

import os
from datetime import datetime, timezone
from functools import wraps
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request
from pydantic import ValidationError

from app.deck.api.schemas import (
    SECTION_METADATA,
    AnalysisDepth,
    DeckGenerateRequest,
    DeckPlanRequest,
    ModelMode,
    PlanTier,
    Provider,
    ReasoningLevel,
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
from app.core.auth import verifier
from app.core.config import settings
from app.core.database import SessionLocal
from app.models import User
from app.services.usage_limits import (
    check_deck_limit_sync,
    enforce_deck_limit_and_increment_sync,
    get_plan_tier,
)

logger = get_logger(__name__)

# Create Blueprint
deck_bp = Blueprint("deck", __name__, url_prefix="/api/v1")


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (UTC semantics)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# =============================================================================
# MIDDLEWARE / DECORATORS
# =============================================================================

def _to_json_safe(value: Any) -> Any:
    """Recursively convert values into JSON-serializable structures."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _to_json_safe(v) for k, v in value.items()}
    return str(value)


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
                    "details": _to_json_safe(e.errors()),
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
            parallel_sections=os.getenv("DECK_PARALLEL_SECTIONS", "false").lower() == "true",
            max_parallel_workers=int(os.getenv("DECK_MAX_PARALLEL_WORKERS", "5")),
            section_delay_seconds=float(os.getenv("DECK_SECTION_DELAY", "0.5")),
        )
        g.deck_generator = DeckGenerator(config)
    return g.deck_generator


def get_api_keys() -> dict[str, str | None]:
    """Get API keys from headers or environment for all providers."""
    return {
        "openai": request.headers.get("X-OpenAI-API-Key") or os.getenv("OPENAI_API_KEY"),
        "gemini": (
            request.headers.get("X-Gemini-API-Key")
            or os.getenv("GEMINI_API_KEY")
            or os.getenv("GOOGLE_API_KEY")
        ),
        "deepseek": request.headers.get("X-DeepSeek-API-Key") or os.getenv("DEEPSEEK_API_KEY"),
        "zai": request.headers.get("X-ZAI-API-Key") or os.getenv("ZAI_API_KEY"),
        "anthropic": request.headers.get("X-Anthropic-API-Key") or os.getenv("ANTHROPIC_API_KEY"),
    }


def _get_bearer_token() -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return None


def _upsert_user_sync(session, user_id: str, payload: dict) -> User:
    """Sync upsert for Flask routes using the shared User model."""
    # Try multiple possible claim locations for email, name, picture
    # Standard claims, custom namespaced claims, or Auth0-specific claims
    email = (
        payload.get("email") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/email") or
        payload.get("https://tickerstats.com/email") or
        payload.get("http://tickerstats.com/email")
    )
    name = (
        payload.get("name") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/name") or
        payload.get("https://tickerstats.com/name") or
        payload.get("http://tickerstats.com/name") or
        payload.get("nickname")
    )
    picture = (
        payload.get("picture") or 
        payload.get(f"https://{settings.AUTH0_DOMAIN}/picture") or
        payload.get("https://tickerstats.com/picture") or
        payload.get("http://tickerstats.com/picture")
    )
    
    # Log what we found for debugging
    if not email or not name:
        logger.warning(
            f"Missing user info from token for {user_id}: "
            f"email={'✓' if email else '✗'}, name={'✓' if name else '✗'}. "
            f"Available claims: {list(payload.keys())}"
        )

    user = session.get(User, user_id)
    if user:
        changed = False
        if not user.subscription_tier:
            user.subscription_tier = "free"
            changed = True
        if email and user.email != email:
            user.email = email
            changed = True
        if name and user.name != name:
            user.name = name
            changed = True
        if picture and user.picture != picture:
            user.picture = picture
            changed = True
        if changed:
            user.updated_at = _utcnow_naive()
            session.flush()
        return user

    user = User(
        auth0_user_id=user_id,
        email=email,
        name=name,
        picture=picture,
        subscription_tier="free",
    )
    session.add(user)
    session.flush()
    return user


def _resolve_plan_and_models(
    deck_request: DeckGenerateRequest,
    api_keys: dict[str, str | None],
    plan_tier: str,
) -> tuple[str, str | None, AnalysisDepth, ModelMode]:
    """Apply plan-tier model rules and return provider, model, depth, mode.

    Delegates to the model_policy module when the model_mode is AUTO.
    When model_mode is SPECIFIC, the user's explicit choice is honoured.
    """
    from app.deck.services.model_policy import resolve_model

    model_mode = deck_request.model_mode or ModelMode.AUTO
    analysis_depth = deck_request.analysis_depth or AnalysisDepth(deck_request.reasoning_level.value)

    # Free tier caps depth at medium
    if plan_tier == "free" and analysis_depth == AnalysisDepth.HIGH:
        analysis_depth = AnalysisDepth.MEDIUM

    thinking_requested = deck_request.reasoning_level == ReasoningLevel.HIGH

    decision = resolve_model(
        plan_tier=plan_tier,
        analysis_depth=analysis_depth.value,
        model_mode=model_mode.value,
        requested_model_id=deck_request.model,
        thinking_requested=thinking_requested,
        available_keys=api_keys,
    )

    return decision.provider, decision.model, analysis_depth, model_mode


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

    # Require authentication for usage limits
    token = _get_bearer_token()
    if not token:
        return jsonify({
            "error": "Authentication required",
            "request_id": getattr(g, "request_id", None),
        }), 401
    try:
        payload = verifier.verify_token(token)
    except Exception:
        return jsonify({
            "error": "Invalid token",
            "request_id": getattr(g, "request_id", None),
        }), 401

    user_id = payload.get("sub")
    if not user_id:
        return jsonify({
            "error": "Invalid token: Missing subject",
            "request_id": getattr(g, "request_id", None),
        }), 401

    # Upsert user and enforce deck generation limits
    session = SessionLocal()
    try:
        user = _upsert_user_sync(session, user_id, payload)
        plan_tier = get_plan_tier(user)
        allowed, limit = check_deck_limit_sync(user, _utcnow_naive())
        session.commit()
    except Exception as e:
        session.rollback()
        return jsonify({
            "error": "User lookup failed",
            "message": str(e) if current_app.debug else "Failed to resolve authenticated user.",
            "request_id": getattr(g, "request_id", None),
        }), 500
    finally:
        session.close()

    if not allowed:
        return jsonify({
            "error": "Deck limit reached",
            "message": f"Your plan is limited to {limit} deck generations per month.",
            "request_id": getattr(g, "request_id", None),
        }), 403
    
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
    api_keys = get_api_keys()

    # Apply plan-tier model routing
    provider_name, model_name, analysis_depth, model_mode = _resolve_plan_and_models(
        deck_request,
        api_keys,
        plan_tier,
    )
    deck_request.plan_tier = PlanTier(plan_tier)
    deck_request.model_mode = model_mode
    deck_request.analysis_depth = analysis_depth
    deck_request.reasoning_level = ReasoningLevel(analysis_depth.value)
    deck_request.provider = Provider(provider_name)
    deck_request.model = model_name

    # Validate we have the required key for the chosen provider
    chosen_provider = deck_request.provider.value
    if not api_keys.get(chosen_provider):
        provider_labels = {
            "openai": "OPENAI_API_KEY",
            "gemini": "GEMINI_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "zai": "ZAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
        }
        env_hint = provider_labels.get(chosen_provider, chosen_provider.upper() + "_API_KEY")
        return jsonify({
            "error": f"{chosen_provider} API key required. Set {env_hint} env var.",
            "request_id": g.request_id,
        }), 400
    
    # Generate deck
    generator = get_deck_generator()
    response = generator.generate_deck(
        request=deck_request,
        api_keys=api_keys,
    )
    
    # Increment deck usage on success
    session = SessionLocal()
    try:
        allowed_after_generate, locked_limit = enforce_deck_limit_and_increment_sync(
            session,
            user_id,
            _utcnow_naive(),
        )
        if not allowed_after_generate:
            session.rollback()
            return jsonify({
                "error": "Deck limit reached",
                "message": f"Your plan is limited to {locked_limit} deck generations per month.",
                "request_id": getattr(g, "request_id", None),
            }), 403
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()

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
    api_keys = get_api_keys()
    
    # Generate plan
    generator = get_deck_generator()
    response = generator.plan_deck(
        request=plan_request,
        api_keys=api_keys,
    )
    
    return jsonify(response.model_dump())


@deck_bp.route("/deck/models", methods=["GET"])
@request_context()
@handle_errors()
def get_available_models():
    """
    Return the list of models available for the caller's tier.
    Requires authentication so the tier can be determined.
    """
    from app.deck.services.model_catalog import get_catalog_for_api

    token = _get_bearer_token()
    tier = "free"  # default for unauthenticated
    if token:
        try:
            payload = verifier.verify_token(token)
            user_id = payload.get("sub")
            if user_id:
                session = SessionLocal()
                try:
                    user = _upsert_user_sync(session, user_id, payload)
                    tier = get_plan_tier(user)
                    session.commit()
                finally:
                    session.close()
        except Exception:
            pass  # Fall back to free tier

    return jsonify({"tier": tier, "models": get_catalog_for_api(tier)})


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
