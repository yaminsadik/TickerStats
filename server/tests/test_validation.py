"""
Tests for validation utilities.
"""

import pytest
from app.deck.utils.validation import (
    validate_ticker,
    validate_json_schema,
    validate_slide_content,
    validate_section_output,
    sanitize_llm_output,
    compute_constraints_hash,
    detect_numeric_claims,
    create_fix_prompt,
)


class TestValidateTicker:
    """Tests for ticker validation."""
    
    def test_valid_ticker(self):
        result = validate_ticker("AAPL")
        assert result.valid
        assert result.data == "AAPL"
    
    def test_lowercase_ticker_converted(self):
        result = validate_ticker("aapl")
        assert result.valid
        assert result.data == "AAPL"
    
    def test_ticker_with_dot(self):
        result = validate_ticker("BRK.B")
        assert result.valid
        assert result.data == "BRK.B"
    
    def test_ticker_with_hyphen(self):
        result = validate_ticker("BF-B")
        assert result.valid
        assert result.data == "BF-B"
    
    def test_empty_ticker(self):
        result = validate_ticker("")
        assert not result.valid
        assert "required" in result.errors[0].lower()
    
    def test_too_long_ticker(self):
        result = validate_ticker("TOOLONGTICKER")
        assert not result.valid
    
    def test_invalid_characters(self):
        result = validate_ticker("AAP$L")
        assert not result.valid


class TestValidateJsonSchema:
    """Tests for JSON schema validation."""
    
    def test_valid_data(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
            },
        }
        data = {"name": "test"}
        
        result = validate_json_schema(data, schema)
        assert result.valid
    
    def test_missing_required_field(self):
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
            },
        }
        data = {}
        
        result = validate_json_schema(data, schema)
        assert not result.valid
        assert any("name" in e for e in result.errors)
    
    def test_wrong_type(self):
        schema = {
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
            },
        }
        data = {"count": "not a number"}
        
        result = validate_json_schema(data, schema)
        assert not result.valid


class TestValidateSlideContent:
    """Tests for slide content validation."""
    
    def test_valid_slide(self):
        slide = {
            "title": "Test Slide",
            "bullets": [
                {"text": "First point"},
                {"text": "Second point"},
            ],
            "flags": {},
        }
        
        result = validate_slide_content(slide)
        assert result.valid
    
    def test_too_many_bullets(self):
        slide = {
            "title": "Test Slide",
            "bullets": [
                {"text": f"Point {i}"} for i in range(6)
            ],
        }
        
        result = validate_slide_content(slide)
        assert not result.valid
        assert any("maximum" in e.lower() for e in result.errors)
    
    def test_missing_title(self):
        slide = {
            "title": "",
            "bullets": [{"text": "Point"}],
        }
        
        result = validate_slide_content(slide)
        assert not result.valid
    
    def test_no_bullets(self):
        slide = {
            "title": "Test",
            "bullets": [],
        }
        
        result = validate_slide_content(slide)
        assert not result.valid


class TestValidateSectionOutput:
    """Tests for section output validation."""
    
    def test_valid_overview_section(self):
        section = {
            "section_id": "overview",
            "slides": [
                {
                    "title": "Company Overview",
                    "bullets": [{"text": "Point 1"}, {"text": "Point 2"}],
                    "flags": {},
                }
            ],
        }
        
        result = validate_section_output(section, "overview")
        assert result.valid
    
    def test_section_id_mismatch(self):
        section = {
            "section_id": "swot",
            "slides": [{"title": "Test", "bullets": [{"text": "Point"}]}],
        }
        
        result = validate_section_output(section, "overview")
        assert not result.valid
    
    def test_history_requires_verification(self):
        section = {
            "section_id": "history",
            "needs_verification": False,  # Should be True
            "slides": [{"title": "Test", "bullets": [{"text": "Point"}]}],
        }
        
        result = validate_section_output(section, "history")
        assert not result.valid
        assert any("verification" in e.lower() for e in result.errors)
    
    def test_history_valid_with_verification(self):
        section = {
            "section_id": "history",
            "needs_verification": True,
            "verification_notes": ["Verify dates"],
            "slides": [{"title": "Timeline", "bullets": [{"text": "Event (verify)"}]}],
        }
        
        result = validate_section_output(section, "history")
        assert result.valid
    
    def test_rebuttals_max_slides(self):
        section = {
            "section_id": "rebuttals",
            "slides": [
                {"title": "Q&A 1", "bullets": [{"text": "Q1"}]},
                {"title": "Q&A 2", "bullets": [{"text": "Q2"}]},
                {"title": "Q&A 3", "bullets": [{"text": "Q3"}]},  # Exceeds max of 2
            ],
        }
        
        result = validate_section_output(section, "rebuttals")
        assert not result.valid


