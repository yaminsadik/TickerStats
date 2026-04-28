#!/bin/bash
# Test the historical_performance_current_setup section via API

API_BASE="http://localhost:5000/api/v1"

# Set your Gemini API key (replace with actual key)
GEMINI_API_KEY="${GEMINI_API_KEY:-your-gemini-api-key-here}"

echo "Testing historical_performance_current_setup section..."
echo "=========================================="

curl -X POST "${API_BASE}/deck/generate" \
  -H "Content-Type: application/json" \
  -H "X-Gemini-API-Key: ${GEMINI_API_KEY}" \
  -d '{
    "ticker": "AAPL",
    "company_name": "Apple Inc",
    "sector": "Technology",
    "fund_constraints": {
      "time_horizon": "12-18 months",
      "risk_profile": "moderate",
      "style": "institutional pitch deck"
    },
    "sections": ["historical_performance_current_setup"],
    "provider": "gemini",
    "model": "gemini-3-flash-preview",
    "reasoning_level": "medium",
    "include_comps": false,
    "include_dcf": false
  }' | jq '.'

echo ""
echo "=========================================="
echo "To test all 4 new sections together:"
echo ""
echo 'sections: ["company_snapshot", "business_model_segments", "industry_competitive_landscape", "historical_performance_current_setup"]'
