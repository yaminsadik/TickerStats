"""
Quick test to validate VALUATION section code structure.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

def test_schema_changes():
    """Test that VALUATION section is properly defined."""
    print("=" * 60)
    print("Testing VALUATION section schema")
    print("=" * 60)
    
    from app.deck.api.schemas import SectionId, SECTION_METADATA
    
    # Check enum
    assert hasattr(SectionId, 'VALUATION'), "VALUATION not in SectionId enum"
    assert SectionId.VALUATION == "valuation"
    print("✅ SectionId.VALUATION enum exists")
    
    # Check metadata
    assert "valuation" in SECTION_METADATA, "valuation not in SECTION_METADATA"
    val_meta = SECTION_METADATA["valuation"]
    print(f"✅ VALUATION metadata exists:")
    print(f"   Label: {val_meta['label']}")
    print(f"   Description: {val_meta['description']}")
    print(f"   Min slides: {val_meta['min_slides']}")
    print(f"   Max slides: {val_meta['max_slides']}")
    
    return True


def test_prompt_function():
    """Test that valuation prompt function exists."""
    print("\n" + "=" * 60)
    print("Testing VALUATION prompt function")
    print("=" * 60)
    
    from app.deck.services.prompts import get_valuation_prompt, SECTION_PROMPT_MAP
    
    # Check function exists
    assert callable(get_valuation_prompt), "get_valuation_prompt not callable"
    print("✅ get_valuation_prompt function exists")
    
    # Check it's in the mapping
    assert "valuation" in SECTION_PROMPT_MAP, "valuation not in SECTION_PROMPT_MAP"
    assert SECTION_PROMPT_MAP["valuation"] == get_valuation_prompt
    print("✅ valuation mapped in SECTION_PROMPT_MAP")
    
    # Test calling it
    prompt = get_valuation_prompt(
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Technology",
        fund_constraints={"style": "test"},
        dcf_data="Test DCF data"
    )
    
    assert "DCF" in prompt or "Valuation" in prompt
    assert "AAPL" in prompt
    print(f"✅ Prompt generated successfully ({len(prompt)} chars)")
    print(f"\nPrompt preview (first 300 chars):")
    print(prompt[:300] + "...")
    
    return True


def test_dcf_formatting():
    """Test DCF formatting methods."""
    print("\n" + "=" * 60)
    print("Testing DCF formatting methods")
    print("=" * 60)
    
    from app.deck.services.deck_generator import DeckGenerator
    
    generator = DeckGenerator()
    
    # Test concise format
    test_dcf = {
        "valuation": {
            "targetPrice": 150.50,
            "upsidePct": 15.5
        }
    }
    
    concise = generator._format_dcf_for_prompt(test_dcf)
    print(f"✅ Concise format: '{concise}'")
    assert "$150.50" in concise
    assert "+15.5%" in concise
    assert len(concise) < 100, f"Concise format too long: {len(concise)} chars"
    
    # Test detailed format
    test_dcf_full = {
        "inputs": {
            "freeCashFlow": 100000000000,
            "growthRate": 0.05,
            "discountRate": 0.08,
            "terminalGrowthRate": 0.025
        },
        "valuation": {
            "currentPrice": 130.50,
            "targetPrice": 150.50,
            "upsidePct": 15.5
        },
        "breakdown": {
            "forecastPeriodPV": 80000000000,
            "terminalValue": 120000000000,
            "enterpriseValue": 200000000000,
            "equityValue": 180000000000
        },
        "sources": {
            "fcf": "yfinance",
            "price": "yfinance"
        }
    }
    
    detailed = generator._format_dcf_detailed(test_dcf_full)
    print(f"✅ Detailed format: {len(detailed)} chars")
    assert "Free Cash Flow" in detailed
    assert "Growth Rate" in detailed
    assert "Target Price" in detailed
    print(f"\nDetailed preview (first 500 chars):")
    print(detailed[:500] + "...")
    
    return True


def test_get_section_prompt():
    """Test that get_section_prompt handles valuation correctly."""
    print("\n" + "=" * 60)
    print("Testing get_section_prompt routing")
    print("=" * 60)
    
    from app.deck.services.prompts import get_section_prompt
    
    # Test with valuation section
    prompt = get_section_prompt(
        section_id="valuation",
        ticker="AAPL",
        company_name="Apple Inc.",
        sector="Technology",
        fund_constraints={"style": "test"},
        dcf_summary="DCF Target: $150.50 (+15.5% vs market)"
    )
    
    assert "valuation" in prompt.lower() or "dcf" in prompt.lower()
    print(f"✅ Valuation prompt routed correctly ({len(prompt)} chars)")
    
    return True


if __name__ == "__main__":
    try:
        test_schema_changes()
        test_prompt_function()
        test_dcf_formatting()
        test_get_section_prompt()
        
        print("\n" + "=" * 60)
        print("✅ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
