"""
Input and output validation utilities for deck generation.
"""

import hashlib
import json
import re
from typing import Any, Optional

import jsonschema
from jsonschema import Draft7Validator, ValidationError

from app.deck.utils.logging import get_logger

logger = get_logger(__name__)


class ValidationResult:
    """Result of a validation operation."""
    
    def __init__(self, valid: bool, errors: list[str] = None, data: Any = None):
        self.valid = valid
        self.errors = errors or []
        self.data = data
    
    def __bool__(self) -> bool:
        return self.valid


def clamp_to_schema_limits(data: Any, schema: dict) -> Any:
    """
    Clamp array fields to schema maxItems limits (non-destructive copy).

    Args:
        data: Parsed JSON data
        schema: JSON schema

    Returns:
        Data with arrays trimmed to maxItems where applicable
    """
    if not isinstance(data, dict) or not isinstance(schema, dict):
        return data

    properties = schema.get("properties", {}) if isinstance(schema.get("properties"), dict) else {}
    if not properties:
        return data

    sanitized = dict(data)
    for key, prop_schema in properties.items():
        if key not in sanitized:
            continue

        value = sanitized.get(key)
        if isinstance(value, list) and isinstance(prop_schema, dict):
            max_items = prop_schema.get("maxItems")
            if isinstance(max_items, int) and max_items >= 0:
                sanitized[key] = value[:max_items]
            # Optionally recurse into array items if they are objects
            item_schema = prop_schema.get("items")
            if isinstance(item_schema, dict):
                sanitized[key] = [
                    clamp_to_schema_limits(item, item_schema) if isinstance(item, dict) else item
                    for item in sanitized[key]
                ]
        elif isinstance(value, dict) and isinstance(prop_schema, dict):
            sanitized[key] = clamp_to_schema_limits(value, prop_schema)

    return sanitized


def validate_ticker(ticker: str) -> ValidationResult:
    """
    Validate stock ticker format.
    
    Args:
        ticker: Ticker symbol to validate
        
    Returns:
        ValidationResult with cleaned ticker or errors
    """
    if not ticker:
        return ValidationResult(False, ["Ticker is required"])
    
    # Clean and uppercase
    cleaned = ticker.strip().upper()
    
    # Validate format: 1-10 alphanumeric chars, dots, hyphens allowed
    if not re.match(r"^[A-Z0-9.\-]{1,10}$", cleaned):
        return ValidationResult(
            False,
            [f"Invalid ticker format: '{ticker}'. Must be 1-10 alphanumeric characters."]
        )
    
    return ValidationResult(True, data=cleaned)


def validate_json_schema(data: dict, schema: dict) -> ValidationResult:
    """
    Validate data against a JSON schema.
    
    Args:
        data: Data to validate
        schema: JSON schema definition
        
    Returns:
        ValidationResult with validation errors if any
    """
    validator = Draft7Validator(schema)
    errors = list(validator.iter_errors(data))
    
    if errors:
        error_messages = []
        for error in errors:
            path = " -> ".join(str(p) for p in error.absolute_path) or "root"
            error_messages.append(f"{path}: {error.message}")
        return ValidationResult(False, error_messages)
    
    return ValidationResult(True, data=data)


def validate_slide_content(slide: dict) -> ValidationResult:
    """
    Validate slide content beyond schema (business rules).
    
    Args:
        slide: Slide data to validate
        
    Returns:
        ValidationResult with validation errors
    """
    errors = []
    
    # Check bullet count
    bullets = slide.get("bullets", [])
    if len(bullets) > 4:
        errors.append(f"Slide has {len(bullets)} bullets, maximum is 4")
    
    # Check for empty content
    if not slide.get("title"):
        errors.append("Slide title is required")
    
    if not bullets:
        errors.append("Slide must have at least one bullet")
    
    # Check for numeric claims without source flags
    flags = slide.get("flags", {})
    for bullet in bullets:
        text = bullet.get("text", "")
        # Detect numbers in text (simple heuristic)
        if re.search(r'\$[\d,]+|\d+%|\d+\s*(million|billion|M|B|K)', text, re.IGNORECASE):
            if not flags.get("contains_numbers") and not bullet.get("source_needed"):
                errors.append(
                    f"Bullet contains numbers but lacks source flag: '{text[:50]}...'"
                )
    
    return ValidationResult(len(errors) == 0, errors)


