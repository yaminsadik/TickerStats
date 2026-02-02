"""
Test the actual deck generation endpoint with Gemini.
"""

import os
import sys
import json
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

def test_deck_generation_endpoint():
    """Test the actual deck generator with a real request."""
    print("=" * 60)
    print("Testing Deck Generation with Gemini")
    print("=" * 60)
    
    try:
        from app.deck.services.deck_generator import DeckGenerator, DeckGeneratorConfig
        from app.deck.api.schemas import DeckGenerateRequest
        from app.deck.utils.ticker_info import enrich_request_with_ticker_info
        
        # Create generator
        config = DeckGeneratorConfig(
            max_retries=1,
            timeout=30,
            use_cache=False,
        )
        generator = DeckGenerator(config)
        
        # Create test request - only ticker required, company_name and sector auto-fetched!
        request = DeckGenerateRequest(
            ticker="AAPL",
            # company_name and sector will be auto-fetched from yfinance
            fund_constraints={
                "time_horizon": "12-24 months",
                "risk_profile": "moderate",
                "style": "student investment fund pitch deck"
            },
            provider="gemini",
            sections=["overview"],
            reasoning_level="low"
        )
        
        print(f"\n📝 Request created (auto-fetching company info)...")
        print(f"   Ticker: {request.ticker}")
        print(f"   Company (before): {request.company_name}")
        print(f"   Sector (before): {request.sector}")
        
        # Enrich with ticker info
        company_name, sector = enrich_request_with_ticker_info(
            ticker=request.ticker,
            company_name=request.company_name,
            sector=request.sector,
        )
        request.company_name = company_name
        request.sector = sector
        
        print(f"\n✨ Auto-fetched from ticker:")
        print(f"   Company (after): {request.company_name}")
        print(f"   Sector (after): {request.sector}")
        
        print(f"\n📝 Generating deck for: {request.company_name}")
        print(f"   Provider: {request.provider}")
        print(f"   Sections: {request.sections}")
        print(f"   Reasoning: {request.reasoning_level}")
        
        # Get API key
        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not gemini_api_key:
            print("❌ GEMINI_API_KEY not found")
            return False
        
        print(f"\n🔑 Using API key: {gemini_api_key[:20]}...")
        
        # Generate
        print("\n⏳ Generating...")
        response = generator.generate_deck(
            request=request,
            gemini_api_key=gemini_api_key
        )
        
        print(f"\n✅ Generation successful!")
        print(f"   Request ID: {response.request_id}")
        print(f"   Generated {len(response.results)} section(s)")
        print(f"   Provider: {response.provider_used.provider}")
        print(f"   Model: {response.provider_used.model}")
        
        # Show section details
        for section in response.results:
            print(f"\n📊 Section: {section.section_id}")
            print(f"   Needs verification: {section.needs_verification}")
            
            if section.slides:
                print(f"   Slides generated: {len(section.slides)}")
                for i, slide in enumerate(section.slides[:2], 1):
                    print(f"\n   Slide {i}: {slide.title}")
                    if slide.bullets:
                        for bp in slide.bullets[:3]:
                            print(f"     • {bp.text[:60]}...")
        
        # Show errors if any
        if response.errors:
            print("\n❌ Errors:")
            for error in response.errors:
                print(f"   Section: {error.section_id}")
                print(f"   Type: {error.error_type}")
                print(f"   Message: {error.message}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_deck_generation_endpoint()
    sys.exit(0 if success else 1)
