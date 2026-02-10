"""
Flask application factory for deck generation service.
Creates and configures the Flask app with all extensions and blueprints.
"""

import os
from typing import Optional

from flask import Flask, jsonify
from flask_cors import CORS

from app.deck.config import DeckConfig, get_config, init_config
from app.deck.utils.logging import configure_logging, get_logger


def create_deck_app(config: Optional[DeckConfig] = None) -> Flask:
    """
    Application factory for Flask deck generation service.
    
    Args:
        config: Optional configuration object. If not provided, loads from environment.
        
    Returns:
        Configured Flask application
    """
    # Initialize configuration
    app_config = init_config(config) if config else get_config()
    
    # Configure logging
    configure_logging(
        level=app_config.LOG_LEVEL,
        json_output=app_config.LOG_JSON,
    )
    
    logger = get_logger(__name__)
    
    # Create Flask app
    app = Flask(__name__)
    
    # Load config into app
    app.config.from_mapping(
        DEBUG=app_config.DEBUG,
        TESTING=app_config.TESTING,
        SECRET_KEY=app_config.SECRET_KEY,
    )
    
    # Store custom config for access by routes
    app.deck_config = app_config
    
    # Initialize extensions
    _init_cors(app)
    _init_rate_limiter(app, app_config)
    _init_cache(app_config)
    
    # Register blueprints
    _register_blueprints(app)
    
    # Register error handlers
    _register_error_handlers(app)
    
    logger.info("Deck generation Flask app initialized", extra={
        "debug": app_config.DEBUG,
        "cache_type": app_config.CACHE_TYPE,
        "rate_limit_enabled": app_config.RATE_LIMIT_ENABLED,
    })
    
    return app


def _init_cors(app: Flask) -> None:
    """Initialize CORS for the app."""
    raw_allowed_origins = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://127.0.0.1:3000",
    )
    allowed_origins = [origin.strip() for origin in raw_allowed_origins.split(",") if origin.strip()]

    CORS(app, resources={
        r"/api/*": {
            "origins": allowed_origins,
            "methods": ["GET", "POST", "OPTIONS"],
            "allow_headers": [
                "Content-Type",
                "Authorization",
                "X-Request-ID",
                "X-OpenAI-API-Key",
                "X-Gemini-API-Key",
            ],
        }
    })


def _init_rate_limiter(app: Flask, config: DeckConfig) -> None:
    """Initialize rate limiting if enabled."""
    if not config.RATE_LIMIT_ENABLED:
        return
    
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        
        limiter = Limiter(
            key_func=get_remote_address,
            app=app,
            default_limits=[config.RATE_LIMIT_DEFAULT],
            storage_uri=config.REDIS_URL or "memory://",
        )
        
        # Apply specific limits to generate endpoint
        @limiter.limit(config.RATE_LIMIT_GENERATE)
        def _generate_limit():
            pass
        
        app.limiter = limiter
        
    except ImportError:
        logger.warning("flask-limiter not installed, rate limiting disabled")


def _init_cache(config: DeckConfig) -> None:
    """Initialize caching backend."""
    from app.deck.utils.cache import InMemoryCache, RedisCache, init_cache
    
    if config.CACHE_TYPE == "redis" and config.REDIS_URL:
        try:
            # Parse Redis URL
            from urllib.parse import urlparse
            parsed = urlparse(config.REDIS_URL)
            
            backend = RedisCache(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                db=int(parsed.path.lstrip("/") or 0),
                password=parsed.password,
            )
            init_cache(backend)
            return
        except Exception as e:
            logger.warning(f"Failed to initialize Redis cache: {e}, falling back to memory")
    
    # Default to in-memory cache
    init_cache(InMemoryCache())


def _register_blueprints(app: Flask) -> None:
    """Register all blueprints."""
    from app.deck.api.routes_deck import deck_bp
    from app.deck.api.routes_relative import relative_bp
    from app.deck.api.routes_dcf import dcf_bp
    
    app.register_blueprint(deck_bp)
    app.register_blueprint(relative_bp)
    app.register_blueprint(dcf_bp)
    
    # Root health check
    @app.route("/")
    def root():
        return jsonify({
            "service": "tickerstats-unified",
            "version": "1.0.0",
            "status": "running",
            "endpoints": {
                "deck": "/api/v1/deck/*",
                "relative": "/api/relative",
                "dcf": "/api/v1/valuation/dcf",
            }
        })
    
    @app.route("/health")
    def health():
        return jsonify({"status": "ok"})


def _register_error_handlers(app: Flask) -> None:
    """Register global error handlers."""
    logger = get_logger(__name__)
    
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({
            "error": "Bad request",
            "message": str(e.description) if hasattr(e, "description") else str(e),
        }), 400
    
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "Not found",
            "message": "The requested resource was not found",
        }), 404
    
    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({
            "error": "Method not allowed",
            "message": "The HTTP method is not allowed for this endpoint",
        }), 405
    
    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({
            "error": "Rate limit exceeded",
            "message": str(e.description) if hasattr(e, "description") else str(e),
        }), 429
    
    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"Internal server error: {e}", exc_info=True)
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred",
        }), 500


# For running with `flask run` or `python -m app.deck.app`
def get_app() -> Flask:
    """Get the Flask app instance (for WSGI servers)."""
    # Load .env file if python-dotenv is available
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    return create_deck_app()


# Create app instance for gunicorn/uwsgi
app = get_app()


if __name__ == "__main__":
    # Development server
    app = get_app()
    app.run(
        host=os.getenv("FLASK_HOST", "0.0.0.0"),
        port=int(os.getenv("FLASK_PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG", "false").lower() == "true",
    )