def validate_section_output(section_data: dict, section_id: str) -> ValidationResult:
    """
    Validate complete section output including business rules.
    
    Args:
        section_data: Section data from LLM
        section_id: Expected section ID
        
    Returns:
        ValidationResult with all validation errors
    """
    errors = []
    
    # Check section ID matches
    if section_data.get("section_id") != section_id:
        errors.append(
            f"Section ID mismatch: expected '{section_id}', got '{section_data.get('section_id')}'"
        )
    
    # Validate slides
    slides = section_data.get("slides", [])
    if not slides:
        errors.append("Section must have at least one slide")
    
    # Section-specific validation
    if section_id == "history":
        if not section_data.get("needs_verification"):
            errors.append("History section must have needs_verification=true")
        if not section_data.get("verification_notes"):
            errors.append("History section must include verification_notes")
    
    if section_id == "rebuttals" and len(slides) > 2:
        errors.append(f"Rebuttals section has {len(slides)} slides, maximum is 2")
    
    # Validate each slide
    for i, slide in enumerate(slides):
        slide_result = validate_slide_content(slide)
        if not slide_result.valid:
            for err in slide_result.errors:
                errors.append(f"Slide {i + 1}: {err}")
    
    return ValidationResult(len(errors) == 0, errors)


def sanitize_llm_output(raw_output: str) -> Optional[dict]:
    """
    Attempt to extract and parse JSON from LLM output.
    
    Args:
        raw_output: Raw string output from LLM
        
    Returns:
        Parsed JSON dict or None if parsing fails
    """
    if not raw_output:
        return None
    
    # Try direct JSON parse
    try:
        return json.loads(raw_output)
    except json.JSONDecodeError:
        pass
    
    # Try to extract JSON from markdown code blocks
    json_patterns = [
        r"```json\s*\n([\s\S]*?)\n```",
        r"```\s*\n([\s\S]*?)\n```",
        r"\{[\s\S]*\}",
    ]
    
    for pattern in json_patterns:
        match = re.search(pattern, raw_output)
        if match:
            try:
                json_str = match.group(1) if match.lastindex else match.group(0)
                return json.loads(json_str)
            except (json.JSONDecodeError, IndexError):
                continue
    
    logger.warning("Failed to parse JSON from LLM output", extra={
        "output_preview": raw_output[:200],
    })
    return None


def compute_constraints_hash(constraints: dict) -> str:
    """
    Compute a stable hash of fund constraints for caching.
    
    Args:
        constraints: Fund constraints dict
        
    Returns:
        Short hash string
    """
    # Sort keys for stability
    normalized = json.dumps(constraints, sort_keys=True)
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def detect_numeric_claims(text: str) -> list[str]:
    """
    Detect potential numeric claims in text that may need verification.
    
    Args:
        text: Text to analyze
        
    Returns:
        List of detected numeric patterns
    """
    patterns = [
        (r'\$[\d,]+(?:\.\d+)?\s*(?:million|billion|M|B|K)?', "monetary"),
        (r'\d+(?:\.\d+)?%', "percentage"),
        (r'\d{4}', "year"),
        (r'(?:founded|established|IPO|acquired)\s+(?:in\s+)?\d{4}', "date_claim"),
        (r'\d+\s*(?:million|billion|M|B|K)\s+(?:users|customers|employees|revenue)', "quantity"),
    ]
    
    claims = []
    for pattern, claim_type in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            claims.append(f"{claim_type}: {match}")
    
    return claims