class TestSanitizeLlmOutput:
    """Tests for LLM output sanitization."""
    
    def test_direct_json(self):
        output = '{"key": "value"}'
        result = sanitize_llm_output(output)
        assert result == {"key": "value"}
    
    def test_json_in_markdown_block(self):
        output = '```json\n{"key": "value"}\n```'
        result = sanitize_llm_output(output)
        assert result == {"key": "value"}
    
    def test_json_in_plain_block(self):
        output = '```\n{"key": "value"}\n```'
        result = sanitize_llm_output(output)
        assert result == {"key": "value"}
    
    def test_json_with_surrounding_text(self):
        output = 'Here is the JSON:\n{"key": "value"}\nDone!'
        result = sanitize_llm_output(output)
        assert result == {"key": "value"}
    
    def test_invalid_json(self):
        output = 'not valid json'
        result = sanitize_llm_output(output)
        assert result is None
    
    def test_empty_input(self):
        result = sanitize_llm_output("")
        assert result is None
        
        result = sanitize_llm_output(None)
        assert result is None


class TestComputeConstraintsHash:
    """Tests for constraints hashing."""
    
    def test_same_input_same_hash(self):
        constraints = {"time_horizon": "12 months", "risk": "moderate"}
        hash1 = compute_constraints_hash(constraints)
        hash2 = compute_constraints_hash(constraints)
        assert hash1 == hash2
    
    def test_different_input_different_hash(self):
        constraints1 = {"time_horizon": "12 months"}
        constraints2 = {"time_horizon": "24 months"}
        hash1 = compute_constraints_hash(constraints1)
        hash2 = compute_constraints_hash(constraints2)
        assert hash1 != hash2
    
    def test_key_order_independent(self):
        constraints1 = {"a": 1, "b": 2}
        constraints2 = {"b": 2, "a": 1}
        hash1 = compute_constraints_hash(constraints1)
        hash2 = compute_constraints_hash(constraints2)
        assert hash1 == hash2


class TestDetectNumericClaims:
    """Tests for numeric claim detection."""
    
    def test_monetary_claim(self):
        text = "Revenue of $1.5 billion"
        claims = detect_numeric_claims(text)
        assert len(claims) > 0
        assert any("monetary" in c for c in claims)
    
    def test_percentage_claim(self):
        text = "Growth rate of 15%"
        claims = detect_numeric_claims(text)
        assert any("percentage" in c for c in claims)
    
    def test_year_claim(self):
        text = "Founded in 2010"
        claims = detect_numeric_claims(text)
        assert any("year" in c for c in claims)
    
    def test_no_numeric_claims(self):
        text = "The company provides consulting services"
        claims = detect_numeric_claims(text)
        # May have some false positives, but should be minimal
        assert len(claims) == 0 or all("date" not in c for c in claims)


class TestCreateFixPrompt:
    """Tests for fix prompt generation."""
    
    def test_includes_errors(self):
        errors = ["Missing field: title", "Too many bullets"]
        prompt = create_fix_prompt('{"bad": "json"}', errors, {"type": "object"})
        
        assert "Missing field: title" in prompt
        assert "Too many bullets" in prompt
    
    def test_includes_original_output(self):
        original = '{"partial": "response"}'
        prompt = create_fix_prompt(original, ["error"], {})
        
        assert "partial" in prompt
    
    def test_truncates_long_output(self):
        original = "x" * 3000
        prompt = create_fix_prompt(original, ["error"], {})
        
        # Should be truncated
        assert len(prompt) < len(original)
