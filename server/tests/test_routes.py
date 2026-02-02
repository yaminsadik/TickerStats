"""
Tests for API routes.
"""

import json
import pytest
from unittest.mock import MagicMock, patch


class TestSectionsEndpoint:
    """Tests for GET /api/v1/sections."""
    
    def test_get_sections_success(self, client):
        response = client.get("/api/v1/sections")
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert "sections" in data
        assert len(data["sections"]) == 6
        
        section_ids = {s["id"] for s in data["sections"]}
        expected_ids = {"overview", "history", "swot", "porters_five", "rebuttals", "layout"}
        assert section_ids == expected_ids
    
    def test_sections_have_labels(self, client):
        response = client.get("/api/v1/sections")
        data = response.get_json()
        
        for section in data["sections"]:
            assert "id" in section
            assert "label" in section
            assert len(section["label"]) > 0


class TestHealthEndpoint:
    """Tests for health check endpoints."""
    
    def test_root_health(self, client):
        response = client.get("/")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "running"
    
    def test_health_endpoint(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
    
    def test_deck_health(self, client):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["service"] == "deck-generator"


class TestGenerateEndpoint:
    """Tests for POST /api/v1/deck/generate."""
    
    def test_missing_api_key(self, client, sample_generate_request):
        response = client.post(
            "/api/v1/deck/generate",
            json=sample_generate_request,
            content_type="application/json",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "API key" in data.get("error", "")
    
    def test_invalid_content_type(self, client, sample_generate_request):
        response = client.post(
            "/api/v1/deck/generate",
            data=json.dumps(sample_generate_request),
            content_type="text/plain",
        )
        
        assert response.status_code == 400
        data = response.get_json()
        assert "Content-Type" in data.get("error", "")
    
    def test_invalid_request_body(self, client):
        response = client.post(
            "/api/v1/deck/generate",
            json={"invalid": "request"},
            content_type="application/json",
        )
        
        assert response.status_code == 400
    
    def test_invalid_ticker_format(self, client, sample_generate_request):
        sample_generate_request["ticker"] = "INVALID$TICKER"
        
        response = client.post(
            "/api/v1/deck/generate",
            json=sample_generate_request,
            content_type="application/json",
        )
        
        assert response.status_code == 400
    
    def test_invalid_section_id(self, client, sample_generate_request):
        sample_generate_request["sections"] = ["overview", "not_a_section"]
        
        response = client.post(
            "/api/v1/deck/generate",
            json=sample_generate_request,
            content_type="application/json",
        )
        
        assert response.status_code == 400
    
    def test_invalid_provider(self, client, sample_generate_request):
        sample_generate_request["provider"] = "invalid_provider"
        
        response = client.post(
            "/api/v1/deck/generate",
            json=sample_generate_request,
            content_type="application/json",
        )
        
        assert response.status_code == 400
    
    @patch("app.deck.services.deck_generator.DeckGenerator.generate_deck")
    def test_successful_generation(self, mock_generate, client, sample_generate_request, mock_openai_response):
        # Mock the response
        from app.deck.api.schemas import (
            DeckGenerateResponse,
            SectionResult,
            Slide,
            BulletPoint,
            ProviderInfo,
        )
        
        mock_generate.return_value = DeckGenerateResponse(
            ticker="ACN",
            provider_used=ProviderInfo(
                provider="openai",
                model="gpt-4o",
                reasoning_level="medium",
            ),
            results=[
                SectionResult(
                    section_id="overview",
                    slides=[
                        Slide(
                            slide_id="overview_1",
                            title="Test Title",
                            bullets=[BulletPoint(text="Test bullet")],
                        )
                    ],
                )
            ],
            errors=[],
            request_id="test123",
        )
        
        response = client.post(
            "/api/v1/deck/generate",
            json=sample_generate_request,
            content_type="application/json",
            headers={"X-OpenAI-API-Key": "test-key"},
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["ticker"] == "ACN"
        assert data["provider_used"]["provider"] == "openai"
        assert len(data["results"]) == 1


class TestPlanEndpoint:
    """Tests for POST /api/v1/deck/plan."""
    
    def test_plan_success(self, client, sample_plan_request):
        response = client.post(
            "/api/v1/deck/plan",
            json=sample_plan_request,
            content_type="application/json",
        )
        
        assert response.status_code == 200
        data = response.get_json()
        
        assert data["ticker"] == "ACN"
        assert "suggested_sections" in data
        assert "recommended_order" in data
        assert len(data["suggested_sections"]) > 0
    
    def test_plan_includes_all_sections(self, client, sample_plan_request):
        response = client.post(
            "/api/v1/deck/plan",
            json=sample_plan_request,
            content_type="application/json",
        )
        
        data = response.get_json()
        section_ids = {s["id"] for s in data["suggested_sections"]}
        
        expected = {"overview", "history", "swot", "porters_five", "rebuttals", "layout"}
        assert section_ids == expected
    
    def test_plan_sections_have_priority(self, client, sample_plan_request):
        response = client.post(
            "/api/v1/deck/plan",
            json=sample_plan_request,
            content_type="application/json",
        )
        
        data = response.get_json()
        
        for section in data["suggested_sections"]:
            assert "priority" in section
            assert "rationale" in section
            assert "estimated_slides" in section
    
    def test_plan_invalid_request(self, client):
        response = client.post(
            "/api/v1/deck/plan",
            json={"ticker": "ACN"},  # Missing required fields
            content_type="application/json",
        )
        
        assert response.status_code == 400


class TestErrorHandling:
    """Tests for error handling."""
    
    def test_404_not_found(self, client):
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404
    
    def test_405_method_not_allowed(self, client):
        response = client.delete("/api/v1/sections")
        assert response.status_code == 405


class TestRequestContext:
    """Tests for request context handling."""
    
    def test_request_id_in_response(self, client, sample_plan_request):
        response = client.post(
            "/api/v1/deck/plan",
            json=sample_plan_request,
            content_type="application/json",
        )
        
        data = response.get_json()
        assert "request_id" in data
    
    def test_custom_request_id_header(self, client, sample_plan_request):
        custom_id = "custom-request-123"
        
        response = client.post(
            "/api/v1/deck/plan",
            json=sample_plan_request,
            content_type="application/json",
            headers={"X-Request-ID": custom_id},
        )
        
        # The custom ID should be used
        data = response.get_json()
        assert "request_id" in data
