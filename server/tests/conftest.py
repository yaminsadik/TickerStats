"""
Pytest configuration and fixtures for deck generation tests.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

# Set test environment variables before importing app
os.environ["FLASK_TESTING"] = "true"
os.environ["FLASK_DEBUG"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["LOG_JSON"] = "false"


@pytest.fixture
def app():
    """Create Flask test application."""
    from app.deck.app import create_deck_app
    from app.deck.config import DeckConfig
    
    config = DeckConfig(
        DEBUG=False,
        TESTING=True,
        SECRET_KEY="test-secret-key",
        RATE_LIMIT_ENABLED=False,
        CACHE_TYPE="memory",
        LOG_JSON=False,
        LOG_LEVEL="WARNING",
    )
    
    app = create_deck_app(config)
    app.config.update({
        "TESTING": True,
    })
    
    yield app


@pytest.fixture
def client(app):
    """Create test client."""
    return app.test_client()


@pytest.fixture
def mock_openai_response():
    """Mock OpenAI API response."""
    return {
        "section_id": "overview",
        "slides": [
            {
                "slide_id": "overview_1",
                "title": "Accenture: Global IT Services Leader",
                "bullets": [
                    {"text": "Leading professional services company", "source_needed": False},
                    {"text": "Consulting, technology, and outsourcing services", "source_needed": False},
                    {"text": "Strong presence in digital transformation", "source_needed": False},
                ],
                "speaker_notes": "Introduce Accenture as a global leader...",
                "layout_hints": {"style": "bullets", "max_bullets": 4},
                "flags": {"needs_sources": False, "contains_numbers": False, "is_draft": False},
            }
        ],
    }


@pytest.fixture
def mock_history_response():
    """Mock history section response."""
    return {
        "section_id": "history",
        "needs_verification": True,
        "verification_notes": ["Verify IPO date", "Confirm acquisition timeline"],
        "slides": [
            {
                "slide_id": "history_1",
                "title": "Accenture Timeline",
                "bullets": [
                    {"text": "1989: Formed as Andersen Consulting (verify)", "source_needed": True},
                    {"text": "2001: Rebranded to Accenture, IPO (verify)", "source_needed": True},
                    {"text": "2010s: Major acquisitions in digital (verify)", "source_needed": True},
                ],
                "speaker_notes": "Walk through key milestones...",
                "layout_hints": {"style": "timeline", "max_bullets": 4, "suggested_visual": "timeline"},
                "flags": {"needs_sources": True, "contains_numbers": True, "is_draft": True},
            }
        ],
    }


@pytest.fixture
def sample_generate_request():
    """Sample deck generation request."""
    return {
        "ticker": "ACN",
        "company_name": "Accenture",
        "sector": "IT",
        "fund_constraints": {
            "time_horizon": "12-24 months",
            "risk_profile": "moderate",
            "portfolio_context": "Tech-focused portfolio",
            "style": "student investment fund pitch deck",
        },
        "sections": ["overview"],
        "provider": "openai",
        "model": "gpt-4o",
        "reasoning_level": "medium",
        "include_comps": False,
    }


@pytest.fixture
def sample_plan_request():
    """Sample deck plan request."""
    return {
        "ticker": "ACN",
        "company_name": "Accenture",
        "sector": "IT",
        "fund_constraints": {
            "time_horizon": "12-24 months",
            "risk_profile": "moderate",
        },
        "provider": "openai",
    }