def has_unverified_numbers(text: str, computed_inputs: Optional[dict] = None) -> bool:
    """
    Check if text contains numeric claims that aren't from computed_inputs.
    
    This is a strict "no fabricated numbers" gate. Any number in the text
    that cannot be traced back to computed_inputs should be flagged.
    
    Args:
        text: Text to check
        computed_inputs: Dict of computed data that contains allowed numbers
        
    Returns:
        True if text contains unverified numeric claims
    """
    # Patterns that indicate numeric claims
    numeric_patterns = [
        r'\$[\d,]+(?:\.\d+)?(?:\s*(?:million|billion|trillion|M|B|T|K))?',  # Money
        r'\d+(?:\.\d+)?%',  # Percentages
        r'\b\d+(?:\.\d+)?\s*(?:million|billion|trillion|M|B|T|K)\b',  # Large numbers
        r'\b(?:over|under|approximately|about|nearly|more than|less than)\s*\d+',  # Quantified claims
        r'\b\d{4,}\b(?!\d)',  # 4+ digit numbers (not part of larger nums)
    ]
    
    # Extract all numbers from text
    found_numbers = set()
    for pattern in numeric_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found_numbers.update(matches)
    
    if not found_numbers:
        return False
    
    # If no computed inputs, any number is unverified
    if not computed_inputs:
        return bool(found_numbers)
    
    # Build set of allowed numbers from computed_inputs
    allowed_numbers = set()
    
    def extract_numbers_from_value(val: Any) -> None:
        """Recursively extract numbers from computed inputs."""
        if isinstance(val, (int, float)):
            # Store various formatted versions
            allowed_numbers.add(str(val))
            allowed_numbers.add(f"{val:,.0f}" if isinstance(val, float) else f"{val:,}")
            if val >= 1e9:
                allowed_numbers.add(f"{val/1e9:.1f}B")
                allowed_numbers.add(f"{val/1e9:.2f} billion")
            elif val >= 1e6:
                allowed_numbers.add(f"{val/1e6:.1f}M")
                allowed_numbers.add(f"{val/1e6:.2f} million")
        elif isinstance(val, str):
            # Extract any numbers in string values
            for num_match in re.findall(r'[\d,.]+', val):
                allowed_numbers.add(num_match)
        elif isinstance(val, dict):
            for v in val.values():
                extract_numbers_from_value(v)
        elif isinstance(val, list):
            for item in val:
                extract_numbers_from_value(item)
    
    extract_numbers_from_value(computed_inputs)
    
    # Check if any found number is NOT in allowed numbers
    for num in found_numbers:
        # Normalize and check
        normalized = re.sub(r'[,$%]', '', num.lower()).strip()
        
        # Check against allowed numbers
        is_allowed = False
        for allowed in allowed_numbers:
            allowed_norm = re.sub(r'[,$%]', '', allowed.lower()).strip()
            if normalized == allowed_norm or normalized in allowed_norm or allowed_norm in normalized:
                is_allowed = True
                break
        
        if not is_allowed:
            # Check for common safe patterns (years in normal range)
            if re.match(r'^(19|20)\d{2}$', normalized):
                # Years like 1999-2099 are generally OK if not making specific claims
                continue
            logger.debug(f"Unverified number detected: {num}")
            return True
    
    return False


def flag_numeric_content(
    bullets: list[dict],
    computed_inputs: Optional[dict] = None,
) -> list[dict]:
    """
    Check bullets for unverified numeric content and flag appropriately.
    
    Args:
        bullets: List of bullet dicts with 'text' field
        computed_inputs: Dict of computed data with allowed numbers
        
    Returns:
        Updated bullets with source_needed flags set appropriately
    """
    updated_bullets = []
    
    for bullet in bullets:
        text = bullet.get("text", "")
        updated = bullet.copy()
        
        if has_unverified_numbers(text, computed_inputs):
            # Flag this bullet as needing a source
            updated["source_needed"] = True
            logger.debug(f"Flagged bullet with unverified numbers: {text[:50]}...")
        
        updated_bullets.append(updated)
    
    return updated_bullets


def create_fix_prompt(original_output: str, errors: list[str], schema: dict) -> str:
    """
    Create a prompt to fix invalid LLM output.
    
    Args:
        original_output: The invalid output
        errors: List of validation errors
        schema: Expected JSON schema
        
    Returns:
        Prompt string for retry
    """
    error_list = "\n".join(f"- {e}" for e in errors)
    schema_str = json.dumps(schema, indent=2)
    
    return f"""Your previous output had validation errors. Please fix and return valid JSON.

ERRORS FOUND:
{error_list}

EXPECTED SCHEMA:
{schema_str}

YOUR PREVIOUS OUTPUT:
{original_output[:2000]}

Please provide a corrected JSON response that:
1. Fixes all the errors listed above
2. Conforms exactly to the schema
3. Contains ONLY the JSON object, no markdown or explanation
"""
