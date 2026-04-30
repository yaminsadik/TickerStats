"""Pytest configuration and fixtures for deck generation tests."""

import os
import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from httpx import Response

# Set test environment variables before importing app.
os.environ["LOG_JSON"] = "false"


if not hasattr(Response, "get_json"):
    Response.get_json = Response.json


@pytest.fixture
def app():
    """Create FastAPI test application."""
    from app.main import app as fastapi_app

    yield fastapi_app


@pytest.fixture
def client(app):
    """Create test client."""
    class CompatTestClient(TestClient):
        def post(self, url, *args, content_type=None, **kwargs):
            if content_type:
                headers = dict(kwargs.pop("headers", {}) or {})
                headers.setdefault("content-type", content_type)
                kwargs["headers"] = headers
            return super().post(url, *args, **kwargs)

    with CompatTestClient(app) as test_client:
        yield test_client


@pytest.fixture
def mock_gemini_response():
    """Mock Gemini API response."""
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
        "provider": "gemini",
        "model": "gemini-3-flash-preview",
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
        "provider": "gemini",
    }
