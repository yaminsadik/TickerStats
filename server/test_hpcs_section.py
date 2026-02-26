#!/usr/bin/env python3
"""
Test the historical_performance_current_setup section locally.
"""

import json
from app.deck.services.sections import get_section

# Minimal test inputs
inputs = {
    "ticker": "AAPL",
    "company_name": "Apple Inc",
    "sector": "Technology",
    "financials": {
        "series": [
            {
                "metric": "revenue",
                "label": "Revenue",
                "unit": "$M",
                "points": [
                    {"period": "fy-5", "value": 274515},
                    {"period": "fy-4", "value": 365817},
                    {"period": "fy-3", "value": 394328},
                    {"period": "fy-2", "value": 383285},
                    {"period": "fy-1", "value": 391035},
                ],
            },
            {
                "metric": "operating_margin",
                "label": "Operating Margin",
                "unit": "%",
                "points": [
                    {"period": "fy-5", "value": 26.8},
                    {"period": "fy-4", "value": 24.1},
                    {"period": "fy-3", "value": 27.3},
                    {"period": "fy-2", "value": 29.8},
                    {"period": "fy-1", "value": 31.2},
                ],
            },
            {
                "metric": "fcf",
                "label": "Free Cash Flow",
                "unit": "$M",
                "points": [
                    {"period": "fy-5", "value": 73365},
                    {"period": "fy-4", "value": 80674},
                    {"period": "fy-3", "value": 92953},
                    {"period": "fy-2", "value": 111443},
                    {"period": "fy-1", "value": 110543},
                ],
            },
        ],
    },
    "price_history": {
        "benchmark_name": "S&P 500",
        "series": [
            {
                "name": "AAPL",
                "points": [
                    {"date": "2023-01", "value": 100.0},
                    {"date": "2024-01", "value": 120.5},
                    {"date": "2025-01", "value": 145.2},
                ],
            },
            {
                "name": "S&P 500",
                "points": [
                    {"date": "2023-01", "value": 100.0},
                    {"date": "2024-01", "value": 110.3},
                    {"date": "2025-01", "value": 125.8},
                ],
            },
        ],
    },
    "rerating": {
        "current": 28.5,
        "median": 22.0,
        "multiple_name": "Forward P/E",
    },
    "recent_events": [
        {
            "date": "2025-11-01",
            "type": "earnings",
            "headline": "Q4 2025 earnings beat consensus by 8%",
            "why_it_matters": "Services revenue grew 15% YoY, exceeding expectations",
            "sentiment_effect": "positive",
        },
        {
            "date": "2025-12-15",
            "type": "product",
            "headline": "Vision Pro international launch announced",
            "why_it_matters": "Expands addressable market for spatial computing",
            "sentiment_effect": "positive",
        },
        {
            "date": "2026-01-20",
            "type": "guidance",
            "headline": "Q1 2026 guidance slightly below consensus",
            "why_it_matters": "Reflects iPhone supply constraints in Asia",
            "sentiment_effect": "negative",
        },
    ],
}


def test_prompt_generation():
    """Test that the prompt is generated correctly."""
    print("=" * 80)
    print("Testing prompt generation for historical_performance_current_setup")
    print("=" * 80)
    
    spec = get_section("historical_performance_current_setup")
    prompt = spec.build_prompt(inputs)
    
    print("\nGenerated Prompt (first 2000 chars):")
    print("-" * 80)
    print(prompt[:2000])
    print("...\n")
    
    print(f"Full prompt length: {len(prompt)} characters")
    print(f"Contains 'FUNDAMENTALS MODULE': {('FUNDAMENTALS MODULE' in prompt)}")
    print(f"Contains 'STOCK VS BENCHMARK MODULE': {('STOCK VS BENCHMARK MODULE' in prompt)}")
    print(f"Contains 'VALUATION RERATING MODULE': {('VALUATION RERATING MODULE' in prompt)}")
    print(f"Contains 'WHAT CHANGED MODULE': {('WHAT CHANGED MODULE' in prompt)}")
    

def test_postprocess():
    """Test that postprocess works with mock LLM output."""
    print("\n" + "=" * 80)
    print("Testing postprocess with mock LLM output")
    print("=" * 80)
    
    # Mock LLM output matching our schema
    mock_llm_output = {
        "setup_mode": "both",
        "fundamentals": {
            "window_years": 5,
            "series": [
                {
                    "metric": "revenue",
                    "label": "Revenue",
                    "unit": "$M",
                    "points": [
                        {"period": "fy-5", "value": 274515},
                        {"period": "fy-4", "value": 365817},
                        {"period": "fy-3", "value": 394328},
                        {"period": "fy-2", "value": 383285},
                        {"period": "fy-1", "value": 391035},
                    ],
                },
            ],
            "highlights": [
                "Revenue grew from $275B in FY-5 to $391B in FY-1, representing 42% cumulative growth",
                "Operating margin expanded from 26.8% to 31.2%, demonstrating pricing power and operational leverage",
                "Free cash flow increased from $73B to $111B, highlighting strong cash generation",
            ],
            "confidence": "high",
        },
        "stock": {
            "benchmark_name": "S&P 500",
            "series": [
                {"name": "AAPL", "points": [{"date": "2023-01", "value": 100.0}]},
            ],
            "takeaways": [
                "Stock outperformed S&P 500 by 15.4% over 2 years (45.2% vs 25.8%)",
                "Strong performance driven by services growth and margin expansion",
            ],
            "confidence": "high",
        },
        "rerating": {
            "current_vs_median": ["Current Forward P/E: 28.5x vs historical median: 22.0x"],
            "peer_context": [],
            "series": [],
            "takeaways": [
                "Multiple expanded 30% above historical median, reflecting services mix shift",
                "Premium justified by accelerating services growth and ecosystem lock-in",
            ],
            "confidence": "medium",
        },
        "what_changed": {
            "events": [
                {
                    "date": "2025-11-01",
                    "type": "earnings",
                    "headline": "Q4 2025 earnings beat consensus by 8%",
                    "why_it_matters": "Services revenue grew 15% YoY, exceeding expectations",
                    "sentiment_effect": "positive",
                },
                {
                    "date": "2026-01-20",
                    "type": "guidance",
                    "headline": "Q1 2026 guidance slightly below consensus",
                    "why_it_matters": "Reflects iPhone supply constraints in Asia",
                    "sentiment_effect": "negative",
                },
            ],
            "current_sentiment_summary": "Market sentiment is cautiously optimistic following strong Q4 earnings, though tempered by near-term supply constraints",
            "confidence": "high",
        },
        "low_confidence_flag": False,
    }
    
    spec = get_section("historical_performance_current_setup")
    result = spec.postprocess(mock_llm_output, inputs)
    
    print(f"\nSection ID: {result['section_id']}")
    print(f"Number of slides: {len(result['slides'])}")
    print(f"Needs verification: {result['needs_verification']}")
    
    for i, slide in enumerate(result['slides'], 1):
        print(f"\n--- Slide {i}: {slide['title']} ---")
        print(f"Bullets ({len(slide['bullets'])}):")
        for bullet in slide['bullets']:
            print(f"  • {bullet['text'][:100]}...")
        print(f"Speaker notes preview: {slide['speaker_notes'][:150]}...")


if __name__ == "__main__":
    test_prompt_generation()
    test_postprocess()
    print("\n" + "=" * 80)
    print("✓ All tests passed!")
    print("=" * 80)
