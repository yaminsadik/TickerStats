# Deck Generation API

A production-grade Flask backend for generating AI-powered investment pitch deck sections.

## Overview

This service generates structured slide content for investment pitch decks using Google Gemini. It integrates with the existing yfinance-based comparables table generator to provide market context.

## Features

- **Gemini Generation**: Gemini-backed structured slide generation
- **Structured Output**: Strict JSON output format for frontend slide rendering
- **Section Types**: Overview, History, SWOT, Porter's Five Forces, Rebuttals, Layout
- **Validation**: Server-side JSON schema validation with retry on failure
- **Caching**: In-memory or Redis caching for performance
- **Rate Limiting**: Per-IP rate limiting with Flask-Limiter
- **Logging**: Structured JSON logging with request tracing

## Quick Start

### Installation

```bash
cd server
pip install -r requirements.txt
```

### Configuration

Create a `.env` file in the `server` directory:

```env
# Required: Gemini API key
GEMINI_API_KEY=your-gemini-key

# Optional: Flask settings
FLASK_DEBUG=false
FLASK_HOST=0.0.0.0
FLASK_PORT=5000

# Optional: Generation settings
DECK_MAX_RETRIES=2
DECK_TIMEOUT=60
DECK_USE_CACHE=true

# Optional: Rate limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_DEFAULT=100 per minute
RATE_LIMIT_GENERATE=10 per minute

# Optional: Redis for distributed caching
# CACHE_TYPE=redis
# REDIS_URL=redis://localhost:6379/0
```

### Running the Server

```bash
# Development
python -m app.deck.app

# Or with Flask CLI
FLASK_APP=app.deck.app flask run

# Production (with gunicorn)
gunicorn -w 4 -b 0.0.0.0:5000 "app.deck.app:app"
```

## API Endpoints

### GET /api/v1/sections

Get available deck sections.

**Response:**

```json
{
  "sections": [
    {
      "id": "overview",
      "label": "Company Overview + Catalysts",
      "description": "..."
    },
    {
      "id": "history",
      "label": "History Timeline (Draft)",
      "description": "..."
    },
    { "id": "swot", "label": "SWOT", "description": "..." },
    {
      "id": "porters_five",
      "label": "Porter's Five Forces",
      "description": "..."
    },
    { "id": "rebuttals", "label": "Rebuttals / Q&A", "description": "..." },
    { "id": "layout", "label": "Layout Decisions", "description": "..." }
  ]
}
```

**Example:**

```bash
curl http://localhost:5000/api/v1/sections
```

### POST /api/v1/deck/generate

Generate pitch deck sections.

**Request:**

```json
{
  "ticker": "ACN",
  "company_name": "Accenture",
  "sector": "IT",
  "fund_constraints": {
    "time_horizon": "12-24 months",
    "risk_profile": "moderate",
    "portfolio_context": "Tech-focused portfolio",
    "style": "student investment fund pitch deck"
  },
  "sections": [
    "overview",
    "history",
    "business_model_segments",
    "industry_competitive_landscape",
    "swot"
  ],
  "provider": "gemini",
  "model": "gemini-3-flash-preview",
  "reasoning_level": "medium",
  "include_comps": true
}
```

**Response:**

```json
{
  "ticker": "ACN",
  "provider_used": {
    "provider": "gemini",
    "model": "gemini-3-flash-preview",
    "reasoning_level": "medium"
  },
  "generated_at": "2026-01-31T12:00:00Z",
  "computed_inputs": {
    "comps_table": {...}
  },
  "results": [
    {
      "section_id": "overview",
      "slides": [
        {
          "slide_id": "overview_1",
          "title": "Accenture: Global IT Services Leader",
          "bullets": [
            {"text": "Leading professional services company", "source_needed": false},
            {"text": "Strong presence in digital transformation", "source_needed": false}
          ],
          "speaker_notes": "Introduce Accenture as a global leader...",
          "layout_hints": {"style": "bullets", "max_bullets": 4},
          "flags": {"needs_sources": false, "contains_numbers": false, "is_draft": false}
        }
      ],
      "needs_verification": false,
      "verification_notes": []
    },
    {
      "section_id": "history",
      "needs_verification": true,
      "verification_notes": ["Verify IPO date", "Confirm acquisition timeline"],
      "slides": [...]
    }
  ],
  "errors": [],
  "request_id": "abc123"
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/api/v1/deck/generate \
  -H "Content-Type: application/json" \
  -H "X-Gemini-API-Key: your-gemini-key" \
  -d '{
    "ticker": "ACN",
    "company_name": "Accenture",
    "sector": "IT",
    "fund_constraints": {
      "time_horizon": "12-24 months",
      "risk_profile": "moderate"
    },
    "sections": ["overview", "swot"],
    "provider": "gemini",
    "reasoning_level": "medium"
  }'
```

### POST /api/v1/deck/plan

Get suggested sections and ordering without generating content.

**Request:**

```json
{
  "ticker": "ACN",
  "company_name": "Accenture",
  "sector": "IT",
  "fund_constraints": {
    "time_horizon": "12-24 months",
    "risk_profile": "moderate"
  },
  "provider": "gemini"
}
```

**Response:**

```json
{
  "ticker": "ACN",
  "company_name": "Accenture",
  "suggested_sections": [
    {
      "id": "overview",
      "label": "Company Overview + Catalysts",
      "priority": 1,
      "rationale": "Essential for introducing the IT investment thesis",
      "estimated_slides": 3
    },
    ...
  ],
  "recommended_order": ["overview", "history", "swot", "porters_five", "rebuttals", "layout"],
  "notes": "Standard investment pitch deck structure for IT sector.",
  "request_id": "xyz789"
}
```

**Example:**

```bash
curl -X POST http://localhost:5000/api/v1/deck/plan \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "ACN",
    "sector": "IT",
    "fund_constraints": {
      "time_horizon": "12-24 months",
      "risk_profile": "moderate"
    }
  }'
```

## Supported Sections

| Section ID     | Description                                      | Max Slides |
| -------------- | ------------------------------------------------ | ---------- |
| `overview`     | Company overview, segments, "why now", catalysts | 3          |
| `history`      | Timeline of key events (requires verification)   | 2          |
| `swot`         | Strengths, Weaknesses, Opportunities, Threats    | 3          |
| `porters_five` | Porter's Five Forces competitive analysis        | 2          |
| `rebuttals`    | Q&A preparation with objections and responses    | 2          |
| `layout`       | Presentation structure and guidance              | 1          |

## Provider Configuration

Models available:

- `gemini-3-flash-preview` (standard/default)
- `gemini-3-pro-preview` (Pro/Enterprise)

### Reasoning Levels

| Level    | Temperature | Use Case                         |
| -------- | ----------- | -------------------------------- |
| `low`    | 0.3         | Conservative, factual content    |
| `medium` | 0.7         | Balanced creativity and accuracy |
| `high`   | 0.9         | More creative, varied outputs    |

## Slide Output Format

Each slide follows this structure:

```json
{
  "slide_id": "section_1",
  "title": "Slide Title",
  "bullets": [
    { "text": "Concise bullet point", "source_needed": false },
    {
      "text": "Claim needing verification (source needed)",
      "source_needed": true
    }
  ],
  "speaker_notes": "Expanded talking points for presenter...",
  "layout_hints": {
    "style": "bullets",
    "max_bullets": 4,
    "suggested_visual": "chart"
  },
  "flags": {
    "needs_sources": false,
    "contains_numbers": false,
    "is_draft": false
  }
}
```

## Content Guidelines

The generator enforces these constraints:

- Maximum 4 bullets per slide
- No fabricated numeric claims (marked with "(source needed)")
- History section always marked as draft requiring verification
- Professional, fund-ready tone
- Concise, actionable content

## Running Tests

```bash
cd server
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=app.deck --cov-report=term-missing
```

## Architecture

```
server/app/deck/
├── __init__.py
├── app.py              # Flask application factory
├── config.py           # Configuration management
├── api/
│   ├── __init__.py
│   ├── routes_deck.py  # API endpoints (Blueprint)
│   └── schemas.py      # Pydantic models and JSON schemas
├── services/
│   ├── __init__.py
│   ├── llm_base.py     # Abstract LLM provider interface
│   ├── llm_gemini.py   # Gemini implementation
│   ├── deck_generator.py # Generation orchestrator
│   ├── comps_service.py  # yfinance wrapper
│   └── prompts.py      # Section-specific prompts
└── utils/
    ├── __init__.py
    ├── validation.py   # Input/output validation
    ├── logging.py      # Structured JSON logging
    └── cache.py        # Caching interface
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "error": "Error type",
  "message": "Detailed message",
  "request_id": "abc123"
}
```

HTTP Status Codes:

- `200`: Success
- `400`: Validation error / Bad request
- `429`: Rate limit exceeded
- `500`: Internal server error

## Environment Variables Reference

| Variable              | Default          | Description                           |
| --------------------- | ---------------- | ------------------------------------- |
| `GEMINI_API_KEY`      | -                | Google Gemini API key                 |
| `FLASK_DEBUG`         | `false`          | Enable debug mode                     |
| `FLASK_HOST`          | `0.0.0.0`        | Server host                           |
| `FLASK_PORT`          | `5000`           | Server port                           |
| `DECK_MAX_RETRIES`    | `2`              | Max LLM retries on validation failure |
| `DECK_TIMEOUT`        | `60`             | LLM request timeout (seconds)         |
| `DECK_USE_CACHE`      | `true`           | Enable response caching               |
| `CACHE_TYPE`          | `memory`         | Cache backend (`memory` or `redis`)   |
| `CACHE_TTL`           | `3600`           | Cache TTL (seconds)                   |
| `REDIS_URL`           | -                | Redis connection URL                  |
| `RATE_LIMIT_ENABLED`  | `true`           | Enable rate limiting                  |
| `RATE_LIMIT_DEFAULT`  | `100 per minute` | Default rate limit                    |
| `RATE_LIMIT_GENERATE` | `10 per minute`  | Generate endpoint limit               |
| `LOG_LEVEL`           | `INFO`           | Logging level                         |
| `LOG_JSON`            | `true`           | Use JSON log format                   |

## License

MIT
